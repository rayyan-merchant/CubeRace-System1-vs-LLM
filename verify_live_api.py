"""Opt-in paid smoke test: at most one request per selected assigned model, no retries."""
import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
import httpx
from backend.config import Settings
from backend.models import MODELS, ModelFailure, Router, POLICY_VERSION, request_policy
from backend.races import puzzle
from backend.store import Store
from backend.billing import summarize, reported

MODEL_NAMES = dict(zip(("jev", "luna", "clef", "claude"), MODELS))


def select_models(value):
    names = {**MODEL_NAMES, **{m.id: m for m in MODELS}}
    selected = []
    for name in value.split(","):
        model = names.get(name.strip())
        if model is None or model in selected:
            raise argparse.ArgumentTypeError("Use unique models: jev,luna,clef,claude (or assigned full IDs)")
        selected.append(model)
    return tuple(selected)


async def smoke(models=MODELS, *, confirm_paid=False, settings=None):
    if not confirm_paid:
        raise SystemExit("BLOCKED: explicit --confirm-paid is required")
    models = tuple(models)
    if not models or len(set(models)) != len(models) or any(m not in MODELS for m in models):
        raise SystemExit("BLOCKED: select unique assigned models only")
    settings = replace(settings or Settings.env(), retries=0)
    if not settings.key or not settings.allow_live or settings.mock_mode:
        raise SystemExit("BLOCKED: configure OPENROUTER_API_KEY, ALLOW_LIVE=true, OPENROUTER_MOCK_MODE=false")
    store = Store(settings.database)
    budget = {"used": 0, "cap": len(models)}
    results = []
    try:
        state = puzzle(2026, "primary")["initial_state"]
        async with httpx.AsyncClient() as client:
            router = Router(settings, store, client)
            for model in models:
                records = []
                entry = {"model_id": model.id, "requests": records}
                try:
                    entry["move"] = await router.decide(model, state, [], records, budget)
                    entry["status"] = "VALID_RESPONSE"
                except ModelFailure as exc:
                    outcome = records[-1]["outcome"] if records else exc.status
                    entry.update(status="OUTPUT_LIMIT" if outcome == "OUTPUT_LIMIT" else exc.status,
                                 error=str(exc))
                results.append(entry)
                last = records[-1] if records else {}
                print(json.dumps({"requested_model_id": model.id,
                    "effective_model_id": last.get("effective_model_id"), "status": entry["status"],
                    "outcome": last.get("outcome", entry["status"]), "http_status": last.get("http_status"),
                    "finish_reason": last.get("finish_reason"), "usage": last.get("usage"),
                    "billing": reported(last.get("usage"))}))
        now = datetime.now(timezone.utc)
        report = {"mode": "live", "kind": "adapter_smoke_not_benchmark", "timestamp": now.isoformat(),
                  "source": "CubeRace: System-1 vs LLM", "seed": 2026, "metric": "HTM", "move_limit": 30,
                  "policy_version": POLICY_VERSION, "request_policy": request_policy(settings),
                  "selected_models": [m.id for m in models], "request_cap": len(models),
                  "billing": {**summarize(q for r in results for q in r["requests"]),
                              "by_model": {r["model_id"]: summarize(r["requests"]) for r in results}},
                  "initial_state": state, "results": results, "request_count": budget["used"]}
        directory = Path("data")
        directory.mkdir(exist_ok=True)
        path = directory / f"live-smoke-{now:%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json"
        with path.open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2)
        print(f"Report: {path}")
        if not all(r["status"] == "VALID_RESPONSE" for r in results):
            raise SystemExit(f"PARTIAL: inspect {path}; no model substitutions were made")
        return path
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=select_models, default=MODELS,
                        help="Comma-separated jev,luna,clef,claude; defaults to all four")
    parser.add_argument("--confirm-paid", action="store_true", required=True,
                        help="Authorize at most one request per selected model within the persistent budget")
    args = parser.parse_args(argv)
    asyncio.run(smoke(args.models, confirm_paid=args.confirm_paid))


if __name__ == "__main__":
    main()
