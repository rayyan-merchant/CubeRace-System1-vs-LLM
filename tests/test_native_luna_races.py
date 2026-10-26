"""Production race/suite native Luna routing; all HTTP is intercepted."""

import json
from dataclasses import replace
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.models import MODELS, payload, request_policy
from backend.store import Store
from backend.stats import aggregate
from tests.test_application import wait_done
from tests.test_direct_openai import native_response
from tests.test_local_readiness import one_turn_fixture
from tests.test_models import response


def settings(tmp_path):
    return Settings(
        key="router-offline",
        openai_key="native-offline",
        luna_provider="openai",
        allow_live=True,
        mock_mode=False,
        database=str(tmp_path / "native-races.db"),
    )


def test_runtime_env_defaults_to_native_without_exposing_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("LUNA_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "native-offline")
    cfg = replace(Settings.env(), database=str(tmp_path / "config.db"))
    assert cfg.luna_provider == "openai" and cfg.openai_key == "native-offline"
    with TestClient(create_app(cfg)) as client:
        info = client.get("/api/config").json()
        assert info["luna_provider"] == "openai"
        assert "native-offline" not in json.dumps(info)
    with pytest.raises(ValueError):
        Settings(luna_provider="fallback")


@pytest.mark.parametrize("outcome", ["valid", "refused", "502", "wrong_id", "schema"])
def test_ui_native_route_exact_context_billing_and_read_only_replay(tmp_path, monkeypatch, outcome):
    monkeypatch.setattr("backend.races.puzzle", one_turn_fixture)
    cfg = settings(tmp_path)
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append((str(req.url), body))
        if req.url.host == "api.openai.com":
            assert (
                body["model"] == "gpt-6-luna"
                and req.headers["authorization"] == "Bearer native-offline"
            )
            baseline = payload(MODELS[1], one_turn_fixture(0, "primary")["initial_state"], [])
            assert body["input"][0]["content"][0]["data"] == baseline["state"]
            assert (
                body["questions"][0]["instructions"]
                == baseline["questions"]["next_move"]["instructions"]
            )
            assert body["questions"][0]["choices"] == [
                {"value": m, "description": d}
                for m, d in baseline["questions"]["next_move"]["criteria"].items()
            ]
            native = native_response()
            native["usage"]["output_tokens_details"]["reasoning_tokens"] = 7
            if outcome == "502":
                return httpx.Response(502, json={"error": {"message": "fixture"}})
            if outcome == "refused":
                native["answers"] = [{"type": "refusal", "name": "next_move"}]
            if outcome == "wrong_id":
                native["model"] = "other/model"
            if outcome == "schema":
                native["answers"] = {}
            return httpx.Response(200, json=native, headers={"x-request-id": "req-offline"})
        assert (
            req.url.host == "openrouter.ai"
            and req.headers["authorization"] == "Bearer router-offline"
        )
        assert body["model"] != MODELS[1].id
        m = next(m for m in MODELS if m.id == body["model"])
        return httpx.Response(200, json=response(m, "R'", usage={"cost": 0.001}))

    with TestClient(create_app(cfg, httpx.MockTransport(handler))) as client:
        assert client.post("/api/runs", json={"mode": "live", "call_cap": 120}).status_code == 422
        assert seen == []
        result = client.post(
            "/api/runs", json={"mode": "live", "confirm_paid_calls": True, "call_cap": 120}
        )
        run = wait_done(client, result.json()["id"])
        assert len(seen) == 4
        assert all(
            t["status"] == "SOLVED" for i, t in enumerate(run["races"][0]["trials"]) if i != 1
        )
        trial = run["races"][0]["trials"][1]
        record = trial["requests"][0]
        assert (
            record["api_provider"] == "OpenAI"
            and record["provider_route"] == "direct_openai_decisions"
        )
        assert (
            record["requested_model_id"] == MODELS[1].id
            and record["provider_requested_model_id"] == "gpt-6-luna"
        )
        assert (
            trial["status"]
            == (
                {
                    "valid": "SOLVED",
                    "refused": "REFUSED",
                    "502": "API_ERROR",
                    "wrong_id": "UNAVAILABLE",
                    "schema": "API_ERROR",
                }[outcome]
            )
        )
        assert trial["moves"] == (["R'"] if outcome == "valid" else [])
        assert run["request_policy"]["luna_route"]["provider"] == "OpenAI"
        if outcome != "502":
            assert (
                record["billing"]["reasoning_tokens"] == 7
                and record["billing"]["prompt_tokens"] == 100
            )
            assert record["billing"]["cost_usd"] is None
        assert run["billing"]["unknown_cost_requests"] == 1
        for path in (
            "/",
            "/api/health",
            "/api/config",
            "/api/stats",
            "/api/runs",
            f"/api/runs/{run['id']}/events",
            f"/api/runs/{run['id']}/export/requests.csv",
        ):
            assert client.get(path).status_code == 200
        assert len(seen) == 4
        old = {**run, "request_policy": request_policy(replace(cfg, luna_provider="openrouter"))}
        assert (
            aggregate([run, old])["excluded_policy_suites"] == 0
        )  # races never become suite evidence
        run["kind"] = old["kind"] = "suite"
        assert aggregate([run, old])["excluded_policy_suites"] == 1


def test_missing_native_key_blocks_before_any_paid_request(tmp_path):
    cfg = replace(settings(tmp_path), openai_key="")
    with TestClient(
        create_app(cfg, httpx.MockTransport(lambda r: pytest.fail("No HTTP allowed")))
    ) as client:
        assert not client.get("/api/config").json()["live_enabled"]
        assert (
            client.post(
                "/api/runs", json={"mode": "live", "confirm_paid_calls": True, "call_cap": 120}
            ).status_code
            == 409
        )
    store = Store(cfg.database)
    assert store.used() == 0
    store.close()


def test_native_full_30_actions_and_six_move_history_preserve_all_internal_moves(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("backend.races.puzzle", one_turn_fixture)
    cfg = settings(tmp_path)
    bodies = []

    def handler(req):
        body = json.loads(req.content)
        if req.url.host == "api.openai.com":
            bodies.append(body)
            return httpx.Response(200, json=native_response("U"))
        return httpx.Response(
            200, json=response(next(m for m in MODELS if m.id == body["model"]), "U")
        )

    with TestClient(create_app(cfg, httpx.MockTransport(handler))) as client:
        result = client.post(
            "/api/runs", json={"mode": "live", "confirm_paid_calls": True, "call_cap": 120}
        )
        run = wait_done(client, result.json()["id"])
        assert all(
            t["status"] == "MOVE_LIMIT" and len(t["moves"]) == 30 for t in run["races"][0]["trials"]
        )
        assert len(bodies) == 30 and run["budget"]["used"] == 120
        assert bodies[0]["input"][0]["content"][0]["data"]["recent_moves"] == []
        assert bodies[-1]["input"][0]["content"][0]["data"]["recent_moves"] == ["U"] * 6
        assert bodies[-1]["input"][0]["content"][0]["data"]["moves_remaining"] == 1


def test_three_puzzle_suite_sends_each_luna_trial_to_openai(tmp_path, monkeypatch):
    from backend.cube import SOLVED, sequence

    def puzzle(seed, tier):
        move = ("R", "F", "L")[seed % 3]
        return {
            "seed": seed,
            "tier": tier,
            "scramble": [move],
            "initial_state": sequence(SOLVED, [move]),
            "shortest_distance": 1,
            "proof_method": "offline fixture",
            "solution_upper_bound": 1,
        }

    monkeypatch.setattr("backend.races.puzzle", puzzle)
    seen = []

    def handler(req):
        seen.append((req.url.host, json.loads(req.content)["model"]))
        return httpx.Response(502, json={"error": {"message": "offline fixture"}})

    with TestClient(create_app(settings(tmp_path), httpx.MockTransport(handler))) as client:
        result = client.post(
            "/api/runs",
            json={
                "mode": "live",
                "kind": "suite",
                "puzzles": 3,
                "confirm_paid_calls": True,
                "call_cap": 120,
            },
        )
        run = wait_done(client, result.json()["id"])
        assert seen.count(("api.openai.com", "gpt-6-luna")) == 3
        assert len(seen) == 12 and all(model != MODELS[1].id for _, model in seen)
        assert all(r["trials"][1]["requests"][0]["api_provider"] == "OpenAI" for r in run["races"])


@pytest.mark.asyncio
async def test_native_abort_persists_charged_attempt_without_fallback(tmp_path):
    import asyncio
    from backend.models import Router

    cfg = settings(tmp_path)
    store = Store(cfg.database)
    calls = []

    async def handler(req):
        calls.append(req.url.host)
        raise asyncio.CancelledError

    records = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(asyncio.CancelledError):
            await Router(cfg, store, client).decide(
                MODELS[1],
                one_turn_fixture(0, "primary")["initial_state"],
                [],
                records,
                {"used": 0, "cap": 1},
            )
    assert calls == ["api.openai.com"] and store.used() == 1
    assert records[0]["outcome"] == "CANCELLED" and records[0]["billing"]["cost_usd"] is None
    store.close()
