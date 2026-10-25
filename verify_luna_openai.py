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
from backend.billing import number, reported, summarize
from backend.config import Settings
from backend.cube import MOVES
from backend.models import MODELS, V4_POLICY_VERSION, payload, strict_json
from backend.store import Store
from verify_cube_diagnostics import plan, first_action_correct

ENDPOINT = "https://api.openai.com/v1/decisions"
MODEL = "gpt-6-luna"
LEDGER_MODEL = "openai-direct/gpt-6-luna"


class NativeSchemaError(ValueError):
    pass


class NativeIdentityError(ValueError):
    pass


class NativeRefusal(ValueError):
    pass


def native_payload(state):
    baseline = payload(MODELS[1], state, [], policy_version=V4_POLICY_VERSION)
    question = baseline["questions"]["next_move"]
    return {"model": MODEL,
            "input": [{"role": "user", "content": [{"type": "input_json", "data": baseline["state"]}]}],
            "questions": [{"type": "choice", "name": "next_move", "instructions": question["instructions"],
                           "choices": [{"value": m, "description": description}
                                       for m, description in question["criteria"].items()]}]}


def parse_native(body):
    if not isinstance(body, dict):
        raise NativeSchemaError("Expected native Decision object")
    if body.get("model") != MODEL:
        raise NativeIdentityError("Missing or unrecognized native model identity; no substitution")
    answers = body.get("answers")
    if not isinstance(answers, list) or len(answers) != 1 or not isinstance(answers[0], dict):
        raise NativeSchemaError("Expected one native answer in an array")
    answer = answers[0]
    if answer.get("name") != "next_move":
        raise NativeSchemaError("Unexpected native question name")
    if answer.get("type") == "refusal":
        raise NativeRefusal("OpenAI declined the next_move question")
    if answer.get("type") != "choice":
        raise NativeSchemaError("Expected native choice answer")
    move = answer.get("choice")
    if not isinstance(move, str) or move not in MOVES:
        raise ValueError("Expected exactly one legal move")
    confidence = number(answer.get("confidence"))
    values = answer.get("probabilities")
    if confidence is None or confidence > 1 or not isinstance(values, list) or len(values) != 18:
        raise NativeSchemaError("Missing or invalid native confidence/probabilities")
    probabilities = {}
    for item in values:
        if not isinstance(item, dict):
            raise NativeSchemaError("Invalid native probability entry")
        action, probability = item.get("value"), number(item.get("probability"))
        if (not isinstance(action, str) or action not in MOVES or action in probabilities
                or probability is None or probability > 1):
            raise NativeSchemaError("Invalid or duplicate native probability option")
        probabilities[action] = probability
    return move, {"confidence": confidence, "probabilities": probabilities,
                  "provider_probabilities": values}


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


def preview():
    return {"kind": "direct_openai_luna_diagnostic_not_benchmark", "provider": "OpenAI",
            "endpoint": ENDPOINT, "model": MODEL, "policy_version": V4_POLICY_VERSION,
            "paid_calls_authorized": False, "request_cap": 2, "retries": 0,
            "cases": plan(1)["cases"]}


async def diagnose(*, confirm_paid=False, api_key=None, settings=None, transport=None):
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
        if cfg.budget - store.used() < 2:
            raise SystemExit("BLOCKED: fewer than two persistent requests remain; budget unchanged")
        report = {**preview(), "id": "openai-direct-diagnostic-" + uuid.uuid4().hex,
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
                    "policy_version": V4_POLICY_VERSION, "history_window": 6,
                    "model_visible_history": [], "moves_remaining": 30, "http_status": None,
                    "request_id": None, "latency_ms": None, "outcome": "PENDING",
                    "usage": None, "provider_usage": None, "billing": reported(None)}
                entry["requests"].append(record)
                requests.append(record)
                start = time.perf_counter()
                try:
                    response = await client.post(ENDPOINT, json=native_payload(case["initial_state"]),
                        headers={"Authorization": f"Bearer {key}"}, timeout=cfg.timeout)
                    record["latency_ms"] = (time.perf_counter() - start) * 1000
                    record.update(http_status=response.status_code,
                        request_id=safe_metadata(response.headers.get("x-request-id"), key))
                    try:
                        body = strict_json(response.text)
                    except (ValueError, TypeError):
                        body = None
                    if isinstance(body, dict):
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
                    billing=summarize(requests), planned_first_actions=2,
                    valid_first_actions=sum(r["status"] == "VALID_RESPONSE" for r in report["results"]),
                    correct_first_actions=sum(r["first_action_correct"] is True for r in report["results"]))
                directory = Path("data/direct-openai")
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / f"luna-v4-{now:%Y%m%dT%H%M%S%fZ}-{report['id'][-8:]}.json"
                with path.open("x", encoding="utf-8") as file:
                    json.dump(report, file, indent=2, allow_nan=False)
                print(json.dumps({"report": str(path), "provider": "OpenAI",
                    "request_count": len(requests), "correct_first_actions": report["correct_first_actions"],
                    "valid_first_actions": report["valid_first_actions"], "billing": report["billing"]}))
        finally:
            store.close()
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-paid", action="store_true",
                        help="Authorize at most two direct OpenAI requests; no retries or provider fallback")
    args = parser.parse_args(argv)
    if args.confirm_paid:
        asyncio.run(diagnose(confirm_paid=True))
    else:
        print(json.dumps(preview(), indent=2))


if __name__ == "__main__":
    main()
