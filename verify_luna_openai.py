"""Optional direct OpenAI Luna diagnostic: free preview, --confirm-paid for <=2 requests."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
import uuid
import httpx
from backend.billing import reported, summarize
from backend.config import Settings
from backend.models import MODELS, V4_POLICY_VERSION, POLICY_VERSION, payload, strict_json
from backend.native_decisions import (translate, parse_native, NativeSchemaError,
                                      NativeIdentityError, NativeRefusal)
from backend.store import Store
from verify_cube_diagnostics import plan, first_action_correct

ENDPOINT = "https://api.openai.com/v1/decisions"
MODEL = "gpt-6-luna"
LEDGER_MODEL = "openai-direct/gpt-6-luna"
POLICIES = {"v4": V4_POLICY_VERSION, "v5": POLICY_VERSION}


def native_payload(state, *, policy="v4"):
    return translate(payload(MODELS[1], state, [], policy_version=POLICIES[policy]))


def safe_metadata(value, secret):
    """Whitelist callers select metadata; redact reflected credentials before persistence."""
    if isinstance(value, str):
        value = value.replace(secret, "[REDACTED]") if secret else value
        return re.sub(r"(?i)\b(?:Bearer\s+\S+|sk-[A-Za-z0-9_-]+)", "[REDACTED]", value)[:2048]
    if isinstance(value, list):
        return [safe_metadata(v, secret) for v in value]
    if isinstance(value, dict):
        return {safe_metadata(k, secret): safe_metadata(v, secret) for k, v in value.items()}
    return value


def preview(*, policy="v4", case="all"):
    if policy not in POLICIES or case not in ("all", "1", "2"):
        raise ValueError("Unknown diagnostic policy or case")
    cases = plan(1)["cases"]
    if case != "all":
        cases = [cases[int(case) - 1]]
    return {"kind": "direct_openai_luna_diagnostic_not_benchmark", "provider": "OpenAI",
            "endpoint": ENDPOINT, "model": MODEL, "policy_version": POLICIES[policy],
            "paid_calls_authorized": False, "request_cap": len(cases), "retries": 0,
            "cases": cases}


async def diagnose(*, confirm_paid=False, api_key=None, settings=None, transport=None,
                   policy="v4", case="all"):
    selection = preview(policy=policy, case=case)
    if not confirm_paid:
        raise SystemExit("BLOCKED: explicit --confirm-paid is required")
    cfg = settings or Settings.env()
    key = os.getenv("OPENAI_API_KEY", "").strip() if api_key is None else api_key.strip()
    if not key or not cfg.allow_live or cfg.mock_mode:
        raise SystemExit("BLOCKED: OPENAI_API_KEY, ALLOW_LIVE=true and OPENROUTER_MOCK_MODE=false required")
    if cfg.retries != 0:
        raise SystemExit("BLOCKED: direct diagnostics require API_RETRIES=0; configuration unchanged")
    store = Store(cfg.database)
    report, requests = None, []
    try:
        if any(r["status"] == "RUNNING" for r in store.all()):
            raise SystemExit("BLOCKED: a saved run is active")
        if cfg.budget - store.used() < selection["request_cap"]:
            raise SystemExit("BLOCKED: insufficient persistent requests remain; budget unchanged")
        report = {**selection, "id": "openai-direct-diagnostic-" + uuid.uuid4().hex,
                  "mode": "live", "source": "CubeRace: System-1 vs LLM",
                  "paid_calls_authorized": True, "assignment_benchmark_evidence": False,
                  "move_limit": 30, "metric": "HTM", "timeout_seconds": cfg.timeout, "results": []}
        report["results"] = [{"case_id": case["id"], "status": "NOT_RUN", "requests": [],
                              "first_action_correct": None} for case in report["cases"]]
        blocked = None
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            for index, (case, entry) in enumerate(zip(report["cases"], report["results"])):
                if blocked:
                    entry["error"] = blocked
                    continue
                ledger_id = store.reserve(cfg.budget, LEDGER_MODEL, report["id"], index, 0)
                if ledger_id is None:
                    entry.update(status="BUDGET_EXHAUSTED", error="Persistent request cap reached")
                    blocked = entry["error"]
                    continue
                record = {"ledger_id": ledger_id, "run_id": report["id"], "race_index": index,
                    "request_index": len(requests) + 1, "retry": 0, "provider": "OpenAI",
                    "provider_route": "direct_openai_decisions", "endpoint": ENDPOINT,
                    "requested_model_id": MODEL, "effective_model_id": None,
                    "policy_version": POLICIES[policy], "history_window": 6,
                    "model_visible_history": [], "moves_remaining": 30, "http_status": None,
                    "request_id": None, "latency_ms": None, "outcome": "PENDING",
                    "usage": None, "provider_usage": None, "billing": reported(None)}
                entry["requests"].append(record)
                requests.append(record)
                start = time.perf_counter()
                try:
                    response = await client.post(ENDPOINT, json=native_payload(case["initial_state"], policy=policy),
                        headers={"Authorization": f"Bearer {key}"}, timeout=cfg.timeout)
                    record["latency_ms"] = (time.perf_counter() - start) * 1000
                    record.update(http_status=response.status_code,
                        request_id=safe_metadata(response.headers.get("x-request-id"), key))
                    try:
                        body = strict_json(response.text)
                    except (ValueError, TypeError):
                        body = None
                    if isinstance(body, dict):
                        # Retain native refusal/choice evidence, with reflected secrets redacted.
                        record["provider_answers"] = safe_metadata(body.get("answers"), key)
                        record["effective_model_id"] = safe_metadata(body.get("model"), key)
                        usage = body.get("usage")
                        if isinstance(usage, dict):
                            record["provider_usage"] = safe_metadata(usage, key)
                            # Preserve native usage; add only the canonical reasoning-details alias.
                            record["usage"] = {**record["provider_usage"],
                                "completion_tokens_details": record["provider_usage"].get("output_tokens_details")}
                            record["billing"] = reported(record["usage"])
                        error = body.get("error")
                        if isinstance(error, dict):
                            record["api_error"] = safe_metadata(
                                {k: error.get(k) for k in ("type", "code", "message", "param")}, key)
                    if response.status_code >= 300 or (isinstance(body, dict) and body.get("error") is not None):
                        record["outcome"] = "HTTP_ERROR" if response.status_code >= 300 else "API_ERROR"
                        entry.update(status="API_ERROR", error=f"OpenAI HTTP {response.status_code}; no retry or fallback")
                        if response.status_code in (400, 401, 402, 403, 404, 422) or 300 <= response.status_code < 400:
                            blocked = entry["error"]
                        continue
                    move, metadata = parse_native(body)
                    record.update(metadata, outcome="VALID")
                    entry.update(status="VALID_RESPONSE", move=move,
                                 first_action_correct=first_action_correct(case["initial_state"], move, 1))
                except NativeIdentityError as exc:
                    record["outcome"] = "MODEL_ID_MISMATCH"
                    entry.update(status="UNAVAILABLE", error=str(exc))
                    blocked = str(exc)
                except NativeRefusal as exc:
                    record["outcome"] = "REFUSED"
                    entry.update(status="REFUSED", error=str(exc))
                except NativeSchemaError as exc:
                    record["outcome"] = "UNSUPPORTED_SCHEMA"
                    entry.update(status="API_ERROR", error=str(exc))
                    blocked = str(exc)
                except ValueError:
                    record["outcome"] = "MALFORMED"
                    entry.update(status="API_ERROR", error="Illegal move rejected; no correction")
                except httpx.HTTPError as exc:
                    record["outcome"] = "TIMEOUT" if isinstance(exc, httpx.TimeoutException) else "TRANSPORT_ERROR"
                    entry.update(status="API_ERROR", error="OpenAI transport failure; no retry or fallback")
                except asyncio.CancelledError:
                    record["outcome"] = "CANCELLED"
                    entry["status"] = "ABORTED"
                    raise
                finally:
                    if record["latency_ms"] is None:
                        record["latency_ms"] = (time.perf_counter() - start) * 1000
                    store.record_request(ledger_id, record)
    finally:
        try:
            if report is not None:
                # Preserve evidence even on cancellation; never insert a benchmark run.
                now = datetime.now(timezone.utc)
                report.update(timestamp=now.isoformat(), request_count=len(requests),
                    billing=summarize(requests), planned_first_actions=selection["request_cap"],
                    valid_first_actions=sum(r["status"] == "VALID_RESPONSE" for r in report["results"]),
                    correct_first_actions=sum(r["first_action_correct"] is True for r in report["results"]))
                directory = Path("data/direct-openai")
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / f"luna-{policy}-{now:%Y%m%dT%H%M%S%fZ}-{report['id'][-8:]}.json"
                with path.open("x", encoding="utf-8") as file:
                    json.dump(report, file, indent=2, allow_nan=False)
                print(json.dumps({"report": str(path), "provider": "OpenAI",
                    "request_count": len(requests), "correct_first_actions": report["correct_first_actions"],
                    "valid_first_actions": report["valid_first_actions"], "policy_version": POLICIES[policy],
                    "statuses": [r["status"] for r in report["results"]], "billing": report["billing"]}))
        finally:
            store.close()
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-paid", action="store_true",
                        help="Authorize at most two direct OpenAI requests; no retries or provider fallback")
    parser.add_argument("--policy", choices=POLICIES, default="v4",
                        help="Fixed prompt policy; v4 baseline by default, v5 adds existing general turn rules")
    parser.add_argument("--case", choices=("all", "1", "2"), default="all",
                        help="Select one diagnostic state (one request) or both (at most two)")
    args = parser.parse_args(argv)
    if args.confirm_paid:
        asyncio.run(diagnose(confirm_paid=True, policy=args.policy, case=args.case))
    else:
        print(json.dumps(preview(policy=args.policy, case=args.case), indent=2))


if __name__ == "__main__":
    main()
