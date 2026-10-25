# OpenRouter contract verification

Reviewed 2026-10-22; cost/reasoning contract rechecked 2026-10-24. Documentation/model-page visibility is not proof of paid account access.

Official sources consulted:

- https://openrouter.ai/docs/api-reference/overview — chat endpoint, request `model` /
  `messages`, response `choices[].message.content`, effective `model`, optional usage.
- https://openrouter.ai/blog/tutorials/how-to-use-jev/ — Decisions endpoint, state,
  questions, `type: choice`, criteria, `answers.<question>.choice`, confidence/probabilities.
- https://openrouter.ai/typesafe/jev-1.13/ — assigned pinned Jev model page.
- https://openrouter.ai/openai/gpt-6-luna-decisions/providers — assigned Luna model,
  Decisions endpoint, typed question example and response choice/probability fields.
- https://openrouter.ai/cloudflare/clef/providers — assigned Clef ID, Decisions
  endpoint, choice request and answer examples verified through official search results.
- https://openrouter.ai/anthropic/claude-opus-5.5/providers — assigned Claude model
  and chat-completions endpoint example verified; paid account routing remains untested.
- https://openrouter.ai/anthropic/claude-opus-5.5 — official model FAQ explicitly
  confirms JSON-schema structured output via `response_format`.

Some model `/api` pages and the attempted Decisions reference URL were not retrievable.
The Decisions adapter uses the official tutorial and Luna provider-page contract rather
than permissive guesses from the reference parser. The exact four IDs are fixed in code.
No paid call was made as part of this documentation review.

Decisions request: `{model, state, questions: {next_move: {type: "choice", instructions,
criteria: {<18 legal moves>: <definitions>}}}}`. Response must have
`answers.next_move.type == "choice"` and a legal string `choice`.

Chat request: explicit assigned model and shared state/question content. Only an exact
JSON object with one `move` key is accepted. No markdown/code-fence/free-text recovery.
The adapter requests strict JSON-schema structured output with an 18-move enum and
`require_parameters: true`. Official support was verified in the model FAQ; account-specific
route acceptance remains untested. It fails visibly if the requested constraint cannot be
served, without retrying with weaker output or another model. Claude now defaults to `CLAUDE_REASONING_EFFORT=low` and `CLAUDE_MAX_TOKENS=1024`,
recorded in fixed request policy; this is not a promise about actual cost or quality.

Retries: at most configured retries (0–3), only transport failures, malformed responses,
429, 500, 502, 503, 504. Same ID every time. Missing optional confidence/usage stays null.
Effective model ID is retained. The explicit user-reviewed allowlist now accepts
`typesafe/jev-1.13-20260917` only for `typesafe/jev-1.13`, and
`openai/gpt-6-luna-decisions-20261006` only for `openai/gpt-6-luna-decisions`, plus each
assigned ID itself. Clef and Claude permit only their assigned IDs. No prefix matching,
future-date inference or fallback occurs. A valid action without an effective ID fails
closed; a malformed envelope follows existing schema-failure handling. HTTP response bodies are not written to logs, avoiding secret reflection.

Smoke gate: `python verify_live_api.py --confirm-paid` authorizes at most one request per
model (four total), with no retries, while consuming the same persistent application budget.
Valid schema and route access still do not demonstrate cube-solving quality.

## Cost contract verification (2026-10-24)

- Public, unauthenticated `GET https://openrouter.ai/api/v1/models` was executed without
  inference. The assigned Claude ID reports mandatory reasoning; accepted efforts are
  max, xhigh, high, medium, low. Supported parameters include reasoning, max_tokens,
  response_format and structured_outputs. Retained subset: `docs/evidence/openrouter-claude-metadata.json`.
- https://openrouter.ai/docs/guides/best-practices/reasoning-tokens documents effort and
  combined completion/reasoning limits. No `enabled:false`, `effort:none` or guessed
  explicit reasoning budget is sent. `1024` is a ceiling, not a guaranteed valid answer.
- https://openrouter.ai/docs/cookbook/administration/usage-accounting documents automatic
  response usage, native token counts, reasoning tokens and cost; `usage.include` is now
  deprecated and has no effect. The compatible chat opt-in remains; Decisions uses only
  its documented schema and automatic response accounting.
- No paid account/inference compatibility or savings were tested. Billing comes solely
  from the original responses; absent fields are unknown. No extra lookup requests.
- Default retries are zero. HTTP/configuration incompatibility stops later model-puzzle
  requests within the same run; two consecutive unsupported envelopes do the same. Valid
  envelope / bad action quality and token-limit outcomes do not quarantine later puzzles.


## User-observed compatibility corrections (2026-10-25)

The user supplied paid smoke outcomes: Jev and Luna returned HTTP 200 with the two dated
IDs above; Clef returned its assigned ID; Claude returned HTTP 200 / finish_reason=length,
512 completion/reasoning tokens, no final JSON and $0.013768 reported cost. These are
user-reported observations, not an independently rerun four-model test by this patch.

Claude defaults to low effort / 1,024 combined completion tokens / zero retries. The ceiling
is fixed for a run and remains experimental. Last-six executed agent moves is the same
fixed context policy across all four models. Complete gameplay histories remain internal.
No chain-of-thought extraction or prompt leakage was introduced.

Both native Decisions input/output token counts and chat prompt/completion counts normalize
to the same accounting fields. Totals are marked provider-reported or derived; absent values
stay unknown. All billing comes from the original responses; no paid retrieval calls.
Selective smoke tests preserve timestamped reports and consume at most one request per
selected assigned model. No selection retains the four-call maximum. Consent is required
both at the CLI and the smoke function boundary.

A $0.90–$0.95 cumulative no-reset key limit is recommended before a budget-limited benchmark.
See [limits](https://openrouter.ai/docs/api/reference/limits) and
[management-only key updates](https://openrouter.ai/docs/api/api-reference/api-keys/update-keys).
No request-count ceiling guarantees a dollar total or complete five-puzzle evidence.

## Observation policy v4 (offline verified)

New requests use `state-action-v4-facegrids`: the authoritative facelet string plus lossless
slash-separated labeled face grids and exact top/right viewing orientations. Shared
instructions retain the solved goal and HTM; redundant `goal_facelets` and `metric` input
fields are removed. All 18 action definitions remain, with common degree/CW/CCW rules.
The three Decisions payloads differ only by ID; Claude sees equivalent state/question
content with unchanged low/1,024 strict JSON settings. See [policy](PROMPT_POLICY_V4.md)
for the exact prompt and the measured local token-proxy increase. There was no new live
contract test or model-performance validation. A separate, opt-in diagnostic prepares two
first-action states for the three Decisions models only, at most six requests, no retries.
