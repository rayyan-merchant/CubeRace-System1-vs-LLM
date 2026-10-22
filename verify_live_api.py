"""Opt-in paid smoke test. Exactly one request maximum per assigned model; no retries."""
import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import httpx
from backend.config import Settings
from backend.models import MODELS, ModelFailure, Router
from backend.races import puzzle
from backend.store import Store


async def smoke():
    settings = replace(Settings.env(), retries=0)
    if not settings.key or not settings.allow_live or settings.mock_mode:
        raise SystemExit("BLOCKED: configure OPENROUTER_API_KEY, ALLOW_LIVE=true, OPENROUTER_MOCK_MODE=false")
    store = Store(settings.database)
    budget = {"used": 0, "cap": 4}
    state = puzzle(2026, "primary")["initial_state"]
    results = []
    async with httpx.AsyncClient() as client:
        router = Router(settings, store, client)
        for model in MODELS:
            records = []
            entry = {"model_id": model.id, "requests": records}
            try:
                entry["move"] = await router.decide(model, state, [], records, budget)
                entry["status"] = "VALID_RESPONSE"
            except ModelFailure as exc:
                entry.update(status=exc.status, error=str(exc))
            results.append(entry)
            print(f"{model.id}: {entry['status']}")
    report = {"mode": "live", "kind": "adapter_smoke_not_benchmark", "timestamp": datetime.now(timezone.utc).isoformat(),
              "source": "CubeRace: System-1 vs LLM", "seed": 2026, "metric": "HTM", "move_limit": 30,
              "initial_state": state, "results": results, "request_count": budget["used"]}
    Path("data").mkdir(exist_ok=True)
    Path("data/live-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    store.close()
    if not all(r["status"] == "VALID_RESPONSE" for r in results):
        raise SystemExit("PARTIAL: inspect data/live-smoke.json; no model substitutions were made")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-paid", action="store_true", required=True,
                        help="Authorize at most four paid requests, bounded by the persistent budget")
    parser.parse_args()
    asyncio.run(smoke())
