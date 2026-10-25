"""Diagnostic requests are intercepted; no external API calls."""
import importlib
import json
from pathlib import Path
import httpx
import pytest
from backend.config import Settings
from backend.cube import MOVES, SOLVED, apply
from backend.models import MODELS
from backend.store import Store


def diagnostic_module():
    assert importlib.util.find_spec("verify_cube_diagnostics"), "Missing opt-in cube diagnostic CLI"
    return importlib.import_module("verify_cube_diagnostics")


def test_preview_is_free_and_separates_depths(tmp_path, monkeypatch, capsys):
    module = diagnostic_module()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "Store", lambda *args: pytest.fail("Preview must not open a database"))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: pytest.fail("Preview must not use HTTP"))
    for depth in (1, 2):
        module.main(["--depth", str(depth)])
        plan = json.loads(capsys.readouterr().out)
        assert plan["depth"] == depth and plan["request_cap"] == 6
        assert plan["selected_models"] == [m.id for m in MODELS[:3]]
        assert plan["paid_calls_authorized"] is False
        assert len(plan["cases"]) == 2 and all(set(c) == {"id", "initial_state"} for c in plan["cases"])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize("outcome", ["correct", "wrong", "http_error", "wrong_model"])
async def test_exact_request_ceiling_scoring_and_no_solution_leak(tmp_path, monkeypatch, depth, outcome):
    module = diagnostic_module()
    monkeypatch.chdir(tmp_path)
    settings = Settings(database=str(tmp_path / "diagnostics.db"), key="private-offline-key",
                        allow_live=True, mock_mode=False, budget=12)
    seen = []
    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        assert body["model"] in {m.id for m in MODELS[:3]}
        assert body["state"]["recent_moves"] == [] and body["state"]["moves_remaining"] == 30
        assert set(body["state"]) == {"cube_facelets", "faces", "recent_moves", "moves_remaining"}
        assert set(body["questions"]["next_move"]["criteria"]) == set(MOVES)
        assert not any(word in json.dumps(body) for word in ("scramble", "solution", "correct_move", "BFS"))
        if outcome == "http_error":
            return httpx.Response(502)
        state = body["state"]["cube_facelets"]
        def correct(move):
            after = apply(state, move)
            return after == SOLVED if depth == 1 else any(apply(after, m) == SOLVED for m in MOVES)
        move = next(m for m in MOVES if correct(m)) if outcome == "correct" else "B"
        return httpx.Response(200, json={"model": "unrelated/model" if outcome == "wrong_model" else body["model"],
            "answers": {"next_move": {"type": "choice", "choice": move}},
            "usage": {"input_tokens": 20, "output_tokens": 2, "cost": 0.0001}})
    paths = []
    for _ in range(2):
        path = await module.diagnose(depth=depth, confirm_paid=True, settings=settings,
                                     transport=httpx.MockTransport(handler))
        report = json.loads(path.read_text())
        paths.append(path)
        assert report["request_count"] == (3 if outcome == "wrong_model" else 6)
        assert report["kind"] == "first_action_diagnostic_not_benchmark"
        assert len(report["results"]) == 6
        assert report["correct_first_actions"] == (6 if outcome == "correct" else 0)
        assert report["request_policy"]["retries"] == 0
        assert report["selected_models"] == [m.id for m in MODELS[:3]]
        if outcome == "wrong":
            assert all(r["move"] == "B" and r["first_action_correct"] is False for r in report["results"])
        if outcome in ("http_error", "wrong_model"):
            assert all(r["first_action_correct"] is None for r in report["results"])
        assert report["billing"]["unknown_cost_requests"] == (6 if outcome == "http_error" else 0)
        assert settings.key not in path.read_text()
    assert paths[0] != paths[1] and all(p.exists() for p in paths)
    store = Store(settings.database)
    assert store.used() == len(seen)
    assert store.all() == []  # Diagnostics must not enter benchmark/replay datasets.
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("block", ["consent", "budget", "retries", "active"])
async def test_diagnostics_block_before_paid_http(tmp_path, monkeypatch, block):
    module = diagnostic_module()
    monkeypatch.chdir(tmp_path)
    settings = Settings(database=str(tmp_path / "guard.db"), key="offline", allow_live=True,
                        mock_mode=False, budget=5 if block == "budget" else 6,
                        retries=1 if block == "retries" else 0)
    if block == "active":
        store = Store(settings.database)
        store.save({"id": "active", "status": "RUNNING"})
        store.close()
    with pytest.raises(SystemExit):
        await module.diagnose(confirm_paid=block != "consent", settings=settings,
            transport=httpx.MockTransport(lambda r: pytest.fail("Unexpected paid request")))
    if Path(settings.database).exists():
        store = Store(settings.database)
        assert store.used() == 0
        store.close()
