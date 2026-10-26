"""No solver imports: live adapters only receive the current state and agent history."""
import asyncio
import json
import time
from dataclasses import dataclass
import httpx
from .cube import MOVES, FACES
from .config import Settings
from .billing import reported
from .turn_rules import TURN_RULES
from . import native_decisions as native


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
ALLOWED_EFFECTIVE_IDS = {
    "typesafe/jev-1.13": {"typesafe/jev-1.13", "typesafe/jev-1.13-20260917"},
    "openai/gpt-6-luna-decisions": {
        "openai/gpt-6-luna-decisions", "openai/gpt-6-luna-decisions-20261006"},
    "cloudflare/clef": {"cloudflare/clef"},
    "anthropic/claude-opus-5.5": {"anthropic/claude-opus-5.5"},
}
HISTORY_WINDOW = 6
V4_POLICY_VERSION = "state-action-v4-facegrids"
V5_POLICY_VERSION = "state-action-v5-permutations"
POLICY_VERSION = "state-action-v6-compact-choice"
FACE_ORIENTATION = {"U": "B/R", "R": "U/B", "F": "U/R",
                    "D": "F/R", "L": "U/F", "B": "U/L"}


def request_policy(settings):
    policy = {"timeout_seconds": settings.timeout, "retries": settings.retries,
            "claude_reasoning_effort": settings.claude_reasoning_effort,
            "chat_max_tokens": settings.claude_max_tokens, "concurrency": settings.concurrency,
            "history_window": HISTORY_WINDOW, "history_policy": "last-six-executed-agent-moves",
            "state_encoding": "URFDLB-row-major-slash-grids-v1",
            "turn_rules_version": None,
            "effective_id_policy": "explicit-allowlist-2026-10-25"}
    if settings.luna_provider == "openai":
        policy["luna_route"] = {"provider": "OpenAI", "model": native.MODEL,
                                "endpoint": native.ENDPOINT}
    return policy


ENDPOINTS = {"decisions": "https://openrouter.ai/api/alpha/decisions",
             "chat": "https://openrouter.ai/api/v1/chat/completions"}
V4_INSTRUCTIONS = (
    "Choose one move to solve all six faces within moves_remaining. "
    "Goal: each face matches its center. Letters denote fixed-center colors "
    "(URFDLB=up/right/front/down/left/back). "
    "cube_facelets is row-major URFDLB; faces uses '/' between rows. "
    "Outside views; top/right neighbors: "
    + ";".join(f"{f}={neighbors}" for f, neighbors in FACE_ORIENTATION.items()) + ". "
    "Turns: degrees, CW clockwise, CCW counterclockwise, viewed at the named face. "
    "HTM: each listed turn=1 move; 30 max."
)
V5_INSTRUCTIONS = V4_INSTRUCTIONS + TURN_RULES
# Restore v4's compact representation, but ask for one bounded choice, not a full solution.
INSTRUCTIONS = (
    "Which listed face turn should be executed next to solve this Rubik's Cube, within moves_remaining? "
    "Goal: " + V4_INSTRUCTIONS.split("Goal: ", 1)[1]
)
NAMES = dict(zip(FACES, ("up", "right", "front", "down", "left", "back")))
CRITERIA = {m: f"{NAMES[m[0]]} " +
            ("180" if m.endswith("2") else "90 CCW" if m.endswith("'") else "90 CW")
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


def payload(model, state, history, settings=None, *, policy_version=POLICY_VERSION):
    if policy_version not in (V4_POLICY_VERSION, V5_POLICY_VERSION, POLICY_VERSION):
        raise ValueError("Unknown prompt policy")
    settings = settings or Settings(claude_max_tokens=1024 if policy_version in (
        V4_POLICY_VERSION, V5_POLICY_VERSION) else 2048)
    context = {"cube_facelets": state,
               "faces": {f: "/".join(state[i:i + 3] for i in range(n * 9, n * 9 + 9, 3))
                         for n, f in enumerate(FACES)},
               "recent_moves": list(history[-HISTORY_WINDOW:]),
               "moves_remaining": 30 - len(history)}
    instructions = {V4_POLICY_VERSION: V4_INSTRUCTIONS, V5_POLICY_VERSION: V5_INSTRUCTIONS,
                    POLICY_VERSION: INSTRUCTIONS}[policy_version]
    question = {"type": "choice", "instructions": instructions, "criteria": CRITERIA}
    if model.interface == "decisions":
        return {"model": model.id, "state": context, "questions": {"next_move": question}}
    return {"model": model.id, "messages": [
        {"role": "system", "content": "Return one legal move as schema JSON."},
        {"role": "user", "content": json.dumps({"state": context, "question": question}, separators=(",", ":"))}],
        "max_tokens": settings.claude_max_tokens,
        "reasoning": {"effort": settings.claude_reasoning_effort},
        # Legacy chat opt-in is accepted but deprecated; accounting is now automatic.
        # The typed Decisions contract does not document this extra request property.
        "usage": {"include": True},
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "cube_action", "strict": True, "schema": {
                "type": "object", "properties": {"move": {"type": "string", "enum": list(MOVES)}},
                "required": ["move"], "additionalProperties": False}}},
        "provider": {"allow_fallbacks": False, "require_parameters": True}}


