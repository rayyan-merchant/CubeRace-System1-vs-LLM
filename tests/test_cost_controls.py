"""Paid paths exercised only with HTTP fixtures. No network or real credentials."""
import json
from dataclasses import replace
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.billing import reported, summarize
from backend.config import Settings
from backend.cube import SOLVED
from backend.main import StartRequest, create_app
from backend.models import MODELS, Router, ModelFailure, payload
from backend.races import Manager
from backend.stats import aggregate
from backend.store import Store
from tests.test_models import response

USAGE = {"prompt_tokens": 120, "completion_tokens": 24, "total_tokens": 144,
         "completion_tokens_details": {"reasoning_tokens": 20}, "cost": 0.001}


def test_fixed_claude_settings_and_compact_fair_information():
    cfg = Settings()
    assert cfg.retries == 0 and cfg.claude_max_tokens == 512 and cfg.claude_reasoning_effort == "low"
    for effort in ("none", "minimal", "disabled"):
        with pytest.raises(ValueError):
            Settings(claude_reasoning_effort=effort)
    bodies = [payload(m, SOLVED, ["U", "R2"], cfg) for m in MODELS]
    chat = json.loads(bodies[3]["messages"][1]["content"])
    for body in bodies[:3]:
        assert body["state"] == chat["state"]
        assert body["questions"]["next_move"] == chat["question"]
        assert "usage" not in body  # No undocumented addition to typed Decisions request.
    assert "scramble" not in json.dumps(bodies)
    assert bodies[3]["reasoning"] == {"effort": "low"}
    assert bodies[3]["max_tokens"] == 512
    assert bodies[3]["usage"] == {"include": True}
    custom = payload(MODELS[3], SOLVED, [], replace(cfg, claude_reasoning_effort="medium", claude_max_tokens=768))
    assert custom["reasoning"] == {"effort": "medium"} and custom["max_tokens"] == 768


def test_usage_missing_zero_partial_and_reasoning():
    assert reported(USAGE)["reasoning_tokens"] == 20
    assert summarize([{ "usage": USAGE}])["total_cost_usd"] == 0.001
    assert summarize([{ "usage": {"cost": 0}}])["total_cost_usd"] == 0
    missing = summarize([{"usage": None}])
    assert missing["known_cost_usd"] is None and missing["total_cost_usd"] is None
    assert missing["unknown_cost_requests"] == 1
    partial = summarize([{"usage": USAGE}, {"usage": {}}])
    assert partial["known_cost_usd"] == 0.001 and partial["total_cost_usd"] is None
    assert partial["tokens"]["reasoning_tokens"] == {"known_total": 20, "unknown_requests": 1}
    assert reported({"cost": -1})["cost_usd"] is None
    assert reported({"cost": True})["cost_usd"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [502, 429])
async def test_zero_retry_accounts_http_failure_once(tmp_path, code):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(code, json={"usage": USAGE})
    store = Store(str(tmp_path / "billing.db"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = []
        with pytest.raises(ModelFailure):
            await Router(Settings(), store, client).decide(MODELS[0], SOLVED, [], records, {"used": 0, "cap": 10})
    assert len(seen) == store.used() == 1
    assert records[0]["billing"]["cost_usd"] == 0.001
    assert store.billing()["by_model"][MODELS[0].id]["total_cost_usd"] == 0.001
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,expected,attempted", [("permanent", 4, 1), ("schema", 8, 2),
                                                    ("illegal_move", 20, 5), ("transient", 20, 5)])
async def test_fail_fast_is_incompatibility_only(tmp_path, kind, expected, attempted):
    seen = []
    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        model = next(m for m in MODELS if m.id == body["model"])
        if kind == "permanent":
            return httpx.Response(404, json={"usage": USAGE})
        if kind == "schema":
            return httpx.Response(200, json={"usage": USAGE})
        if kind == "transient":
            return httpx.Response(503, json={"usage": USAGE})
        return httpx.Response(200, json=response(model, "X", usage=USAGE))
    cfg = Settings(database=str(tmp_path / "test.db"))
    store = Store(cfg.database)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        manager = Manager(cfg, store, client)
        run = await manager.start(StartRequest(mode="live", kind="suite", puzzles=5, call_cap=600))
        await manager.active[run["id"]]["task"]
    assert len(seen) == store.used() == expected
    stats = aggregate([run])
    assert all(r["attempted"] == attempted and r["planned"] == 5 for r in stats["rows"])
    assert all(r["not_run"] == 5 - attempted for r in stats["rows"])
    assert stats["billing"]["total_cost_usd"] == pytest.approx(expected * 0.001)
    assert run["evidence_status"] == "INCOMPLETE"
    store.close()


