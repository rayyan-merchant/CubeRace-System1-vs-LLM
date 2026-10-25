# v4 diagnostic audit and v5 general turn mechanics

The saved six-request v4 diagnostic was inspected offline, without any new OpenRouter
calls. Source: `data/cube-diagnostic-depth1-20261025T141601182507Z-4c4575df.json`,
diagnostic ID `diagnostic-4c20fa8a2c154a9797d1c3ae4c4575df`. Its original JSON and journal
remain unchanged. A [normalized audit](evidence/v4-diagnostic-audit.json) includes source
hash, selected probabilities, confidence, tied ranks, HTTP timing and reported billing.

## Probability findings

The correct action is used only by the observer to audit ranks; it is never model input.
Competition rank is one plus the number of strictly higher probabilities. A tied range
shows every position occupied by that probability, rather than breaking ties arbitrarily.

| Model | Case | Chosen | Chosen probability | Correct-action probability | Correct-action rank | Response confidence |
|---|---|---|---:|---:|---|---:|
| Jev | 1 | U2 | 18% | 2% | 11th, tied positions 11–14 | 0.13 |
| Jev | 2 | U2 | 15% | 8% | 4th, tied positions 4–6 | 0.10 |
| Clef | 1 | U' | 26.57% | 4.92% | 6th | 0.2225 |
| Clef | 2 | R' | 11.32% | 5.10% | 9th, tied positions 9–10 | 0.061 |
| Luna | 1 | No action; HTTP 502 | Unknown | Unknown | Unknown | Unknown |
| Luna | 2 | No action; HTTP 502 | Unknown | Unknown | Unknown | Unknown |

These are probabilities over allowed choices, not probabilities of solving. Response
confidence describes the returned decision distribution/selected choice; the API does not
provide a separate confidence for the correct action. The low correct-action ranks do not
support rescuing results by selecting a runner-up or forcing another move. All four valid
actions were legal and were preserved unchanged. There were zero correct actions among
four valid responses, with two infrastructure errors out of six planned calls. This is
not a completed assignment benchmark or evidence that Luna selected an incorrect action.

The diagnostic reports $0.00012978 known cost and two requests with unknown cost. No new
charges were incurred for this investigation. The persistent request count remains 98.

## Prompt audit and technical justification

v4 specifies all six face grids, their outside-view orientation, the target and the meaning
of CW/CCW/180-degree turns. It does **not explicitly describe the sticker permutations**:
which neighboring rows/columns move, whether their order reverses, and how the turned
face rotates internally. The model must infer those mechanics from the notation.
This is a specific specification gap, not proof that it caused all observed bad choices.

v5 appends only state-independent rules for those mechanics. A single pair of cycles
describes the eight moving stickers on any turned face. Six ordered strip cycles describe
adjacent transfers for the six CW quarter-turn generators. Prime moves reverse the
cycles; half-turns repeat CW twice. This factors repeated mechanics instead of supplying
18 full 54-sticker tables. No dynamic field, computed successor, preference, solved-distance
hint, heuristic score, inverse-scramble policy or recommended move is added.

## Exact added rules

```text
 Cells 1-9 are row-major per face. CW source>destination cycles wrap last>first; copy old stickers simultaneously. On the turned face: 1>3>9>7,2>6>8>4. Adjacent strips (digits are cells; map position-wise): U:R123>F123>L123>B123;R:U369>B741>D369>F369;F:U789>R147>D321>L963;D:R789>B789>L789>F789;L:U147>F147>D147>B963;B:U123>L741>D987>R369. Unlisted cells stay fixed. Prime reverses CW cycles; 2 repeats CW twice.
```

For example, a generic strip transfer `R123>F123` means old R1/R2/R3 copy to F1/F2/F3.
It is a rule of the environment and contains no current sticker values. Transfers within
a cycle occur simultaneously, including its last-to-first transfer. Unlisted cells,
including centers, stay fixed. Existing v4 grid orientations still apply.

