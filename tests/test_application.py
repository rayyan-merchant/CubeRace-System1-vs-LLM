import time
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.cube import SOLVED, sequence, shortest_path
from backend.main import create_app, StartRequest
from backend.models import MODELS
from backend.races import Manager, puzzle
from backend.stats import aggregate
from backend.store import Store
from tests.test_models import response


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(database=str(tmp_path / "test.db")))) as client:
        yield client


def wait_done(client, run_id):
    for _ in range(250):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "RUNNING":
            return run
        time.sleep(0.02)
    pytest.fail("Run timed out")


def test_read_endpoints_no_side_effects_or_secrets(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"
    config = client.get("/api/config").json()
    assert config["default_mode"] == "simulated" and not config["live_enabled"]
    assert not config["identity_configured"]
    assert "key" not in config
    stats = client.get("/api/stats").json()
    assert stats["suite_count"] == 0
    assert all(r["solve_rate"] is None for r in stats["rows"])
    assert client.get("/api/runs").json() == []
    assert client.post("/api/config", json={"key": "x"}).status_code == 405


def test_full_five_puzzle_suite_sse_and_exports(client):
    res = client.post("/api/runs", json={"kind": "suite", "puzzles": 5, "seed": 2026})
    assert res.status_code == 201
    run = wait_done(client, res.json()["id"])
    assert run["status"] == "COMPLETED" and run["mode"] == "simulated"
    assert len(run["races"]) == 5
    assert len({p["initial_state"] for p in run["races"]}) == 5
    assert run["evidence_status"] == "SIMULATED_ONLY"
    assert run["budget"]["used"] == 0
    for p in run["races"]:
        assert p["shortest_distance"] <= len(p["scramble"])
        for trial in p["trials"]:
            assert len(trial["moves"]) <= 30
            assert sequence(p["initial_state"], trial["moves"]) == trial["state"]
            assert trial["effective_agent_id"].startswith("synthetic-")
            assert trial["requests"] == []
            assert (trial["status"] == "SOLVED") == (trial["state"] == SOLVED)
            assert trial["elapsed_ms"] > 0
    sse = client.get(f"/api/runs/{run['id']}/events").text
    assert "event: race_started" in sse and "event: run_finished" in sse
    assert sse.count("event: model_finished") == 20
    cursor = run["events"][-1]["id"]
    assert client.get(f"/api/runs/{run['id']}/events", headers={"Last-Event-ID": str(cursor)}).text == ""
    for fmt in ("json", "csv", "steps.csv", "requests.csv"):
        exported = client.get(f"/api/runs/{run['id']}/export/{fmt}")
        assert exported.status_code == 200
        assert "attachment" in exported.headers["content-disposition"]
    assert all(r["attempted"] == 0 for r in client.get("/api/stats").json()["rows"])
    simulated = client.get("/api/stats?mode=simulated").json()
    assert all(r["attempted"] == 5 and r["avg_api_latency_ms"] is None for r in simulated["rows"])
    assert all("not evidence" in a for a in simulated["analysis"])


def test_explicit_live_gate_and_input_validation(client):
    assert client.post("/api/runs", json={"mode": "live", "confirm_paid_calls": True, "call_cap": 4}).status_code == 409
    for body in ({"max_moves": 60}, {"kind": "suite", "puzzles": 0}, {"kind": "suite", "puzzles": 26}, {"puzzles": 2},
                 {"tier": "unknown"}, {"seed": -1}, {"mode": "mock"}):
        assert client.post("/api/runs", json=body).status_code == 422
    assert client.get("/api/runs/not-real").status_code == 404
    assert client.post("/api/runs", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/config", headers={"Host": "evil.example"}).status_code == 403


def test_abort_and_run_isolation(client):
    a = client.post("/api/runs", json={"tier": "extension"}).json()["id"]
    assert client.post("/api/runs", json={}).status_code == 409
    assert client.post(f"/api/runs/{a}/abort").status_code == 200
    old = wait_done(client, a)
    assert old["status"] == "ABORTED"
    assert all(t["status"] != "RUNNING" for p in old["races"] for t in p["trials"])
    b = client.post("/api/runs", json={"seed": 13}).json()["id"]
    assert b != a
    wait_done(client, b)
    assert client.get(f"/api/runs/{a}").json() == old


def test_extension_no_guessed_distance(client):
    p = client.get("/api/puzzle?tier=extension&seed=8").json()
    assert p["shortest_distance"] is None and p["proof_method"] is None
    assert 15 <= len(p["scramble"]) <= 20


@pytest.mark.asyncio
async def test_real_adapter_orchestration_move_cap_and_empty_initial_history(tmp_path):
    seen = []
    def handler(request):
        import json
        body = json.loads(request.content)
        model = next(m for m in MODELS if m.id == body["model"])
        context = body.get("state") or json.loads(body["messages"][1]["content"])["state"]
        seen.append((model.id, context))
        effective = {MODELS[0].id: "typesafe/jev-1.13-20260917",
                     MODELS[1].id: "openai/gpt-6-luna-decisions-20261006"}.get(model.id, model.id)
        return httpx.Response(200, json={**response(model, "R"), "model": effective})
    cfg = Settings(key="test", allow_live=True, mock_mode=False, database=str(tmp_path / "test.db"))
    store = Store(cfg.database)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        manager = Manager(cfg, store, client)
        run = await manager.start(StartRequest(mode="live", call_cap=120, confirm_paid_calls=True))
        await manager.active[run["id"]]["task"]
    assert all(t["status"] == "MOVE_LIMIT" and len(t["moves"]) == 30 for t in run["races"][0]["trials"])
    for model in MODELS:
        contexts = [c for m, c in seen if m == model.id]
        assert contexts[0]["recent_moves"] == []
        assert contexts[-1]["recent_moves"] == ["R"] * 6
        assert all("scramble" not in c for c in contexts)
        assert [c["moves_remaining"] for c in contexts] == list(range(30, 0, -1))
    assert run["request_policy"]["history_window"] == 6
    for trial in store.get(run["id"])["races"][0]["trials"]:
        assert trial["moves"] == ["R"] * 30
        assert len(trial["steps"]) == 30
        assert trial["requests"][-1]["model_visible_history"] == ["R"] * 6
        assert trial["requests"][-1]["moves_remaining"] == 1
    assert store.used() == 120
    store.close()


def test_stats_denominators_and_missing_optimum():
    p = puzzle(2026, "primary")
    path = shortest_path(p["initial_state"])
    trials = []
    for i, status in enumerate(("SOLVED", "UNAVAILABLE", "NOT_RUN", "MOVE_LIMIT")):
        trials.append({"model_id": MODELS[i].id, "status": status, "requests": [],
                       "moves": list(path) if status == "SOLVED" else [],
                       "elapsed_ms": 42, "optimality_gap": 0 if status == "SOLVED" else None})
    run = {"mode": "live", "kind": "suite", "tier": "primary", "puzzle_count": 1,
           "races": [{"trials": trials}]}
    rows = aggregate([run])["rows"]
    assert rows[0]["solve_rate"] == 100 and rows[0]["mean_optimality_gap"] == 0
    assert rows[1]["solve_rate"] == 0 and rows[1]["attempted"] == 1
    assert rows[2]["solve_rate"] is None and rows[2]["attempted"] == 0
    assert rows[3]["mean_optimality_gap"] is None


def test_restart_recovery(tmp_path):
    path = str(tmp_path / "test.db")
    store = Store(path)
    store.save({"id": "x", "status": "RUNNING", "races": [{"trials": [{"status": "RUNNING"}]}]})
    store.close()
    store = Store(path)
    store.recover()
    assert store.get("x")["status"] == "INTERRUPTED"
    assert store.get("x")["races"][0]["trials"][0]["status"] == "ABORTED"
    store.close()

@pytest.mark.parametrize('count', [1, 3, 4])
def test_small_suite_runs_with_actual_puzzle_count(client, count):
    result = client.post('/api/runs', json={'kind': 'suite', 'puzzles': count, 'seed': 2026})
    assert result.status_code == 201
    run = wait_done(client, result.json()['id'])
    assert run['status'] == 'COMPLETED'
    assert run['puzzle_count'] == count and len(run['races']) == count
    assert all(len(r['trials']) == 4 for r in run['races'])
    stats = client.get('/api/stats?mode=simulated').json()
    assert all(row['planned'] == count for row in stats['rows'])


def test_three_puzzle_live_suite_accepts_user_request_with_mocked_provider(tmp_path):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(502, json={'error': {'message': 'Offline gateway fixture'}})
    cfg = Settings(database=str(tmp_path / 'three.db'), allow_live=True, mock_mode=False, key='offline')
    with TestClient(create_app(cfg, httpx.MockTransport(handler))) as client:
        result = client.post('/api/runs', json={'mode': 'live', 'kind': 'suite', 'puzzles': 3,
            'tier': 'primary', 'seed': 2026, 'call_cap': 120, 'confirm_paid_calls': True})
        assert result.status_code == 201
        run = wait_done(client, result.json()['id'])
        assert len(run['races']) == 3 and run['puzzle_count'] == 3
        assert len(seen) == 12
        assert all(len(r['trials']) == 4 for r in run['races'])
        assert run['budget']['used'] == 12
        assert all(t['status'] == 'API_ERROR' for r in run['races'] for t in r['trials'])

@pytest.mark.parametrize('solves', [0, 1])
def test_three_puzzle_live_analysis_answers_all_questions_without_minimum_gate(solves):
    trials = []
    for model_index, model in enumerate(MODELS):
        for index in range(3):
            solved = model_index == 0 and index < solves
            trials.append({'model_id': model.id, 'status': 'SOLVED' if solved else 'MOVE_LIMIT',
                'moves': ['R'] if solved else ['U'] * 30, 'elapsed_ms': 1000,
                'optimality_gap': 0 if solved else None,
                'requests': [{'outcome': 'VALID', 'retry': 0, 'latency_ms': 10 + model_index, 'usage': None}]})
    run = {'mode': 'live', 'kind': 'suite', 'tier': 'primary', 'puzzle_count': 3,
           'races': [{'trials': trials}]}
    stats = aggregate([run])
    assert all(row['attempted'] == 3 for row in stats['rows'])
    answers = stats['analysis']
    assert len(answers) == 5 and all('Insufficient live measured' not in a for a in answers)
    assert '3 attempted trials per model' in answers[1] and 'Small sample' in answers[1]
    if solves:
        assert '33.3%' in answers[1] and 'Fewest mean solved moves' in answers[2]
        assert 'provisionally choose' in answers[4]
    else:
        assert '0.0%' in answers[1] and 'No solved trials' in answers[2]
        assert 'No evaluated model solved' in answers[4]
    assert all('not evidence' in a for a in aggregate([{**run, 'mode': 'simulated'}], mode='simulated')['analysis'])


def test_empty_and_partial_analysis_do_not_invent_missing_results():
    assert all('Insufficient' in a for a in aggregate([])['analysis'])
    trials = [{'model_id': m.id, 'status': 'NOT_RUN', 'moves': [], 'elapsed_ms': None,
               'optimality_gap': None, 'requests': []} for m in MODELS]
    trials[0].update(status='API_ERROR', elapsed_ms=100,
        requests=[{'outcome': 'HTTP_ERROR', 'retry': 0, 'latency_ms': 100, 'usage': None}])
    stats = aggregate([{'mode': 'live', 'kind': 'suite', 'tier': 'primary', 'puzzle_count': 3,
                        'races': [{'trials': trials}]}])
    assert stats['rows'][1]['solve_rate'] is None
    assert '0\u20131 attempted trials per model' in stats['analysis'][1]
    assert MODELS[1].label not in stats['analysis'][1]
    assert 'missing trials' in stats['analysis'][1]
