"""Read-only localhost readiness check. Never starts a run or contacts OpenRouter."""
import argparse
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
import httpx
from backend.config import Settings
from backend.runtime import ROOT, runtime_info

EXPECTED_IDS = {
    "typesafe/jev-1.13": ["typesafe/jev-1.13", "typesafe/jev-1.13-20260917"],
    "openai/gpt-6-luna-decisions": ["openai/gpt-6-luna-decisions", "openai/gpt-6-luna-decisions-20261006"],
    "cloudflare/clef": ["cloudflare/clef"],
    "anthropic/claude-opus-5.5": ["anthropic/claude-opus-5.5"],
}


def localhost_url(value):
    try:
        url = urlsplit(value)
        valid = (url.scheme == "http" and url.hostname in ("127.0.0.1", "localhost", "::1")
                 and url.username is None and url.password is None and not url.query
                 and not url.fragment and url.path in ("", "/") and url.port != 0)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Use an http localhost base URL without credentials, query or path")
    return value.rstrip("/")


def database_status(path):
    path = Path(path).resolve()
    # mode=ro cannot create, recover, reset or modify the live database.
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2) as db:
        used = db.execute("SELECT used FROM budget WHERE id=1").fetchone()[0]
        runs = [json.loads(body) for body, in db.execute("SELECT body FROM runs")]
        unknown = sum(json.loads(body).get("usage") is None
                      for body, in db.execute("SELECT body FROM requests"))
        return {"path": str(path), "used": used, "run_count": len(runs),
                "running_runs": sum(r["status"] == "RUNNING" for r in runs),
                "requests_without_usage": unknown}


def check(base_url="http://127.0.0.1:8000", *, client=None, settings=None):
    base_url = localhost_url(base_url)
    settings = settings or Settings.env()
    local = runtime_info()
    checks, warnings = {}, []
    checks["local_project_directory"] = Path.cwd().resolve() == ROOT
    checks["local_model_module"] = Path(local["models_module"]).resolve() == ROOT / "backend/models.py"
    checks["local_policy"] = local["policy_version"] == "state-action-v5-permutations" and local["history_window"] == 6
    checks["local_allowlist"] = local["allowed_effective_ids"] == EXPECTED_IDS
    checks["local_claude"] = settings.claude_reasoning_effort == "low" and settings.claude_max_tokens == 1024
    checks["local_zero_retries"] = settings.retries == 0
    checks["local_live_enabled"] = bool(settings.key and settings.allow_live and not settings.mock_mode)
    database = None
    try:
        database = database_status(settings.database)
        checks["database_readable"] = True
        checks["no_active_run"] = database["running_runs"] == 0
        checks["request_budget_remaining"] = database["used"] < settings.budget
    except (OSError, sqlite3.Error, TypeError, KeyError, ValueError):
        checks["database_readable"] = False
    health, config = {}, {}
    own_client = client is None
    client = client or httpx.Client(timeout=5, follow_redirects=False, trust_env=False)
    try:
        for endpoint, target in (("/api/health", health), ("/api/config", config)):
            response = client.get(base_url + endpoint, follow_redirects=False)
            response.raise_for_status()
            target.update(response.json())
        checks["server_health"] = health.get("status") == "ok"
        server = health.get("runtime") or {}
        if not isinstance(server, dict):
            raise ValueError("Invalid runtime metadata")
        for field in ("git_commit", "source_sha256", "policy_version", "history_window",
                      "allowed_effective_ids", "project_root", "models_module", "python", "working_directory"):
            checks["server_" + field] = bool(local.get(field)) and server.get(field) == local[field]
        checks["server_live_enabled"] = config.get("live_enabled") is True
        checks["server_claude"] = config.get("claude_reasoning_effort") == "low" and config.get("claude_max_tokens") == 1024
        checks["server_zero_retries"] = config.get("retries") == 0
        checks["server_move_limit"] = config.get("move_limit") == 30
        checks["server_assigned_models"] = [m["id"] for m in config.get("models", [])] == list(EXPECTED_IDS)
        checks["server_budget_matches"] = bool(database) and config.get("budget_used") == database["used"] and config.get("budget_limit") == settings.budget
        checks["server_database_path"] = bool(database) and server.get("database") == database["path"]
        page = client.get(base_url + "/", follow_redirects=False)
        page.raise_for_status()
        checks["student_identity"] = "Rayyan Merchant · 23K-0073" in page.text
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        checks["server_health"] = False
        warnings.append("Server unavailable or invalid health/config response; start the correct local server.")
    finally:
        if own_client:
            client.close()
    if local["backend_dirty"]:
        warnings.append("Backend has uncommitted changes; source hashes identify the loaded content, not the commit alone.")
    remaining = settings.budget - database["used"] if database else None
    worst_case = 5 * 4 * 30 * (1 + settings.retries)
    if remaining is not None and remaining < worst_case:
        warnings.append(f"Five-puzzle worst case needs {worst_case} requests; only {remaining} remain. Budget was not increased.")
    billing = config.get("billing", {})
    if billing.get("unknown_cost_requests"):
        warnings.append(f"{billing['unknown_cost_requests']} requests have unknown cost; known cost is not complete spending.")
    warnings.append("Offline/local checks do not prove external API availability, solving quality, or completion below $1. Provider USD cap not queried.")
    return {"local_runtime_ready": all(checks.values()), "checks": checks,
            "local_runtime": local, "server_runtime": health.get("runtime"),
            "database": database, "persistent_budget_limit": settings.budget,
            "persistent_requests_remaining": remaining,
            "five_puzzle_worst_case_requests": worst_case,
            "five_puzzle_worst_case_covered": remaining is not None and remaining >= worst_case,
            "billing": billing, "warnings": warnings, "inference_requests": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Local server base URL only")
    args = parser.parse_args(argv)
    try:
        report = check(args.url)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))
    return 0 if report["local_runtime_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
