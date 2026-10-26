"""Native OpenAI contract fixtures, never paid requests."""
import asyncio
import importlib
import json
from dataclasses import replace
import httpx
import pytest
from backend.config import Settings
from backend.cube import MOVES
from backend.models import MODELS, V4_POLICY_VERSION, payload
from backend.store import Store
from backend.stats import aggregate
from verify_cube_diagnostics import plan


def diagnostic():
    assert importlib.util.find_spec("verify_luna_openai"), "Missing optional native Luna diagnostic"
    return importlib.import_module("verify_luna_openai")


def native_response(move="R'", **extra):
    return {"model": "gpt-6-luna", "answers": [{"type": "choice", "name": "next_move",
        "choice": move, "confidence": 0.2,
        "probabilities": [{"value": m, "probability": 1 / 18} for m in MOVES]}],
        "usage": {"input_tokens": 100, "output_tokens": 0, "total_tokens": 100,
                  "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                  "output_tokens_details": {"reasoning_tokens": 0}}, **extra}


def test_native_request_preserves_exact_v4_information():
    module = diagnostic()
    for case in plan()["cases"]:
        baseline = payload(MODELS[1], case["initial_state"], [], policy_version=V4_POLICY_VERSION)
        body = module.native_payload(case["initial_state"])
        assert set(body) == {"model", "input", "questions"}
        assert body["model"] == "gpt-6-luna"
        assert body["input"] == [{"role": "user", "content": [
            {"type": "input_json", "data": baseline["state"]}]}]
        question = body["questions"][0]
        assert question["instructions"] == baseline["questions"]["next_move"]["instructions"]
        assert question["type"] == "choice" and question["name"] == "next_move"
        assert question["choices"] == [{"value": m, "description": desc}
                                       for m, desc in baseline["questions"]["next_move"]["criteria"].items()]
        assert "source>destination" not in json.dumps(body)  # v4, never current v5 rules


def test_preview_does_not_open_database_or_http(tmp_path, monkeypatch, capsys):
    module = diagnostic()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "Store", lambda *a: pytest.fail("Preview must not open DB"))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **k: pytest.fail("Preview must not call HTTP"))
    module.main([])
    preview = json.loads(capsys.readouterr().out)
    assert preview["request_cap"] == 2 and preview["paid_calls_authorized"] is False
    assert preview["provider"] == "OpenAI" and preview["model"] == "gpt-6-luna"
    assert preview["policy_version"] == V4_POLICY_VERSION
    assert preview["cases"] == plan()["cases"] and list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome,expected", [("valid", 2), ("wrong_move", 2), ("http502", 2),
    ("http401", 1), ("wrong_model", 1), ("refusal", 2), ("timeout", 2), ("schema", 1), ("redirect", 1)])
async def test_direct_calls_accounting_errors_and_isolation(tmp_path, monkeypatch, capsys, outcome, expected):
    module = diagnostic()
    monkeypatch.chdir(tmp_path)
    key = "sk-private-offline-only"
    settings = Settings(database=str(tmp_path / "native.db"), allow_live=True,
                        mock_mode=False, budget=4)  # No OpenRouter key required.
    seen = []
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/decisions"
        assert request.headers["authorization"] == f"Bearer {key}"
        seen.append(json.loads(request.content))
        if outcome in ("http502", "http401"):
            return httpx.Response(502 if outcome == "http502" else 401, json={"error": {
                "type": "provider_error", "code": "native_error", "message": f"Echo {key}"}},
                headers={"x-request-id": "req-fixture"})
        if outcome == "timeout":
            raise httpx.ReadTimeout(f"Echo {key}")
        if outcome == "redirect":
            return httpx.Response(307, headers={"location": "https://other.invalid/paid"})
        body = native_response("B" if outcome == "wrong_move" else ("R'" if len(seen) % 2 else "U"))
        if outcome == "valid":
            body["error"] = None  # A null optional error is not an API failure.
        if outcome == "wrong_model":
            body["model"] = "unrelated/model"
        if outcome == "refusal":
            body["answers"] = [{"type": "refusal", "name": "next_move"}]
        if outcome == "schema":
            body["answers"] = {"next_move": {"type": "choice", "choice": "R'"}}
        return httpx.Response(200, json=body, headers={"x-request-id": "req-fixture"})
    paths = []
    for _ in range(2):
        path = await module.diagnose(confirm_paid=True, api_key=key, settings=settings,
                                     transport=httpx.MockTransport(handler))
        paths.append(path)
        report = json.loads(path.read_text())
        assert report["provider"] == "OpenAI" and report["request_count"] == expected
        assert report["policy_version"] == V4_POLICY_VERSION
        assert report["kind"] == "direct_openai_luna_diagnostic_not_benchmark"
        assert report["retries"] == 0 and report["request_cap"] == 2
        assert report["correct_first_actions"] == (2 if outcome == "valid" else 0)
        requests = [q for r in report["results"] for q in r["requests"]]
        assert all(q["retry"] == 0 and q["provider"] == "OpenAI" for q in requests)
        assert all(q["latency_ms"] >= 0 for q in requests)
        assert report["billing"]["total_cost_usd"] is None  # Native API reports no cost.
        if outcome not in ("http502", "http401", "timeout", "redirect"):
            assert report["billing"]["tokens"]["reasoning_tokens"]["known_total"] == 0
        if outcome == "refusal":
            assert all(r["status"] == "REFUSED" for r in report["results"])
        if outcome == "wrong_move":
            assert all(r["move"] == "B" and r["first_action_correct"] is False for r in report["results"])
        if outcome.startswith("http"):
            assert requests[0]["api_error"]["code"] == "native_error"
            assert requests[0]["request_id"] == "req-fixture"
        assert key not in path.read_text()
    assert paths[0] != paths[1] and len(seen) == expected * 2
    if expected == 2:
        with pytest.raises(SystemExit):
            await module.diagnose(confirm_paid=True, api_key=key, settings=settings,
                                  transport=httpx.MockTransport(handler))
        assert len(seen) == 4  # No budget reset on another invocation.
    store = Store(settings.database)
    assert store.used() == len(seen) and store.all() == []
    assert list(store.billing()["by_model"]) == [module.LEDGER_MODEL]
    store.close()
    assert key not in capsys.readouterr().out


