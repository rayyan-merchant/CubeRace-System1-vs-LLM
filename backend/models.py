"""No solver imports: live adapters only receive the current state and agent history."""
import asyncio
import json
import time
from dataclasses import dataclass
import httpx
from .cube import MOVES, SOLVED


@dataclass(frozen=True)
class Model:
    id: str
    label: str
    interface: str


MODELS = (
    Model("typesafe/jev-1.13", "Jev 1.13", "decisions"),
    Model("openai/gpt-6-luna-decisions", "GPT-6 Luna Decisions", "decisions"),
    Model("cloudflare/clef", "Cloudflare Clef", "decisions"),
    Model("anthropic/claude-opus-5.5", "Claude Opus 5.5", "chat"),
)
ENDPOINTS = {"decisions": "https://openrouter.ai/api/alpha/decisions",
             "chat": "https://openrouter.ai/api/v1/chat/completions"}
INSTRUCTIONS = (
    "Choose the single next move most likely to progress toward the solved cube. "
    "Use standard Singmaster notation, clockwise when looking directly at the named face. "
    "Facelets are row-major in URFDLB order with fixed centers. "
    "Only one legal move may be executed per decision. Maximum 30 moves, half-turn metric."
)
NAMES = dict(zip("URFDLB", ("upper", "right", "front", "down", "left", "back")))
CRITERIA = {m: f"Turn the {NAMES[m[0]]} face " +
            ("180 degrees" if m.endswith("2") else
             "counterclockwise 90 degrees" if m.endswith("'") else "clockwise 90 degrees")
            for m in MOVES}


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON property")
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=pairs)
    json.dumps(value, allow_nan=False)
    return value


def payload(model, state, history):
    context = {"cube_facelets": state, "recent_moves": list(history),
               "goal_facelets": SOLVED, "moves_remaining": 30 - len(history),
               "metric": "HTM", "facelet_order": "URFDLB"}
    question = {"type": "choice", "instructions": INSTRUCTIONS, "criteria": CRITERIA}
    if model.interface == "decisions":
        return {"model": model.id, "state": context, "questions": {"next_move": question}}
    return {"model": model.id, "messages": [
        {"role": "system", "content": INSTRUCTIONS + ' Return only JSON: {"move":"R"}.'},
        {"role": "user", "content": json.dumps({"state": context, "question": question})}],
        "max_tokens": 2048,
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "cube_action", "strict": True, "schema": {
                "type": "object", "properties": {"move": {"type": "string", "enum": list(MOVES)}},
                "required": ["move"], "additionalProperties": False}}},
        "provider": {"allow_fallbacks": False, "require_parameters": True}}


class ModelFailure(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def parse(model, body):
    if model.interface == "decisions":
        answer = body["answers"]["next_move"]
        if answer["type"] != "choice":
            raise ValueError("Expected choice answer")
        move = answer["choice"]
        metadata = {k: answer.get(k) for k in ("confidence", "probabilities")}
    else:
        answer = strict_json(body["choices"][0]["message"]["content"])
        if not isinstance(answer, dict) or set(answer) != {"move"}:
            raise ValueError("Expected exactly one move property")
        move, metadata = answer["move"], {"confidence": None, "probabilities": None}
    if not isinstance(move, str) or move not in MOVES:
        raise ValueError("Expected exactly one legal move")
    return move, metadata


class Router:
    def __init__(self, settings, store, client):
        self.settings, self.store, self.client = settings, store, client
        self.semaphore = asyncio.Semaphore(settings.concurrency)

    async def decide(self, model, state, history, records, run_budget):
        cfg = self.settings
        for retry in range(cfg.retries + 1):
            async with self.semaphore:
                if run_budget["used"] >= run_budget["cap"] or not self.store.consume(cfg.budget):
                    raise ModelFailure("BUDGET_EXHAUSTED", "Persistent or per-run request cap reached")
                run_budget["used"] += 1
                record = {"request_index": len(records) + 1, "retry": retry,
                          "requested_model_id": model.id, "effective_model_id": None,
                          "endpoint": ENDPOINTS[model.interface], "http_status": None,
                          "latency_ms": None, "outcome": "PENDING", "usage": None,
                          "provider": None, "response_id": None}
                records.append(record)
                start = time.perf_counter()
                try:
                    response = await self.client.post(ENDPOINTS[model.interface],
                        headers={"Authorization": f"Bearer {cfg.key}",
                                 "X-Title": "CubeRace: System-1 vs LLM"},
                        json=payload(model, state, history), timeout=cfg.timeout)
                    record["latency_ms"] = (time.perf_counter() - start) * 1000
                    record["http_status"] = response.status_code
                    if response.status_code >= 400:
                        record["outcome"] = "HTTP_ERROR"
                        if response.status_code in (429, 500, 502, 503, 504) and retry < cfg.retries:
                            pass
                        else:
                            status = "UNAVAILABLE" if response.status_code in (400, 402, 404) else "API_ERROR"
                            raise ModelFailure(status, f"OpenRouter HTTP {response.status_code}; no substitution")
                    else:
                        try:
                            body = strict_json(response.text)
                            if not isinstance(body, dict):
                                raise ValueError("Expected response object")
                            record.update(effective_model_id=body.get("model"), usage=body.get("usage"),
                                          provider=body.get("provider"), response_id=body.get("id"))
                            if body.get("model") and body["model"] != model.id:
                                record["outcome"] = "MODEL_ID_MISMATCH"
                                raise ModelFailure("UNAVAILABLE", "Effective model ID differs; review routing")
                            move, meta = parse(model, body)
                            record.update(meta)
                            record["outcome"] = "VALID"
                            return move
                        except (KeyError, ValueError, TypeError, IndexError):
                            record["outcome"] = "MALFORMED"
                            if retry == cfg.retries:
                                raise ModelFailure("API_ERROR", "Malformed structured output; no move executed")
                except (httpx.TimeoutException, httpx.NetworkError):
                    record["latency_ms"] = (time.perf_counter() - start) * 1000
                    record["outcome"] = "TRANSPORT_ERROR"
                    if retry == cfg.retries:
                        raise ModelFailure("API_ERROR", "OpenRouter transport error or timeout")
                except asyncio.CancelledError:
                    record["latency_ms"] = (time.perf_counter() - start) * 1000
                    record["outcome"] = "CANCELLED"
                    raise
            await asyncio.sleep(min(0.25 * 2 ** retry, 2))
        raise ModelFailure("API_ERROR", "No valid decision")
