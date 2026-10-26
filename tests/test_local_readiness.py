"""Exact UI routes with intercepted HTTP and read-only runtime preflight checks."""
import asyncio
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import threading
import httpx
import pytest
from fastapi.testclient import TestClient
import preflight
from backend.config import Settings
from backend.cube import SOLVED, sequence
from backend.main import create_app
from backend.models import MODELS, POLICY_VERSION
from tests.test_application import wait_done
from tests.test_models import response

EFFECTIVE = {**{m.id: m.id for m in MODELS},
             MODELS[0].id: "typesafe/jev-1.13-20260917",
             MODELS[1].id: "openai/gpt-6-luna-decisions-20261006"}
USAGE = {"input_tokens": 12, "output_tokens": 2, "cost": 0.0001}


def config(tmp_path):
    return Settings(key="offline-fixture-not-a-real-key", allow_live=True, mock_mode=False,
                    database=str(tmp_path / "local.db"))


def one_turn_fixture(seed, tier):
    return {"seed": seed, "tier": tier, "scramble": ["R"],
            "initial_state": sequence(SOLVED, ["R"]), "shortest_distance": 1,
            "proof_method": "offline one-turn fixture", "solution_upper_bound": 1}


def db_rows(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        return {t: db.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()
                for t in ("budget", "runs", "requests")}


@pytest.mark.parametrize("wrong_identity", [False, True])
def test_ui_start_identity_completion_billing_and_read_only_replay(tmp_path, monkeypatch, wrong_identity):
    import backend.races
    monkeypatch.setattr(backend.races, "puzzle", one_turn_fixture)
    settings = config(tmp_path)
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        model = next(m for m in MODELS if m.id == body["model"])
        return httpx.Response(200, json={**response(model, "R'", usage=USAGE),
            "model": "unrelated/model" if wrong_identity else EFFECTIVE[model.id]})
    with TestClient(create_app(settings, httpx.MockTransport(handler))) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/health").json()["runtime"]["policy_version"] == POLICY_VERSION
        assert calls == []
        started = client.post("/api/runs", json={"mode": "live", "confirm_paid_calls": True, "call_cap": 120})
        assert started.status_code == 201
        run = wait_done(client, started.json()["id"])
        assert run["status"] == "COMPLETED" and len(calls) == 4
        assert {b["model"] for b in calls} == {m.id for m in MODELS}
        assert all(b["max_tokens"] == 2048 for b in calls if "max_tokens" in b)
        assert run["billing"]["total_cost_usd"] == 0.0004
        for t in run["races"][0]["trials"]:
            assert t["status"] == ("UNAVAILABLE" if wrong_identity else "SOLVED")
            assert t["moves"] == ([] if wrong_identity else ["R'"])
            assert t["requests"][0]["requested_model_id"] == t["model_id"]
            assert t["requests"][0]["effective_model_id"] == ("unrelated/model" if wrong_identity else EFFECTIVE[t["model_id"]])
        before = db_rows(settings.database)
        for url in ("/", "/api/config", "/api/health", "/api/runs", "/api/stats",
                    f"/api/runs/{run['id']}", f"/api/runs/{run['id']}/events",
                    *(f"/api/runs/{run['id']}/export/{fmt}" for fmt in ("json", "csv", "steps.csv", "requests.csv"))):
            assert client.get(url).status_code == 200
        assert len(calls) == 4 and db_rows(settings.database) == before
        stream = client.get(f"/api/runs/{run['id']}/events").text
        assert stream.count("event: model_finished") == 4 and "event: run_finished" in stream
        assert json.dumps(settings.key) not in client.get("/api/health").text


def test_ui_abort_keeps_valid_moves_cancelled_requests_and_unknown_costs(tmp_path, monkeypatch):
    import backend.races
    monkeypatch.setattr(backend.races, "puzzle", one_turn_fixture)
    settings = config(tmp_path)
    calls = Counter()
    all_pending = threading.Event()
    async def handler(request):
        body = json.loads(request.content)
        model = next(m for m in MODELS if m.id == body["model"])
        calls[model.id] += 1
        if calls[model.id] == 1:
            return httpx.Response(200, json={**response(model, "U", usage=USAGE), "model": EFFECTIVE[model.id]})
        if all(calls[m.id] == 2 for m in MODELS):
            all_pending.set()
        await asyncio.sleep(60)  # Cancelled by Abort; no network, sleeps do not finish normally.
        raise AssertionError("Abort should cancel each pending fixture")
    with TestClient(create_app(settings, httpx.MockTransport(handler))) as client:
        run_id = client.post("/api/runs", json={"mode": "live", "confirm_paid_calls": True, "call_cap": 120}).json()["id"]
        assert all_pending.wait(5)
        assert client.post(f"/api/runs/{run_id}/abort").json()["status"] == "ABORTED"
        run = client.get(f"/api/runs/{run_id}").json()
        assert run["billing"]["request_count"] == 8
        assert run["billing"]["known_cost_usd"] == 0.0004
        assert run["billing"]["unknown_cost_requests"] == 4 and run["billing"]["total_cost_usd"] is None
        assert all(t["status"] == "ABORTED" and t["moves"] == ["U"] for t in run["races"][0]["trials"])
        assert all(t["requests"][-1]["outcome"] == "CANCELLED" for t in run["races"][0]["trials"])
        assert client.get("/api/config").json()["budget_used"] == 8
        assert client.get(f"/api/runs/{run_id}/events").status_code == 200
        assert sum(calls.values()) == 8


def test_preflight_is_read_only_and_reports_current_startup_identity(tmp_path):
    settings = config(tmp_path)
    def forbidden(request):
        raise AssertionError("Preflight must not invoke inference")
    with TestClient(create_app(settings, httpx.MockTransport(forbidden))) as client:
        before = db_rows(settings.database)
        report = preflight.check(client=client, settings=settings)
        assert report["local_runtime_ready"] and all(report["checks"].values())
        assert report["inference_requests"] == 0
        assert report["persistent_requests_remaining"] == settings.budget
        assert report["server_runtime"]["pid"]
        assert report["server_runtime"]["git_commit"] == report["local_runtime"]["git_commit"]
        assert db_rows(settings.database) == before
        assert settings.key not in json.dumps(report)


@pytest.mark.parametrize("field,value", [("runtime", None), ("git_commit", "old"),
    ("source_sha256", {}), ("policy_version", "state-action-v2-compact"),
    ("allowed_effective_ids", {}), ("python", "wrong-python"), ("working_directory", "wrong-cwd"),
    ("database", "wrong-database.db")])
def test_preflight_rejects_stale_runtime_even_when_health_is_ok(tmp_path, field, value):
    settings = config(tmp_path)
    with TestClient(create_app(settings)) as real:
        health = real.get("/api/health").json()
        cfg = real.get("/api/config").json()
        if field == "runtime":
            health.pop("runtime")
        else:
            health["runtime"][field] = value
        def handler(request):
            assert request.method == "GET" and request.url.host == "127.0.0.1"
            if request.url.path == "/":
                return httpx.Response(200, text="Rayyan Merchant · 23K-0073")
            return httpx.Response(200, json=health if request.url.path == "/api/health" else cfg)
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            report = preflight.check(client=client, settings=settings)
        assert not report["local_runtime_ready"]
        assert report["checks"]["server_health"] and report["checks"]["student_identity"]
        check_name = {"runtime": "git_commit", "database": "database_path"}.get(field, field)
        assert not report["checks"]["server_" + check_name]


@pytest.mark.parametrize("overrides", [{"claude_max_tokens": 512}, {"retries": 1},
    {"allow_live": False}, {"mock_mode": True}, {"budget": 0}])
def test_preflight_rejects_wrong_configuration_or_exhausted_budget(tmp_path, overrides):
    settings = replace(config(tmp_path), **overrides)
    with TestClient(create_app(settings)) as client:
        assert not preflight.check(client=client, settings=settings)["local_runtime_ready"]


def test_preflight_warns_about_insufficient_suite_capacity_without_increasing_budget(tmp_path):
    settings = replace(config(tmp_path), budget=589)
    with TestClient(create_app(settings)) as client:
        report = preflight.check(client=client, settings=settings)
        assert report["local_runtime_ready"]
        assert not report["five_puzzle_worst_case_covered"]
        assert report["persistent_budget_limit"] == 589


@pytest.mark.parametrize("url", ["https://openrouter.ai", "http://example.com", "http://127.0.0.1@evil.com",
    "http://localhost/api/runs", "http://localhost?x=1", "http://localhost:bad", "http://localhost:0"])
def test_preflight_refuses_nonlocal_or_ambiguous_urls(url):
    with pytest.raises(ValueError):
        preflight.check(url)


def test_health_runtime_is_a_startup_snapshot(tmp_path, monkeypatch):
    import backend.models
    app = create_app(config(tmp_path))
    monkeypatch.setattr(backend.models, "POLICY_VERSION", "changed-after-startup")
    with TestClient(app) as client:
        assert client.get("/api/health").json()["runtime"]["policy_version"] == POLICY_VERSION
