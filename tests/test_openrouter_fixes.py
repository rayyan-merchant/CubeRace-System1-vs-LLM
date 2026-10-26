"""User-reported paid response shapes reproduced offline, never real inference."""
import argparse
import json
from dataclasses import replace
import httpx
import pytest
import verify_live_api
from backend.billing import reported, summarize
from backend.config import Settings
from backend.cube import SOLVED, MOVES
from backend.models import MODELS, ALLOWED_EFFECTIVE_IDS, Router, ModelFailure, payload
from backend.stats import aggregate
from backend.store import Store
from tests.test_models import response


@pytest.mark.asyncio
@pytest.mark.parametrize("model,effective", [(m, e) for m in MODELS for e in sorted(ALLOWED_EFFECTIVE_IDS[m.id])])
async def test_explicit_effective_id_acceptance(tmp_path, model, effective):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={**response(model), "model": effective})
    store = Store(str(tmp_path / "ids.db"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = []
        assert await Router(Settings(), store, client).decide(
            model, SOLVED, [], records, {"used": 0, "cap": 1}) == "R"
    assert len(seen) == 1 and seen[0]["model"] == model.id
    assert records[0]["requested_model_id"] == model.id
    assert records[0]["effective_model_id"] == effective
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("effective", ["unrelated/model", "typesafe/jev-1.13-20990101", "", None, ["bad"]])
async def test_unrecognized_effective_identity_fails_closed(tmp_path, model, effective):
    store = Store(str(tmp_path / "reject.db"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(
            200, json={**response(model), "model": effective}))) as client:
        records = []
        with pytest.raises(ModelFailure) as exc:
            await Router(Settings(retries=3), store, client).decide(
                model, SOLVED, [], records, {"used": 0, "cap": 4})
        assert exc.value.permanent and exc.value.status == "UNAVAILABLE"
        assert len(records) == store.used() == 1
    store.close()


@pytest.mark.parametrize("length", [0, 1, 6, 7, 29])
def test_history_window_is_identical_without_mutating_internal_history(length):
    history = (list(MOVES) * 2)[:length]
    original = history.copy()
    bodies = [payload(m, SOLVED, history) for m in MODELS]
    chat = json.loads(bodies[-1]["messages"][1]["content"])
    for body in bodies[:3]:
        assert body["state"] == chat["state"]
        assert body["questions"]["next_move"] == chat["question"]
    state = chat["state"]
    assert state == {"cube_facelets": SOLVED,
                     "faces": {f: "/".join([f * 3] * 3) for f in "URFDLB"},
                     "recent_moves": original[-6:], "moves_remaining": 30 - length}
    assert history == original
    assert list(chat["question"]["criteria"]) == list(MOVES)


@pytest.mark.parametrize("usage,expected", [
    ({"input_tokens": 786, "output_tokens": 156, "cost": 0.000033012},
     (786, 156, 942, "derived", None, 0.000033012)),
    ({"prompt_tokens": 882, "completion_tokens": 512, "total_tokens": 1394, "cost": 0.013768,
      "completion_tokens_details": {"reasoning_tokens": 512}},
     (882, 512, 1394, "provider", 512, 0.013768)),
    ({"input_tokens": 0, "output_tokens": 0, "cost": 0}, (0, 0, 0, "derived", None, 0)),
    ({"input_tokens": 786}, (786, None, None, None, None, None)),
    ({}, (None, None, None, None, None, None)),
    ({"prompt_tokens": 10, "input_tokens": 999, "completion_tokens": 20,
      "output_tokens": 888, "total_tokens": 40}, (10, 20, 40, "provider", None, None)),
])
def test_both_usage_contracts_preserve_unknowns_and_reported_values(usage, expected):
    actual = reported(usage)
    assert tuple(actual[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens",
                                    "total_tokens_source", "reasoning_tokens", "cost_usd")) == expected


def test_historical_usage_is_normalized_read_only_after_restart(tmp_path):
    path = str(tmp_path / "usage.db")
    store = Store(path)
    raw = {"input_tokens": 786, "output_tokens": 156, "cost": 0.000033012}
    request_id = store.reserve(1, MODELS[0].id)
    store.record_request(request_id, {"usage": raw, "billing": {"prompt_tokens": None}})
    before = store.db.execute("SELECT body FROM requests").fetchone()[0]
    store.close()
    store = Store(path)
    assert store.used() == 1 and store.billing()["tokens"]["total_tokens"]["known_total"] == 942
    assert store.billing()["total_cost_usd"] == raw["cost"]
    assert store.db.execute("SELECT body FROM requests").fetchone()[0] == before
    assert summarize([{"usage": raw}, {"usage": None}])["tokens"]["total_tokens"]["unknown_requests"] == 1
    store.close()


@pytest.mark.parametrize("value", ["", "jev,", "jev,jev", "other", "claude,other"])
def test_bad_smoke_selection(value):
    with pytest.raises(argparse.ArgumentTypeError):
        verify_live_api.select_models(value)


def test_cli_requires_consent_before_work(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No settings, key, or client access before CLI consent")
    monkeypatch.setattr(Settings, "env", forbidden)
    with pytest.raises(SystemExit) as exc:
        verify_live_api.main(["--models", "claude"])
    assert exc.value.code == 2


@pytest.mark.asyncio
async def test_direct_smoke_requires_consent():
    with pytest.raises(SystemExit, match="explicit --confirm-paid"):
        await verify_live_api.smoke()


@pytest.mark.asyncio
@pytest.mark.parametrize("selection,count", [("claude", 1), ("jev,luna", 2), (None, 4)])
@pytest.mark.parametrize("outcome", ["valid", "output_limit", "transport", "exhausted"])
async def test_selective_smoke_ceilings_and_evidence_preservation(
        tmp_path, monkeypatch, capsys, selection, count, outcome):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    legacy = tmp_path / "data/live-smoke.json"
    legacy.write_text("preserved historical evidence")
    seen = []
    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        model = next(m for m in MODELS if m.id == body["model"])
        if outcome == "transport":
            raise httpx.ReadTimeout("offline timeout")
        body = response(model, usage={"input_tokens": 10, "output_tokens": 2, "cost": 0.0001})
        if outcome == "output_limit" and model == MODELS[3]:
            body["choices"] = [{"finish_reason": "length", "message": {
                "content": "", "reasoning": "R is a tempting move, not a final JSON answer"}}]
            body["usage"] = {"prompt_tokens": 882, "completion_tokens": 1024, "total_tokens": 1906,
                             "completion_tokens_details": {"reasoning_tokens": 1024}, "cost": 0.024008}
        return httpx.Response(200, json=body)
    settings = Settings(key="private-test-key-must-not-appear", allow_live=True, mock_mode=False,
                        retries=3, budget=0 if outcome == "exhausted" else 20,
                        database=str(tmp_path / "smoke.db"))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(verify_live_api.httpx, "AsyncClient", lambda: original_client(
        transport=httpx.MockTransport(handler)))
    models = verify_live_api.select_models(selection) if selection else MODELS
    for _ in range(2):
        if outcome in ("transport", "exhausted") or outcome == "output_limit" and MODELS[3] in models:
            with pytest.raises(SystemExit, match="PARTIAL"):
                await verify_live_api.smoke(models, confirm_paid=True, settings=settings)
        else:
            await verify_live_api.smoke(models, confirm_paid=True, settings=settings)
    reports = [json.loads(p.read_text()) for p in (tmp_path / "data").glob("live-smoke-*.json")]
    assert len(reports) == 2 and legacy.read_text() == "preserved historical evidence"
    assert len(seen) == (0 if outcome == "exhausted" else count * 2)
    assert {b["model"] for b in seen} <= {m.id for m in models}
    for report in reports:
        assert report["selected_models"] == [m.id for m in models]
        assert report["request_cap"] == count
        assert report["request_policy"]["retries"] == 0
        assert report["request_policy"]["chat_max_tokens"] == 2048
        assert report["request_policy"]["history_window"] == 6
        assert report["request_count"] <= count
        if outcome == "output_limit" and MODELS[3] in models:
            claude = next(r for r in report["results"] if r["model_id"] == MODELS[3].id)
            assert claude["status"] == "OUTPUT_LIMIT" and "move" not in claude
            assert claude["requests"][0]["billing"]["reasoning_tokens"] == 1024
    output = capsys.readouterr().out
    assert settings.key not in output + json.dumps(reports)
    assert "http_status" in output and "effective_model_id" in output and "finish_reason" in output
    store = Store(settings.database)
    assert store.used() == len(seen)
    store.close()


def test_history_policy_conditions_are_not_pooled():
    base = {"mode": "live", "kind": "suite", "tier": "primary", "puzzle_count": 5,
            "races": [], "policy_version": "state-action-v3-recent6"}
    current = {**base, "request_policy": {"history_window": 6, "chat_max_tokens": 1024}}
    old = {**base, "policy_version": "state-action-v2-compact",
           "request_policy": {"chat_max_tokens": 512}}
    different = {**base, "request_policy": {"history_window": 6, "chat_max_tokens": 768}}
    stats = aggregate([current, old, different])
    assert stats["suite_count"] == 1 and stats["excluded_policy_suites"] == 2


def test_env_default_2048_without_overwriting_env(monkeypatch):
    monkeypatch.delenv("CLAUDE_MAX_TOKENS", raising=False)
    assert Settings.env().claude_max_tokens == 2048
    monkeypatch.setenv("CLAUDE_MAX_TOKENS", "512")
    assert Settings.env().claude_max_tokens == 512
    assert replace(Settings.env(), claude_max_tokens=1024).claude_max_tokens == 1024