@pytest.mark.asyncio
@pytest.mark.parametrize("block", ["consent", "key", "budget", "retries", "disabled", "mock", "active"])
async def test_direct_guards_prevent_inference(tmp_path, monkeypatch, block):
    module = diagnostic()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(database=str(tmp_path / "guards.db"), allow_live=True, mock_mode=False, budget=2)
    if block == "budget":
        settings = replace(settings, budget=1)
    if block == "retries":
        settings = replace(settings, retries=1)
    if block == "disabled":
        settings = replace(settings, allow_live=False)
    if block == "mock":
        settings = replace(settings, mock_mode=True)
    if block == "active":
        store = Store(settings.database)
        store.save({"id": "existing", "status": "RUNNING"})
        store.close()
    with pytest.raises(SystemExit):
        await module.diagnose(confirm_paid=block != "consent", api_key="" if block == "key" else "offline",
            settings=settings, transport=httpx.MockTransport(lambda r: pytest.fail("Unexpected HTTP")))


@pytest.mark.parametrize("bad", ["R U", " R", "R\n", "r", True, None, ["R"]])
def test_native_illegal_moves_rejected(bad):
    module = diagnostic()
    with pytest.raises(ValueError):
        module.parse_native(native_response(bad))


@pytest.mark.parametrize("move", MOVES)
def test_native_legal_move_is_never_replaced_by_probability_ranking(move):
    selected, metadata = diagnostic().parse_native(native_response(move))
    assert selected == move and len(metadata["probabilities"]) == 18


@pytest.mark.parametrize("bad", ["extra_answer", "wrong_name", "map_probabilities", "duplicate", "unknown",
                                 "negative", "nan", "boolean_confidence"])
def test_native_schema_and_probability_validation(bad):
    body = native_response()
    answer = body["answers"][0]
    if bad == "extra_answer":
        body["answers"].append(answer.copy())
    elif bad == "wrong_name":
        answer["name"] = "different"
    elif bad == "map_probabilities":
        answer["probabilities"] = {"R": 1}
    elif bad == "duplicate":
        answer["probabilities"][1]["value"] = answer["probabilities"][0]["value"]
    elif bad == "unknown":
        answer["probabilities"][0]["value"] = "X"
    elif bad in ("negative", "nan"):
        answer["probabilities"][0]["probability"] = -1 if bad == "negative" else float("nan")
    else:
        answer["confidence"] = True
    with pytest.raises(ValueError):
        diagnostic().parse_native(body)


@pytest.mark.asyncio
async def test_cancelled_request_remains_counted_and_evidence_saved(tmp_path, monkeypatch):
    module = diagnostic()
    monkeypatch.chdir(tmp_path)
    settings = Settings(database=str(tmp_path / "cancel.db"), allow_live=True, mock_mode=False, budget=2)
    async def handler(request):
        raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await module.diagnose(confirm_paid=True, api_key="offline", settings=settings,
                              transport=httpx.MockTransport(handler))
    reports = list((tmp_path / "data/direct-openai").glob("*.json"))
    report = json.loads(reports[0].read_text())
    assert report["request_count"] == 1
    assert [r["status"] for r in report["results"]] == ["ABORTED", "NOT_RUN"]
    assert report["billing"]["unknown_cost_requests"] == 1
    store = Store(settings.database)
    assert store.used() == 1 and store.all() == []
    store.close()