class ModelFailure(Exception):
    def __init__(self, status, message, permanent=False):
        self.status = status
        self.permanent = permanent
        super().__init__(message)


class UnsupportedSchema(ValueError):
    pass


def parse(model, body):
    if model.interface == "decisions":
        try:
            answer = body["answers"]["next_move"]
            if not isinstance(answer, dict) or answer.get("type") != "choice" or "choice" not in answer:
                raise UnsupportedSchema("Expected typed next_move choice answer")
            move = answer["choice"]
        except (KeyError, TypeError):
            raise UnsupportedSchema("Missing Decisions answer envelope")
        metadata = {k: answer.get(k) for k in ("confidence", "probabilities")}
    else:
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise UnsupportedSchema("Missing chat completion envelope")
        answer = strict_json(content)
        if not isinstance(answer, dict) or set(answer) != {"move"}:
            raise UnsupportedSchema("Expected exactly one move property")
        move, metadata = answer["move"], {"confidence": None, "probabilities": None}
    if not isinstance(move, str) or move not in MOVES:
        raise ValueError("Expected exactly one legal move")
    return move, metadata


class Router:
    def __init__(self, settings, store, client):
        self.settings, self.store, self.client = settings, store, client
        self.semaphore = asyncio.Semaphore(settings.concurrency)

    async def decide(self, model, state, history, records, run_budget, schema_failures=None):
        cfg = self.settings
        direct = model.id == MODELS[1].id and cfg.luna_provider == "openai"
        endpoint = native.ENDPOINT if direct else ENDPOINTS[model.interface]
        provider_name = "OpenAI" if direct else "OpenRouter"
        key = cfg.openai_key if direct else cfg.key
        if direct and not key.strip():
            raise ModelFailure("UNAVAILABLE", "OPENAI_API_KEY missing; no OpenRouter fallback", permanent=True)
        schema_failures = schema_failures if schema_failures is not None else {}
        for retry in range(cfg.retries + 1):
            async with self.semaphore:
                if run_budget["used"] >= run_budget["cap"]:
                    raise ModelFailure("BUDGET_EXHAUSTED", "Persistent or per-run request cap reached")
                request_id = self.store.reserve(cfg.budget, model.id, run_budget.get("run_id"),
                                                run_budget.get("race_index"), retry)
                if request_id is None:
                    raise ModelFailure("BUDGET_EXHAUSTED", "Persistent or per-run request cap reached")
                run_budget["used"] += 1
                record = {"request_index": len(records) + 1, "retry": retry,
                          "run_id": run_budget.get("run_id"),
                          "race_index": run_budget.get("race_index"), "ledger_id": request_id,
                          "requested_model_id": model.id, "effective_model_id": None,
                          "endpoint": endpoint, "http_status": None,
                          "latency_ms": None, "outcome": "PENDING", "usage": None,
                          "provider": None, "response_id": None, "finish_reason": None,
                          "billing": reported(None)}
                record.update(policy_version=POLICY_VERSION, history_window=HISTORY_WINDOW,
                              provider_route="direct_openai_decisions" if direct else "openrouter",
                              api_provider=provider_name,
                              provider_requested_model_id=native.MODEL if direct else model.id,
                              turn_rules_version=None,
                              state_encoding="URFDLB-row-major-slash-grids-v1",
                              model_visible_history=list(history[-HISTORY_WINDOW:]),
                              moves_remaining=30 - len(history))
                records.append(record)
                start = time.perf_counter()
                try:
                    request_body = payload(model, state, history, cfg)
                    response = await self.client.post(endpoint,
                        headers={"Authorization": f"Bearer {key}",
                                 "X-Title": "CubeRace: System-1 vs LLM"},
                        json=native.translate(request_body) if direct else request_body, timeout=cfg.timeout)
                    record["latency_ms"] = (time.perf_counter() - start) * 1000
                    record["http_status"] = response.status_code
                    if direct:
                        record["request_id"] = response.headers.get("x-request-id")
                    # Retain billing even on HTTP errors or unusable action output.
                    try:
                        envelope = strict_json(response.text)
                        if isinstance(envelope, dict):
                            record["usage"] = envelope.get("usage")
                            if direct and isinstance(record["usage"], dict):
                                record["provider_usage"] = record["usage"]
                                record["usage"] = {**record["usage"], "completion_tokens_details":
                                                   record["usage"].get("output_tokens_details")}
                            record["billing"] = reported(record["usage"])
                    except (ValueError, TypeError):
                        pass
                    if response.status_code >= 400 or (direct and response.status_code >= 300):
                        schema_failures[model.id] = 0
                        record["outcome"] = "HTTP_ERROR"
                        if response.status_code in (429, 500, 502, 503, 504) and retry < cfg.retries:
                            pass
                        else:
                            status = "UNAVAILABLE" if response.status_code in (400, 402, 404) else "API_ERROR"
                            raise ModelFailure(status, f"{provider_name} HTTP {response.status_code}; no substitution",
                                               permanent=response.status_code in (400, 401, 402, 403, 404, 422)
                                               or (direct and 300 <= response.status_code < 400))
                    else:
                        try:
                            body = strict_json(response.text)
                            if not isinstance(body, dict):
                                raise UnsupportedSchema("Expected response object")
                            record.update(effective_model_id=body.get("model"),
                                          provider="OpenAI" if direct else body.get("provider"), response_id=body.get("id"))
                            if direct:
                                record["request_id"] = response.headers.get("x-request-id")
                            error = body.get("error")
                            if isinstance(error, dict) and error.get("code") in (400, 401, 402, 403, 404, 422):
                                record["outcome"] = "PROVIDER_ERROR"
                                raise ModelFailure("UNAVAILABLE", "Provider reports permanent incompatibility", permanent=True)
                            effective_id = body.get("model")
                            allowed = {native.MODEL} if direct else ALLOWED_EFFECTIVE_IDS[model.id]
                            if (direct and effective_id is None) or (effective_id is not None and (
                                    not isinstance(effective_id, str) or effective_id not in allowed)):
                                record["outcome"] = "MODEL_ID_MISMATCH"
                                raise ModelFailure("UNAVAILABLE", "Effective model ID not in explicit allowlist", permanent=True)
                            choices = body.get("choices")
                            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                                record["finish_reason"] = choices[0].get("finish_reason")
                            if record["finish_reason"] == "length":
                                schema_failures[model.id] = 0
                                record["outcome"] = "OUTPUT_LIMIT"
                                raise ModelFailure("OUTPUT_LIMIT", f"Fixed {cfg.claude_max_tokens}-token completion budget exhausted; no move or retry")
                            if direct:
                                try:
                                    move, meta = native.parse_native(body)
                                except native.NativeRefusal:
                                    record["outcome"] = "REFUSED"
                                    raise ModelFailure("REFUSED", "OpenAI declined to choose a move; no retry or fallback")
                                except native.NativeSchemaError as exc:
                                    raise UnsupportedSchema(str(exc))
                            else:
                                move, meta = parse(model, body)
                            if effective_id is None:
                                record["outcome"] = "MODEL_ID_MISSING"
                                raise ModelFailure("UNAVAILABLE", "Missing effective model ID; review routing", permanent=True)
                            schema_failures[model.id] = 0
                            record.update(meta)
                            record["outcome"] = "VALID"
                            return move
                        except UnsupportedSchema:
                            record["outcome"] = "MALFORMED"
                            record["schema_error"] = True
                            schema_failures[model.id] = schema_failures.get(model.id, 0) + 1
                            if schema_failures[model.id] >= 2:
                                raise ModelFailure("UNAVAILABLE", "Repeated unsupported response envelope; later puzzles NOT_RUN", permanent=True)
                            if retry == cfg.retries:
                                raise ModelFailure("API_ERROR", "Unsupported response envelope; no move executed")
                        except (KeyError, ValueError, TypeError, IndexError):
                            schema_failures[model.id] = 0
                            record["outcome"] = "MALFORMED"
                            if retry == cfg.retries:
                                raise ModelFailure("API_ERROR", "Malformed structured output; no move executed")
                except (httpx.TimeoutException, httpx.NetworkError):
                    schema_failures[model.id] = 0
                    record["latency_ms"] = (time.perf_counter() - start) * 1000
                    record["outcome"] = "TRANSPORT_ERROR"
                    if retry == cfg.retries:
                        raise ModelFailure("API_ERROR", f"{provider_name} transport error or timeout")
                except asyncio.CancelledError:
                    record["latency_ms"] = (time.perf_counter() - start) * 1000
                    record["outcome"] = "CANCELLED"
                    raise
                finally:
                    self.store.record_request(request_id, record)
            await asyncio.sleep(min(0.25 * 2 ** retry, 2))
        raise ModelFailure("API_ERROR", "No valid decision")
