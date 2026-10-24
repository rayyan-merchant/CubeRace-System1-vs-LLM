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
served, without retrying with weaker output or another model. Claude now defaults to `CLAUDE_REASONING_EFFORT=low` and `CLAUDE_MAX_TOKENS=512`,
recorded in fixed request policy; this is not a promise about actual cost or quality.

Retries: at most configured retries (0–3), only transport failures, malformed responses,
429, 500, 502, 503, 504. Same ID every time. Missing optional confidence/usage stays null.
Effective model ID is retained when returned; an unexpected ID fails closed. Dated alias
canonicalization, if encountered live, requires explicit documented review, never silent
equivalence. HTTP response bodies are not written to logs, avoiding secret reflection.

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
  explicit reasoning budget is sent. `512` is a ceiling, not a guaranteed valid answer.
- https://openrouter.ai/docs/cookbook/administration/usage-accounting documents automatic
  response usage, native token counts, reasoning tokens and cost; `usage.include` is now
  deprecated and has no effect. The compatible chat opt-in remains; Decisions uses only
  its documented schema and automatic response accounting.
- No paid account/inference compatibility or savings were tested. Billing comes solely
  from the original responses; absent fields are unknown. No extra lookup requests.
- Default retries are zero. HTTP/configuration incompatibility stops later model-puzzle
  requests within the same run; two consecutive unsupported envelopes do the same. Valid
  envelope / bad action quality and token-limit outcomes do not quarantine later puzzles.
