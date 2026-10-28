import asyncio
import json
import httpx
import pytest
from backend.config import Settings
from backend.cube import SOLVED, MOVES
from backend.models import MODELS, ENDPOINTS, Router, ModelFailure, parse, payload
from backend.store import Store


def response(model, move="R", **extra):
    body = {"model": model.id, **extra}
    if model.interface == "decisions":
        body["answers"] = {"next_move": {"type": "choice", "choice": move, "confidence": 0}}
    else:
        body["choices"] = [{"message": {"content": json.dumps({"move": move})}}]
    return body


def native_response(move="R'", **extra):
    return {"model": "gpt-6-luna", "answers": [{"type": "choice", "name": "next_move",
        "choice": move, "confidence": 0.2,
        "probabilities": [{"value": m, "probability": 1 / 18} for m in MOVES]}],
        "usage": {"input_tokens": 100, "output_tokens": 0, "total_tokens": 100,
                  "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                  "output_tokens_details": {"reasoning_tokens": 0}}, **extra}


def test_exact_registry():
    assert [m.id for m in MODELS] == ["typesafe/jev-1.13", "openai/gpt-6-luna-decisions",
                                    "cloudflare/clef", "anthropic/claude-opus-5.5"]
    assert [m.interface for m in MODELS] == ["decisions"] * 3 + ["chat"]


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("move", MOVES)
def test_response_contract(model, move):
    action, meta = parse(model, response(model, move))
    assert action == move
    assert meta["confidence"] == (0 if model.interface == "decisions" else None)


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("bad", [" R", "R U", "r", ["R"], None, "Turn R", "R\n"])
def test_strict_rejection(model, bad):
    with pytest.raises((ValueError, TypeError)):
        parse(model, response(model, bad))


def test_chat_rejects_extra_fields_and_prose():
    for content in ['```json\n{"move":"R"}\n```', '{"move":"R","reason":"yes"}', 'R',
                    '{"move":"U","move":"R"}']:
        body = response(MODELS[3])
        body["choices"][0]["message"]["content"] = content
        with pytest.raises(ValueError):
            parse(MODELS[3], body)


def test_equal_information_no_scramble_leak():
    bodies = [payload(m, SOLVED, []) for m in MODELS]
    contexts = [b["state"] for b in bodies[:3]]
    chat = json.loads(bodies[3]["messages"][1]["content"])
    assert all(c == chat["state"] for c in contexts)
    assert all(b["questions"]["next_move"] == chat["question"] for b in bodies[:3])
    assert contexts[0]["recent_moves"] == []
    assert "scramble" not in contexts[0]
    assert len(bodies[0]["questions"]["next_move"]["criteria"]) == 18
    schema = bodies[3]["response_format"]["json_schema"]
    assert schema["strict"] and schema["schema"]["properties"]["move"]["enum"] == list(MOVES)
    assert bodies[3]["provider"]["require_parameters"]
    assert payload(MODELS[0], SOLVED, ["U2"])["state"]["recent_moves"] == ["U2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("model", MODELS)
async def test_route_retry_and_telemetry(tmp_path, model):
    seen = []
    async def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(502)
        return httpx.Response(200, json=response(model, usage={"cost": 0.001}))
    store = Store(str(tmp_path / "test.db"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = []
        action = await Router(Settings(key="test", retries=1), store, client).decide(
            model, SOLVED, [], records, {"used": 0, "cap": 2})
    assert action == "R"
    assert len(records) == 2 and store.used() == 2
    assert [q["retry"] for q in records] == [0, 1]
    assert all(q["latency_ms"] >= 0 for q in records)
    assert all(str(r.url) == ENDPOINTS[model.interface] for r in seen)
    assert all(json.loads(r.content)["model"] == model.id for r in seen)
    assert records[-1]["usage"] == {"cost": 0.001}
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [400, 401, 402, 403, 404])
async def test_no_model_fallback_or_4xx_retry(tmp_path, code):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(code)
    store = Store(str(tmp_path / "test.db"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = []
        with pytest.raises(ModelFailure):
            await Router(Settings(key="test"), store, client).decide(
                MODELS[1], SOLVED, [], records, {"used": 0, "cap": 20})
    assert len(seen) == 1
    assert records[0]["http_status"] == code
    store.close()


@pytest.mark.asyncio
async def test_malformed_and_persistent_budget(tmp_path):
    path = str(tmp_path / "test.db")
    store = Store(path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))) as client:
        records = []
        router = Router(Settings(key="test", budget=1, retries=1), store, client)
        with pytest.raises(ModelFailure) as exc:
            await router.decide(MODELS[0], SOLVED, [], records, {"used": 0, "cap": 10})
        assert exc.value.status == "BUDGET_EXHAUSTED"
        assert records[0]["outcome"] == "MALFORMED"
    store.close()
    store = Store(path)
    assert store.used() == 1 and not store.consume(1)
    store.close()


@pytest.mark.asyncio
async def test_mismatched_effective_id_rejected(tmp_path):
    store = Store(str(tmp_path / "test.db"))
    body = response(MODELS[0])
    body["model"] = "some/other-model"
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))) as client:
        records = []
        with pytest.raises(ModelFailure) as exc:
            await Router(Settings(key="test"), store, client).decide(
                MODELS[0], SOLVED, [], records, {"used": 0, "cap": 10})
        assert exc.value.status == "UNAVAILABLE"
        assert records[0]["effective_model_id"] == "some/other-model"
    store.close()


@pytest.mark.asyncio
async def test_global_and_per_run_caps_under_concurrency(tmp_path):
    store = Store(str(tmp_path / "test.db"))
    def handler(request):
        return httpx.Response(200, json=response(MODELS[0]))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = Router(Settings(key="test", budget=3), store, client)
        budget = {"used": 0, "cap": 2}
        results = await asyncio.gather(*(router.decide(MODELS[0], SOLVED, [], [], budget)
                                         for _ in range(10)), return_exceptions=True)
        assert results.count("R") == 2
        assert store.used() == budget["used"] == 2
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ['[]', 'null', '{"confidence":NaN}',
                                    '{"model":"a","model":"b"}', '{"cost":1e999}'])