@pytest.mark.asyncio
async def test_four_call_smoke_then_600_cap_suite_and_read_only_demo(tmp_path, monkeypatch):
    import verify_live_api
    seen = []
    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        model = next(m for m in MODELS if m.id == body["model"])
        return httpx.Response(200, json=response(model, "R", usage=USAGE))
    transport = httpx.MockTransport(handler)
    cfg = Settings(key="offline-fixture", allow_live=True, mock_mode=False,
                   budget=604, database=str(tmp_path / "test.db"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Settings, "env", classmethod(lambda cls: cfg))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(verify_live_api.httpx, "AsyncClient", lambda: original_client(transport=transport))
    await verify_live_api.smoke()
    assert len(seen) == 4
    smoke = json.loads((tmp_path / "data/live-smoke.json").read_text())
    assert smoke["billing"]["total_cost_usd"] == 0.004
    # Restore the constructor; server itself receives the offline transport explicitly.
    monkeypatch.setattr(verify_live_api.httpx, "AsyncClient", original_client)
    with TestClient(create_app(cfg, transport)) as client:
        for body in ({"mode": "live", "call_cap": 600},
                     {"mode": "live", "confirm_paid_calls": True, "call_cap": 0}):
            assert client.post("/api/runs", json=body).status_code == 422
        assert len(seen) == 4
        started = client.post("/api/runs", json={"mode": "live", "kind": "suite", "puzzles": 5,
                                                "call_cap": 600, "confirm_paid_calls": True})
        assert started.status_code == 201
        from tests.test_application import wait_done
        run = wait_done(client, started.json()["id"])
        assert len(seen) == 604
        assert run["billing"]["total_cost_usd"] == pytest.approx(0.6)
        assert run["request_policy"]["claude_reasoning_effort"] == "low"
        assert all(len(t["moves"]) == 30 for p in run["races"] for t in p["trials"])
        for path in ("/", "/api/config", "/api/health", "/api/stats", "/api/runs",
                     f"/api/runs/{run['id']}", f"/api/runs/{run['id']}/events",
                     *(f"/api/runs/{run['id']}/export/{fmt}" for fmt in ("json", "csv", "steps.csv", "requests.csv"))):
            assert client.get(path).status_code == 200
        assert len(seen) == 604
        config = client.get("/api/config").json()
        assert config["budget_used"] == 604 and config["billing"]["total_cost_usd"] == pytest.approx(0.604)
        assert config["recommended_race_cap"] == 120
        assert all(b["reasoning"] == {"effort": "low"} and b["max_tokens"] == 512
                   for b in seen if b["model"] == MODELS[3].id)
        exhausted = client.post("/api/runs", json={"mode": "live", "call_cap": 120, "confirm_paid_calls": True})
        assert exhausted.status_code == 409 and len(seen) == 604
        stats = client.get("/api/stats").json()
        assert all(r["billing"]["total_cost_usd"] == pytest.approx(0.15) for r in stats["rows"])
        assert all(r["attempted"] == 0 for r in client.get("/api/stats?mode=simulated").json()["rows"])


def test_legacy_costs_unknown_and_policy_groups_not_mixed(tmp_path):
    store = Store(str(tmp_path / "legacy.db"))
    assert store.consume(10)
    store.close()
    store = Store(str(tmp_path / "legacy.db"))
    assert store.billing()["total_cost_usd"] is None
    assert store.billing()["unknown_cost_requests"] == 1
    assert store.used() == 1
    store.close()
    old = {"mode": "live", "kind": "suite", "tier": "primary", "puzzle_count": 5, "races": [],
           "policy_version": "old", "request_policy": {"chat_max_tokens": 2048}}
    new = {**old, "policy_version": "state-action-v2-compact", "request_policy": {"chat_max_tokens": 512}}
    stats = aggregate([new, old])
    assert stats["suite_count"] == 1 and stats["excluded_policy_suites"] == 1


@pytest.mark.asyncio
async def test_output_limit_preserves_billing_without_retry_or_quarantine(tmp_path):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"model": MODELS[3].id, "usage": USAGE,
            "choices": [{"finish_reason": "length", "message": {"content": ""}}]})
    store = Store(str(tmp_path / "limit.db"))
    failures = {}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = Router(Settings(retries=3), store, client)
        for _ in range(2):
            records = []
            with pytest.raises(ModelFailure) as error:
                await router.decide(MODELS[3], SOLVED, [], records, {"used": 0, "cap": 10}, failures)
            assert not error.value.permanent and len(records) == 1
            assert records[0]["finish_reason"] == "length"
            assert records[0]["billing"]["reasoning_tokens"] == 20
    assert len(calls) == 2
    assert all(c["max_tokens"] == 512 and c["reasoning"]["effort"] == "low" for c in calls)
    assert store.billing()["total_cost_usd"] == 0.002
    store.close()


@pytest.mark.asyncio
async def test_valid_envelope_bad_move_breaks_schema_failure_streak(tmp_path):
    bodies = iter([{}, response(MODELS[0], "X"), {}])
    store = Store(str(tmp_path / "schema.db"))
    failures = {}
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=next(bodies)))) as client:
        router = Router(Settings(), store, client)
        for _ in range(3):
            with pytest.raises(ModelFailure) as error:
                await router.decide(MODELS[0], SOLVED, [], [], {"used": 0, "cap": 10}, failures)
            assert not error.value.permanent
    assert store.used() == 3
    store.close()


def test_interrupted_request_remains_counted_and_unknown_in_its_run(tmp_path):
    path = str(tmp_path / "restart.db")
    store = Store(path)
    run = {"id": "interrupted-cost-test", "status": "RUNNING", "mode": "live", "tier": "primary",
           "kind": "suite", "puzzle_count": 5, "budget": {"used": 0, "cap": 600},
           "races": [{"trials": [{"model_id": MODELS[0].id, "status": "PENDING", "requests": [],
                                   "moves": [], "elapsed_ms": None, "optimality_gap": None}]}]}
    store.save(run)
    assert store.reserve(4, MODELS[0].id, run["id"], 0) is not None
    store.close()
    store = Store(path)
    store.recover()
    recovered = store.get(run["id"])
    assert recovered["races"][0]["trials"][0]["status"] == "ABORTED"
    assert len(recovered["races"][0]["trials"][0]["requests"]) == 1
    billing = store.run_billing(recovered)
    assert billing["request_count"] == 1 and billing["total_cost_usd"] is None
    assert billing["unknown_cost_requests"] == 1 and store.used() == 1
    assert recovered["budget"]["used"] == 1
    stats = aggregate([recovered])
    assert stats["rows"][0]["attempted"] == 1
    assert stats["rows"][0]["billing"]["unknown_cost_requests"] == 1
    assert stats["rows"][0]["avg_api_latency_ms"] is None
    store.close()