## Policy and baseline boundaries

New requests use `state-action-v5-permutations` and record
`turn_rules_version=singmaster-sticker-cycles-v1` in request/run metadata. The three
Decisions models retain identical state, question and criteria; Claude receives equivalent
information through the unchanged chat/strict-JSON interface. Model IDs, low/1,024 Claude
settings, retries, history policy, 30-action limit and model-selected actions are unchanged.

The exact v4 instructions remain `V4_INSTRUCTIONS`. Offline callers can construct the
unchanged baseline with `payload(..., policy_version="state-action-v4-facegrids")`;
unknown policy names are rejected. The live Router uses v5, without automatic fallback or
adaptive policies. A frozen hash regression verifies all four v4 payloads at history lengths
0, 6 and 7 against their pre-change snapshot. Existing saved v4 results are not rewritten.
Aggregation continues isolating policy/settings conditions, and replay makes no inference.

## Token overhead

[Local measurements](evidence/prompt-v5-size-comparison.json) use the same fixture and
cached `tiktoken 0.12.0 / o200k_base` proxy as the earlier comparison, with no network.
They cover compact state/question JSON plus Claude's unchanged system text, excluding
provider framing and schema overhead:

| Model content | History length | v4 proxy tokens | v5 proxy tokens | Added |
|---|---:|---:|---:|---:|
| Each Decisions model | 0 | 376 | 524 | 148 |
| Each Decisions model | 6 or 7 | 391 | 539 | 148 |
| Claude including system text | 0 | 384 | 532 | 148 |
| Claude including system text | 6 or 7 | 399 | 547 | 148 |

The saved paid v4 responses reported Jev inputs of 847/843 tokens and Clef inputs of
706/694 tokens; these differ from the local proxy. Do not add 148 to those counts and
claim a provider-specific prediction. Actual v5 usage, cost and accuracy are unmeasured.
The 412 added characters encode complete turn mechanics, not a claim of token savings.

## Luna HTTP 502 evidence and limits

Requests 94 and 97 returned HTTP 502 after about 1.298 and 0.775 seconds, respectively.
Both have `HTTP_ERROR`, no usage, probabilities, response ID or effective model ID, and
retry 0. The local HTTP error branch ran before action parsing or model-ID validation;
these are not invalid-move, alias-rejection or local 30-second timeout events. The existing
journal also contains 12 valid Luna responses and an earlier v3 HTTP 502, so these two
errors do not establish that the assigned ID is invalid or that v4 introduced the problem.

OpenRouter's [official error documentation source](https://github.com/OpenRouterTeam/docs/blob/main/api_reference/errors-and-debugging.mdx)
describes 502 as the chosen model being down or an invalid response being received from it.
The [assigned Luna model page](https://openrouter.ai/openai/gpt-6-luna-decisions/providers)
still describes a Decisions model accepting structured state and typed choice questions.
Documentation visibility is not proof of present account-specific availability.

The saved records do not contain raw error bodies, typed provider error codes/messages,
provider response headers or upstream request IDs. Existing local server logs contain no
body for these diagnostic errors. Therefore outage, upstream refusal, translation failure
or another provider-response defect cannot be distinguished. In particular, neither
"temporary outage" nor "prompt caused refusal" is established. No paid retries, model
substitution, endpoint change or logging-policy change was used to manufacture an answer.
v5 is not a claimed remedy for Luna's 502.

## Offline validation

Tests decode the declared cycles into source-to-destination mappings on all 54 unique
sticker identities, then compare all 18 actions with the engine's exact permutations.
They also apply the decoded rules to scrambled states and independently compare every
facelet with PyCuber. Additional tests check unchanged state fields and criteria, identical
rules for all four models, fixed v4 baseline bytes, unknown-policy rejection, and separate
policy aggregation. Existing diagnostics, billing, budget, abort, replay and browser
regressions run with intercepted responses only. This establishes rule correctness,
not improved external model performance. No paid diagnostic or LIVE benchmark was run.