@pytest.mark.asyncio
async def test_existing_openrouter_history_and_aggregates_remain_separate(tmp_path, monkeypatch):
    module = diagnostic()
    monkeypatch.chdir(tmp_path)
    settings = Settings(database=str(tmp_path / "history.db"), allow_live=True, mock_mode=False, budget=3)
    legacy = {"id": "legacy-suite", "status": "COMPLETED", "mode": "live", "kind": "suite",
              "tier": "primary", "puzzle_count": 1, "races": [], "policy_version": V4_POLICY_VERSION}
    store = Store(settings.database)
    store.save(legacy)
    old_id = store.reserve(3, MODELS[1].id, legacy["id"], 0)
    old_request = {"outcome": "VALID", "run_id": legacy["id"], "usage": {"cost": 0.001}}
    store.record_request(old_id, old_request)
    store.close()
    await module.diagnose(confirm_paid=True, api_key="offline", settings=settings,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=native_response())))
    store = Store(settings.database)
    assert store.all() == [legacy] and aggregate(store.all())["suite_count"] == 1
    assert json.loads(store.db.execute("SELECT body FROM requests WHERE id=?", (old_id,)).fetchone()[0]) == old_request
    assert store.used() == 3
    assert set(store.billing()["by_model"]) == {MODELS[1].id, module.LEDGER_MODEL}
    assert store.billing()["by_model"][MODELS[1].id]["total_cost_usd"] == 0.001
    store.close()

@pytest.mark.parametrize("policy", ["v4", "v5"])
def test_selected_policy_preserves_shared_information(policy):
    from backend.models import V5_POLICY_VERSION
    module = diagnostic()
    version = V4_POLICY_VERSION if policy == 'v4' else V5_POLICY_VERSION
    for case in plan()["cases"]:
        body = module.native_payload(case['initial_state'], policy=policy)
        baseline = payload(MODELS[1], case['initial_state'], [], policy_version=version)
        assert body['input'][0]['content'][0]['data'] == baseline['state']
        assert body['questions'][0]['instructions'] == baseline['questions']['next_move']['instructions']
        assert body['questions'][0]['choices'] == [
            {'value': m, 'description': d} for m, d in baseline['questions']['next_move']['criteria'].items()]


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['1', '2'])
async def test_single_case_v5_uses_one_call_and_one_remaining_budget(tmp_path, monkeypatch, case):
    from backend.models import V5_POLICY_VERSION
    module = diagnostic()
    monkeypatch.chdir(tmp_path)
    cfg = Settings(database=str(tmp_path / 'single.db'), allow_live=True, mock_mode=False, budget=1)
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=native_response())
    path = await module.diagnose(confirm_paid=True, api_key='offline', settings=cfg,
        transport=httpx.MockTransport(handler), policy='v5', case=case)
    report = json.loads(path.read_text())
    assert len(seen) == report['request_count'] == report['request_cap'] == report['planned_first_actions'] == 1
    assert report['policy_version'] == V5_POLICY_VERSION and path.name.startswith('luna-v5-')
    assert report['cases'] == [plan()['cases'][int(case) - 1]]
    request = report['results'][0]['requests'][0]
    assert request['policy_version'] == V5_POLICY_VERSION
    assert request['provider_answers'] == native_response()['answers']
    assert seen[0] == module.native_payload(report['cases'][0]['initial_state'], policy='v5')
    with pytest.raises(SystemExit):
        await module.diagnose(confirm_paid=True, api_key='offline', settings=cfg,
            transport=httpx.MockTransport(handler), policy='v5', case=case)
    assert len(seen) == 1


def test_selection_preview_is_free_and_unknown_policies_fail_closed(tmp_path, monkeypatch, capsys):
    module = diagnostic()
    monkeypatch.chdir(tmp_path)
    module.main(['--policy', 'v5', '--case', '2'])
    result = json.loads(capsys.readouterr().out)
    assert result['request_cap'] == 1 and result['cases'] == [plan()['cases'][1]]
    assert not result['paid_calls_authorized'] and not list(tmp_path.iterdir())
    for kwargs in ({'policy': 'v6'}, {'case': '3'}):
        with pytest.raises(ValueError):
            module.preview(**kwargs)
