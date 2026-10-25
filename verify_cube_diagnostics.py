"""Preview two diagnostic states for free; --confirm-paid authorizes at most six calls."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
import httpx
from backend.billing import summarize
from backend.config import Settings
from backend.cube import SOLVED, MOVES, apply, sequence
from backend.models import MODELS, POLICY_VERSION, Router, ModelFailure, request_policy
from backend.store import Store

# Observer-only fixtures. Neither these sequences nor scoring data enter model payloads.
SCRAMBLES = {1: (("R",), ("U'",)), 2: (("R", "U"), ("F2", "L'"))}
DECISION_MODELS = MODELS[:3]


def plan(depth=1):
    if depth not in SCRAMBLES:
        raise ValueError("Diagnostic depth must be 1 or 2")
    return {"kind": "first_action_diagnostic_not_benchmark", "depth": depth,
            "policy_version": POLICY_VERSION, "paid_calls_authorized": False,
            "selected_models": [m.id for m in DECISION_MODELS], "request_cap": 6,
            "cases": [{"id": f"depth{depth}-case{i + 1}",
                       "initial_state": sequence(SOLVED, moves)}
                      for i, moves in enumerate(SCRAMBLES[depth])]}


def first_action_correct(state, move, depth):
    """Post-response observer scoring only; never used by Router or live policy."""
    after = apply(state, move)
    return after == SOLVED if depth == 1 else any(apply(after, m) == SOLVED for m in MOVES)


async def diagnose(*, depth=1, confirm_paid=False, settings=None, transport=None):
    if not confirm_paid:
        raise SystemExit("BLOCKED: explicit --confirm-paid is required")
    report = plan(depth)
    settings = settings or Settings.env()
    if not settings.key or not settings.allow_live or settings.mock_mode:
        raise SystemExit("BLOCKED: configure server-side key, ALLOW_LIVE=true, OPENROUTER_MOCK_MODE=false")
    if settings.retries != 0:
        raise SystemExit("BLOCKED: diagnostics require API_RETRIES=0; no configuration was changed")
    store = Store(settings.database)
    try:
        if any(r["status"] == "RUNNING" for r in store.all()):
            raise SystemExit("BLOCKED: an existing run is active; no diagnostic calls made")
        if settings.budget - store.used() < report["request_cap"]:
            raise SystemExit("BLOCKED: fewer than six persistent requests remain; budget was not changed")
        report.update(id="diagnostic-" + uuid.uuid4().hex, mode="live", paid_calls_authorized=True,
                      source="CubeRace: System-1 vs LLM", move_limit=30, metric="HTM",
                      request_policy=request_policy(settings), results=[])
        budget = {"used": 0, "cap": 6, "run_id": report["id"]}
        blocked, schema_failures = {}, {}
        async with httpx.AsyncClient(transport=transport) as client:
            router = Router(settings, store, client)
            for index, case in enumerate(report["cases"]):
                budget["race_index"] = index
                for model in DECISION_MODELS:
                    entry = {"case_id": case["id"], "model_id": model.id, "requests": [],
                             "first_action_correct": None}
                    if model.id in blocked:
                        entry.update(status="NOT_RUN", error=blocked[model.id])
                    else:
                        try:
                            move = await router.decide(model, case["initial_state"], [],
                                entry["requests"], budget, schema_failures)
                            # Score only the returned action; do not correct it or request another.
                            entry.update(status="VALID_RESPONSE", move=move,
                                first_action_correct=first_action_correct(case["initial_state"], move, depth))
                        except ModelFailure as exc:
                            entry.update(status=exc.status, error=str(exc))
                            if exc.permanent:
                                blocked[model.id] = str(exc)
                    report["results"].append(entry)
        requests = [q for entry in report["results"] for q in entry["requests"]]
        now = datetime.now(timezone.utc)
        report.update(timestamp=now.isoformat(), request_count=budget["used"],
                      correct_first_actions=sum(r["first_action_correct"] is True for r in report["results"]),
                      valid_first_actions=sum(r["status"] == "VALID_RESPONSE" for r in report["results"]),
                      planned_first_actions=6,
                      billing={**summarize(requests), "by_model": {
                          m.id: summarize(q for r in report["results"] if r["model_id"] == m.id
                                          for q in r["requests"]) for m in DECISION_MODELS}})
        directory = Path("data")
        directory.mkdir(exist_ok=True)
        path = directory / f"cube-diagnostic-depth{depth}-{now:%Y%m%dT%H%M%S%fZ}-{report['id'][-8:]}.json"
        with path.open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2)
        print(json.dumps({"report": str(path), "request_count": report["request_count"],
                          "correct_first_actions": report["correct_first_actions"],
                          "valid_first_actions": report["valid_first_actions"],
                          "planned_first_actions": 6, "billing": report["billing"]}))
        return path
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, choices=(1, 2), default=1,
                        help="1: one-move cases; 2: separate optional two-move cases; six calls each")
    parser.add_argument("--confirm-paid", action="store_true",
                        help="Explicitly authorize at most six Decisions calls, never Claude or retries")
    args = parser.parse_args(argv)
    if args.confirm_paid:
        asyncio.run(diagnose(depth=args.depth, confirm_paid=True))
    else:
        print(json.dumps(plan(args.depth), indent=2))


if __name__ == "__main__":
    main()