async def test_invalid_response_shapes_and_nonfinite_json(tmp_path, content):
    store = Store(str(tmp_path / "test.db"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r: httpx.Response(200, text=content))) as client:
        records = []
        with pytest.raises(ModelFailure):
            await Router(Settings(key="test", retries=0), store, client).decide(
                MODELS[0], SOLVED, [], records, {"used": 0, "cap": 1})
        assert records[0]["outcome"] == "MALFORMED"
    store.close()


@pytest.mark.asyncio
async def test_transport_timeout_and_cancel_recorded(tmp_path):
    store = Store(str(tmp_path / "test.db"))
    async def timeout(request):
        raise httpx.ReadTimeout("synthetic timeout")
    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        records = []
        with pytest.raises(ModelFailure):
            await Router(Settings(key="test", retries=0), store, client).decide(
                MODELS[0], SOLVED, [], records, {"used": 0, "cap": 2})
        assert records[0]["outcome"] == "TRANSPORT_ERROR"
        assert records[0]["latency_ms"] >= 0
    started = asyncio.Event()
    async def delayed(request):
        started.set()
        await asyncio.sleep(10)
        return httpx.Response(200, json=response(MODELS[0]))
    async with httpx.AsyncClient(transport=httpx.MockTransport(delayed)) as client:
        records = []
        task = asyncio.create_task(Router(Settings(key="test"), store, client).decide(
            MODELS[0], SOLVED, [], records, {"used": 0, "cap": 2}))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert records[0]["outcome"] == "CANCELLED"
        assert records[0]["latency_ms"] >= 0
    store.close()
