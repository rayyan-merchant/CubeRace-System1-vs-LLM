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

The initial implementation verified the request/response shape against documentation and
fixtures only. The authorized live investigation below subsequently verified account access
and specific responses; it does not establish reliable cube solving or future availability.
The implementation uses existing `httpx`, without SDK retry behavior or new dependencies.

## Exact v4 observation parity

By default, `native_payload()` builds the frozen v4 payload first, then translates only its interface:

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
rules are absent unless explicitly selected with `--policy v5`. With that option, the
instructions match the existing shared v5 policy exactly, including its general turn rules.
The CLI uses the existing two one-turn diagnostic states,
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

Reports have unique timestamped paths under ignored `data/direct-openai/luna-v4-*.json`
or `luna-v5-*.json`, according to the explicit selection.
They record the direct endpoint/provider, requested/effective model, selected fixed policy,
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

## Authorized live investigation — October 25, 2026

The user's original v4 run returned HTTP 200 with typed refusals for both questions.
No key replacement was necessary. Four subsequently authorized direct requests isolated
access from cube behavior (each was reserved in the persistent request ledger, no retries):

| Ledger | Check | Outcome | Provider input tokens |
|---|---|---|---:|
| 101 | Small shipping/billing classification control | Correct `shipping` choice | 122 |
| 102 | First v4 cube state as equivalent plain-text JSON | REFUSED | 107 |
| 103 | First cube state with existing v5 mechanics instructions | Valid `F`, incorrect | 635 |
| 104 | Second cube state through CLI `--policy v5 --case 2` | Valid `R'`, incorrect | 629 |

All responses were HTTP 200 and identified `gpt-6-luna`. The four calls reported 1,493
input tokens, zero output/reasoning tokens, and no monetary costs. Costs remain unknown;
provider usage is not a dollar receipt. These are diagnostic observations, not benchmark
results or proof of a causal explanation for v4 refusals or historical OpenRouter 502s.
The refusal schema provides no explanation. Neither text serialization nor replacing the
key is an evidence-supported fix. V5 produced answers in these two checks but did not
solve either state; future refusals and incorrect moves remain possible.

The CLI now accepts explicit `--policy v4|v5` and `--case all|1|2`. The defaults remain
v4 and both states, so old commands do not silently switch experimental conditions.
Selection is fixed before requests; there is no adaptive policy or provider fallback.
A single selected case requires and consumes at most one remaining request. Both cases
require at most two. Preview remains free, and `--confirm-paid` remains mandatory:

```powershell
# Free preview of v5:
.venv\Scripts\python.exe verify_luna_openai.py --policy v5
# Only with approval: both states, at most TWO paid requests:
.venv\Scripts\python.exe verify_luna_openai.py --policy v5 --confirm-paid
# Only with approval: one selected state, at most ONE paid request:
.venv\Scripts\python.exe verify_luna_openai.py --policy v5 --case 2 --confirm-paid
```

Reports use policy-specific filenames (`luna-v4-*` / `luna-v5-*`), retain the chosen
policy in every request record, and now retain redacted native `provider_answers`,
including typed refusals. CLI summaries explicitly print statuses, avoiding ambiguity
between wrong moves and no returned move. Original reports and benchmark runs are
unchanged. The assignment OpenRouter adapter, four identities, fixed prompts, 30-action
allowance, Claude settings, UI, and private `.env` are unchanged.

Raw authorized evidence remains under ignored `data/direct-openai/`:
`access-control-20261025T165858929254Z.json`,
`cube-text-transport-20261025T165916698607Z.json`,
`cube-v5-check-20261025T165941614602Z.json`, and
`luna-v5-20261025T170044448943Z-c134b697.json`.
