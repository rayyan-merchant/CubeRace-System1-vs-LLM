# Optional direct OpenAI Luna diagnostic

This CLI is a separate provider diagnostic, not an assignment benchmark, provider fallback
or replacement for `openai/gpt-6-luna-decisions`. The existing four-model OpenRouter
registry, v5 live policy, adapters, cube engine and saved runs remain unchanged.

## Official contract verification

Reviewed against the [OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions)
and [Create a decision reference](https://developers.openai.com/api/reference/resources/decisions/methods/create).
Those sources document `POST https://api.openai.com/v1/decisions`, model `gpt-6-luna`,
and Bearer authentication using `OPENAI_API_KEY`. Native messages support user-role
`input_json` parts with structured `data`. Questions are an array, and a choice question
uses `choices: [{value, description}]`. Responses have ordered `answers` arrays; choice
probabilities are arrays of `{value, probability}`, and a question may return a typed
`refusal`. Usage includes input/output/total tokens, input cache details and output
reasoning details. The documented usage object has no USD-cost field.

This verifies the implemented request/response shape against documentation and fixtures.
It does not establish account access, live endpoint availability or successful inference.
The implementation uses existing `httpx`, without SDK retry behavior or new dependencies.

## Exact v4 observation parity

`native_payload()` builds the frozen v4 payload first, then translates only its interface:

```text
model = gpt-6-luna
input[0] = {role: user, content: [{type: input_json, data: <exact v4 state>} ]}
questions[0] = {
  type: choice,
  name: next_move,
  instructions: <exact v4 instruction string>,
  choices: [{value: <move>, description: <exact v4 criterion>}, ...all 18 in order]
}
```

The authoritative 54 stickers, labeled face grids, empty agent history, 30 remaining
actions, orientations, goal and all 18 action definitions match v4 exactly. v5 permutation
rules are deliberately absent. The CLI uses the existing two one-turn diagnostic states,
not a new puzzle generator. Neither scramble sequences, correct actions, scores nor
successor previews are sent. First-action scoring happens only after a valid response,
without changing the selected move or requesting a second action on that state.

## Execution and configuration

Run from the repository root. Preview without credentials, database access or HTTP:

```powershell
.venv\Scripts\python.exe verify_luna_openai.py
```

Only after explicitly approving direct paid execution:

```powershell
.venv\Scripts\python.exe verify_luna_openai.py --confirm-paid
```

Runtime configuration requires server-side `OPENAI_API_KEY` and the existing shared
`ALLOW_LIVE=true`, `OPENROUTER_MOCK_MODE=false`, `API_RETRIES=0` controls. The mock-mode
flag retains its existing name but also guards this optional CLI. No OpenRouter key is
needed for direct calls. `.env.example` contains an empty optional `OPENAI_API_KEY` slot;
the existing private `.env` was not modified. There is no key command-line argument,
frontend setting, automatic key provisioning or request during preview.

The command makes **at most two** sequential requests, one per state, without retries,
redirect following, provider substitution or automatic benchmark execution. It refuses
an active saved run or fewer than two remaining persistent requests. Each attempt is
reserved atomically in the existing request counter/journal before sending; caps are
never reset or increased. Another invocation requires explicit authorization again and
consumes the remaining shared budget. Permanent HTTP incompatibility, identity mismatch
or unsupported response shape stops the second request, marking its case NOT_RUN.
HTTP 502, transport failures and refusals are recorded; another diagnostic state is a
distinct first-action request, not a retry of the failed state.

Direct OpenAI charges are separate from OpenRouter. An OpenRouter key spending limit
does not cap these direct-provider charges. No dollar estimate or extra billing request
is made; missing response-reported costs remain unknown.

## Validation and retained evidence

The returned model must be exactly the documented `gpt-6-luna`; missing/unrecognized
identities fail closed, without broad alias matching. The sole answer must be named
`next_move`, have native type `choice` or `refusal`, and a valid choice must be exactly
one of the 18 legal strings. No stripping, prose extraction, probability sampling or
move replacement occurs. Choice metadata must contain finite 0–1 confidence and one
finite 0–1 probability per legal option, with no duplicate values. Probabilities are
recorded unchanged, not normalized or interpreted as solving probabilities.

Reports have unique timestamped paths under ignored `data/direct-openai/luna-v4-*.json`.
They record the direct endpoint/provider, requested/effective model, frozen v4 policy,
HTTP status, `x-request-id` when available, measured request latency, native probabilities,
confidence, token usage, first-action correctness and failure statuses. HTTP latency
ends when the response arrives, before parsing or observer scoring. Refusals remain
REFUSED, invalid actions remain errors, and correct/valid/planned counts are separate.
Cancellation keeps the attempted request counted, preserves its unknown billing and
saves partial evidence, with unattempted cases NOT_RUN.

Only selected API-error fields (`type`, `code`, `message`, `param`) are retained, with
credential redaction before persistence. Authorization headers are never logged. Native
usage is preserved as `provider_usage`; the accounting copy adds the existing canonical
reasoning-details alias so the common billing code can read `output_tokens_details`.
No token totals or monetary costs are invented; derived totals retain their existing
source label when the provider omits a total.

Records use the distinct ledger key `openai-direct/gpt-6-luna`, with
`provider_route=direct_openai_decisions`. They consume the existing application-wide
request budget and appear separately in cumulative billing, but never create a saved
benchmark run, enter the four-model comparison, or change prior OpenRouter results.
Reading these files is free; there is no replay or dashboard inference hook for them.

Offline tests intercept all HTTP and cover native schema parity, all legal actions,
strict illegal-action/metadata rejection, explicit consent and configuration guards,
two-request ceiling, zero retries, request IDs/errors/redaction, refusals, unavailable
identity, redirects, cancellation, usage, unknown costs, persistence and historical
OpenRouter isolation. Test credentials/responses are fixtures, not live API evidence.
