# CubeRace: System-1 vs LLM — Implementation Report

Initial implementation: 2026-10-22. Cost optimization review: 2026-10-24. API compatibility/budget review: 2026-10-25. Target: `rayyan-merchant/CubeRace-System1-vs-LLM`, branch `main`.
Verified source milestone: `c64dd2e` (engine, adapters, orchestration, UI, tests and setup).
Implementation follows the supplied master brief and all four pages of `assignment-02.pdf`.
The PDF's recording screenshots were also rendered and inspected; their pictured older
model names do not override the four assigned IDs in the PDF's requirements table.

## Acceptance status

| Area | Status | Evidence / boundary |
|---|---|---|
| Original complete local application | PASS | FastAPI API, vanilla frontend, cube engine, orchestration, analysis, persistence and exports |
| Legal cube engine / exact primary reference | PASS | 18 legal moves, HTM, independent PyCuber comparisons, complete capped BFS tests through depth 5 |
| Offline automated tests | PASS | 281 tests; actual output in `docs/evidence/pytest-output.txt` |
| Lint and JavaScript parsing | PASS | Ruff output retained; Node checked both JavaScript modules |
| Full five-puzzle functional benchmark | PASS | 20 simulated trials, zero paid requests, raw JSON and three CSV exports retained |
| Browser verification | PASS | Real headless Edge race/suite/replay/download/abort flows; no page or console errors |
| Four assigned API interfaces | PASS with offline fixtures | Official contracts reviewed; exact routes and IDs, schema validation, retry/cap/failure tests |
| Live routing/account acceptance | PARTIAL | One authorized Claude-only valid response at 1,024 tokens; other adapter changes verified offline |
| Empirical four-model comparison | NOT RUN | No LIVE benchmark or model winner claimed; one adapter smoke is not solving evidence |
| Student name and roll | PASS | Student-authorized Rayyan Merchant · 23K-0073 banner, all tabs and document fullscreen |
| Required final screen recording | MANUAL / NOT CREATED | Recording checklist and results slide implemented |
| Deployment | NOT PERFORMED | User did not authorize deployment |

The software can be rehearsed locally. The assignment's empirical evaluation and human
submission deliverables are not declared complete.

## Implemented behavior

- Original 2x2 arena with isometric SVG cubes, all-face nets, model categories, scramble,
  move histories, measured times/status, race-only ranks, speed control, abort and replay.
- Persistent identity banner, clearly labelled LIVE/SIMULATED source, benchmark table,
  charts, five evidence-driven answers, export links and presentation view.
- Pure standard URFDLB permutations and reproducible scrambles. Suites skip duplicate or
  solved initial states deterministically; actual seeds remain in the evidence.
- Exact bidirectional BFS for warm-up/primary evaluation, depth/node caps, independently
  verified returned paths. Extensions retain null optimum and gap; scramble length is only
  a solution upper bound. Evaluation paths never enter live policy selection.
- Three Decisions adapters and one strict JSON-schema chat adapter, fixed assigned IDs,
  equivalent state/actions/history, no scramble leakage, no model substitution, no permissive
  free-text move extraction, bounded retries and exact 30 executed-action ceiling.
- Per-request monotonic timing, HTTP outcome, retry count, effective ID when returned,
  optional probabilities/confidence/usage and response ID. Unknown metadata stays null.
- Independent per-run model states, concurrent trials, terminal failures, cancellation,
  replayable SSE lifecycle, SQLite snapshots, restart recovery and persistent request budget.
- Mode/tier-separated suite aggregation, explicit denominators and planned counts,
  solved-only proven gaps, raw trial/step/request exports and immutable puzzle provenance.
- Server-side environment key, no browser key entry, no config mutation API, same-origin
  mutation guard, localhost binding instructions, restricted host/content policy and Git ignores.

## Checks actually executed

Environment: Windows, Python 3.10.11, FastAPI 0.119.1, HTTPX 0.28.1, pytest 8.4.2,
Ruff 0.14.1, Playwright 1.56.0 with headless Microsoft Edge. Direct dependency versions
are pinned in the requirements files. No user browser profile was used.

```text
python run_verification.py
281 passed, 1 warning
All checks passed!
PASS: five seeded puzzles, 20 simulated trials, zero paid requests; exports saved.

python scripts/verify_browser.py
Browser workflow and viewport evidence: docs/evidence/browser-verification.json

python verify_live_api.py --models claude --confirm-paid
One authorized Claude-only request with explicit runtime 1024 ceiling: VALID_RESPONSE, HTTP 200
```

The initial no-credentials gate made zero paid calls. The 2026-10-25 Claude-only retest
was separately authorized and billed $0.019908; private .env stayed unchanged. The warning
is a dependency deprecation in Starlette's TestClient reference to AnyIO's BlockingPortal
alias; tests pass. One Windows Proactor socket-reset callback was observed during an
isolated browser run; it is separate from application-page/console errors.

Test coverage includes all actions/inverses/conservation, independent library sequences,
multiple exact-depth cases, proof limits, reproducible puzzles, parsing/duplicate JSON,
non-finite JSON rejection, endpoint/model invariants, no fallback, timeout/retry/cancellation
telemetry, persistent/global/per-run caps, 30 moves, history fairness, SSE replay, abort
isolation, restart recovery, aggregate denominators, extension N/A and exported provenance.

Browser checks cover arena rendering, race, move-limit termination, five-puzzle suite,
analysis, raw downloads, replay, presentation identity, abort control and responsive layouts.
All four arena cards fit within 1366×768 (ready-card bottom 725 px) and 1920×1080 (ready-card bottom 917 px).
The 390×844 mobile layout scrolls vertically without horizontal overflow.
The application preserves a completed server result if Abort is pressed after server
completion while animation is still playing; it stops playback without inventing an abort.

## Retained evidence

- [Automated test output](docs/evidence/pytest-output.txt) and [lint output](docs/evidence/ruff-output.txt).
- [Functional verification summary](docs/evidence/verification.json).
- [Raw simulated suite](docs/evidence/simulated-suite.json), [trial CSV](docs/evidence/simulated-suite.csv),
  [step CSV](docs/evidence/simulated-suite.steps.csv), [request CSV](docs/evidence/simulated-suite.requests.csv).
- [Browser verification](docs/evidence/browser-verification.json).
- [Laptop arena](docs/evidence/arena-1366x768.png), [desktop arena](docs/evidence/arena-1920x1080.png),
  [mobile](docs/evidence/arena-mobile.png), [in progress](docs/evidence/race-in-progress.png),
  [completed](docs/evidence/race-completed.png), [analysis](docs/evidence/analysis-1366x768.png),
  [results slide](docs/evidence/results-slide.png).

These are real local UI screenshots and functional fixture records. They are prominently
marked simulated. Updated recording screenshots carry the student-authorized identity banner. They are not live model evaluation
evidence or a substitute for the required student recording.

## Reference and official contract review

The reference repository was studied separately; no reference source, author identity or
performance data was imported. The review confirmed its 60-move setting, model substitution
paths and invented model-specific mock telemetry. See [reference review](docs/REFERENCE_REVIEW.md).

Official OpenRouter documentation/model pages verified the Decisions payload/choice response,
the assigned IDs/routes, chat-completions schema and Claude structured-output support.
Sources and limits are recorded in [the contract review](docs/OPENROUTER_CONTRACT.md).
Page visibility and offline fixtures do not establish account-specific availability.
Unexpected effective model IDs fail closed; only the two user-reviewed dated aliases are explicitly allowed as of 2026-10-25.

## Remaining work requiring real external inputs

1. Manually change only `CLAUDE_MAX_TOKENS=1024` in the existing private `.env` and restart;
   keep `CLAUDE_REASONING_EFFORT=low`, `API_RETRIES=0` and existing private credentials.
2. Retain prior `data/live-smoke.json` and new timestamped reports. Claude's selective retest
   below is complete; do not repeat it unnecessarily. Only run Jev/Luna-selective verification
   if explicitly authorized. Lower the existing key's total no-reset cap to $0.95 manually.
3. Set a sufficient cumulative budget after accounting for smoke/warm-up calls. With the
   new zero-retry default, five primary puzzles have a maximum of 600 requests (604 including smoke). The UI requires explicit
   confirmation and a per-run cap. Token cost is not determined by request count alone.
4. Run at least five primary puzzles across all four assigned models. Preserve JSON and
   CSV exports. If routes fail, keep the evidence incomplete and report those failures.
5. Record in-progress and completed stages, then the LIVE primary results slide, keeping
   real student name and roll visible throughout. Review the video and submit it manually.

Operational limits: single local server worker/user, snapshots held in SQLite with bounded
suite size (25); no hosted authentication, deployment, dollar-denominated spend ceiling,
statistical significance test or automated final-video submission. Live outputs may be
malformed, unavailable or unable to solve; those are honest recorded outcomes.

## Targeted cost optimization review — 2026-10-24

Findings: Claude previously hard-coded 2,048 completion tokens with default effort; one
retry was the default; usage was retained raw but had no cumulative monetary accounting;
permanent incompatibilities could repeat on subsequent puzzles. Replay/read paths already
avoided inference and remain explicit read-only demonstrations.

Implemented: fixed configurable `CLAUDE_REASONING_EFFORT=low`, `CLAUDE_MAX_TOKENS=512`,
zero default retries, compact equivalent state/action payloads, strict schema/model IDs,
persistent response billing journal, per-model/run/suite cost and token coverage, displayed
request/cost totals and recommended caps, cleared per-run consent, and run-scoped
incompatibility skips with accurate `NOT_RUN` counts. Fixed methodology changes are isolated
from older/different-setting suite aggregates. Existing unknown costs are not rewritten as zero.

The smoke command uses the same Claude settings and journal and remains capped at four
requests with zero retries. At default settings the approved workflow is at most 604
requests: four smoke plus 600 for one five-puzzle suite. Recording, viewing, refresh,
exports and saved-event replay require no new inference. Settings/counters are never
increased or reset automatically. No model substitution, live solution hints, heuristic
failure prediction or per-trial adaptive reasoning/output limits were added.

Contract evidence: public OpenRouter metadata was fetched without authentication or
inference, confirming mandatory reasoning, low effort and supported output parameters.
Automatic response usage is documented; the legacy chat usage opt-in is deprecated/no-op,
and no undocumented field is added to Decisions. See the updated contract review.
The tighter ceiling may truncate output; billed usage is preserved and no automatic retry
or ceiling increase follows. No billable-token saving or quality improvement is claimed.

Verification for this patch uses intercepted HTTP fixtures, including the 604-request
upper-bound workflow, usage on errors, unknown/zero costs, budget exhaustion, no-consent
rejection, schema/permanent error skipping, unchanged fairness, and no inference on reads
or saved live-mode replay. Browser live-mode checks use dummy credentials and MockTransport;
they are explicitly not paid OpenRouter evidence. Actual paid calls: zero.

Final patch verification: `python run_verification.py` passed **196 tests** (one existing
Starlette/AnyIO deprecation warning), Ruff and Node syntax checks, followed by a successful
five-puzzle / 20-trial simulated suite. `python scripts/verify_browser.py` passed desktop,
laptop, mobile, consent, billing and saved live-mode replay checks with zero page/console
errors. The cost-patch browser run intercepted four inference-path calls locally; the expanded UI checks below intercept eight. No real inference.
Restart regression confirms pending journal entries remain counted, attributed to their
run/puzzle and unknown-cost after recovery. Source changes preserve the original engine,
fixed four IDs, 30 moves and strict schema. No live cost or performance savings verified.


## Final recording UI cleanup — 2026-10-24

Scope: frontend presentation, documentation and the isolated browser verifier only. Removed
marketing headlines, assignment/developer reminders, repeated introductions and verbose normal
status copy. Kept the original palette, branding, model cards and cube visualization. Permanent
student-authorized identity: **Rayyan Merchant · 23K-0073**, including document fullscreen.
Server identity metadata remains a separate configuration and is not rewritten by the UI.

The arena heading is Rubik's Cube Benchmark; the analysis heading remains Benchmark Analysis;
the slide heading is Benchmark Results. Its source, difficulty and puzzle count come from
selected aggregates, including honest empty results. Synthetic results retain explicit labels,
assigned model names and no-performance qualifications. Tables retain failure/NOT_RUN counts,
N/A metrics and billing. Longer methodology was moved to README; paid consent and request caps
remain in the live controls. No backend, cube engine, BFS, model ID, prompt, API setting,
reasoning effort, metric calculation, persistence or experimental policy was changed.

Browser verification uses an isolated temporary database, dummy credentials and exhaustive
MockTransport interception. All screenshots labelled offline-live-errors show deliberately
failed HTTP fixtures, not actual OpenRouter measurements. No paid inference or deployment
was performed. Test-only live-mode screenshots carry an OFFLINE UI FIXTURE watermark;
it is added by the screenshot harness and is not part of the application UI.


Recording verification: `python run_verification.py` passed **196 tests**, Ruff and both Node
syntax checks, plus a five-puzzle / 20-trial simulated suite. One existing Starlette/AnyIO
deprecation warning remains. Expanded `python scripts/verify_browser.py` checks actual
1366×768 and 1920×1080 views for all three pages, unscrolled arena cards, unclipped desktop
tables, sticky identity while scrolling and document fullscreen. It also checks difficulty,
seed, scramble generation, six-face expansion, playback, start/abort, running controls,
empty results, selected source/tier and dynamic puzzle counts, simulated completion/move
limit, intercepted live unavailability/NOT_RUN counts, billing, consent, download, saved
replay and refresh without inference. Eight HTTP fixture calls total, zero real OpenRouter
calls, zero page errors and zero console errors. Mobile 390×844 retains vertical scrolling
without horizontal overflow. This establishes UI readiness, not live API availability or
empirical model performance. The final video remains a manual student deliverable.

| View | 1366×768 | 1920×1080 |
|---|---|---|
| Race Arena | [Screenshot](docs/evidence/arena-1366x768.png) | [Screenshot](docs/evidence/arena-1920x1080.png) |
| Benchmark Analysis | [Screenshot](docs/evidence/analysis-1366x768.png) | [Screenshot](docs/evidence/analysis-1920x1080.png) |
| Full analysis page | [Screenshot](docs/evidence/analysis-full-1366x768.png) | [Screenshot](docs/evidence/analysis-full-1920x1080.png) |
| Results Slide | [Screenshot](docs/evidence/presentation-1366x768.png) | [Screenshot](docs/evidence/presentation-1920x1080.png) |
| Fullscreen slide | [Screenshot](docs/evidence/fullscreen-1366x768.png) | [Screenshot](docs/evidence/fullscreen-1920x1080.png) |
| Offline live-mode failures | [Screenshot](docs/evidence/offline-live-errors-presentation-1366x768.png) | [Screenshot](docs/evidence/offline-live-errors-presentation-1920x1080.png) |

Machine-readable browser checks: [browser-verification.json](docs/evidence/browser-verification.json).


## Final OpenRouter compatibility and sub-$1 workflow — 2026-10-25

Changes are limited to adapter validation/context, configuration defaults, billing normalization,
the smoke CLI, tests and documentation. Recording UI, identity, cube engine, reference BFS,
seeds, 30-action allowance, suite execution and metric calculations are unchanged. SQLite
schema and historical data are not migrated or overwritten. Only run policy metadata is extended.

- Exact effective-ID sets allow the assigned Jev ID and `typesafe/jev-1.13-20260917`, the
  assigned Luna ID and `openai/gpt-6-luna-decisions-20261006`, and only the original Clef/
  Claude IDs. Requests retain the four assigned IDs; unrelated/future/prefix matches fail.
  Both requested and effective IDs are retained. Valid moves without effective IDs fail closed.
- Defaults: low Claude effort, 1,024 combined completion/reasoning tokens, zero retries.
  Strict one-move schema and mandatory reasoning remain; output-limit failures never trigger
  parsing of reasoning, automatic retries or automatic increases. The 1,024 setting remains
  experimental. Private `.env` was left unchanged (its ceiling is still 512).
- All four models receive the same last-six executed-move policy, current/goal facelets,
  legal action definitions, HTM and remaining allowance based on the full internal history.
  Full move/step histories remain saved and exported. `state-action-v3-recent6` and request/run
  metadata prevent mixing new results with full-history or different-setting experiments.
  Action descriptions were retained for fair interpretation; no word-level optimization
  was traded for loss of decision information.
- Selective `--models claude` and `--models jev,luna` cap calls at one and two; no selection
  preserves four. CLI/function consent, zero retries and the persistent ledger apply.
  Timestamp + unique-suffix reports use exclusive creation, preserving prior smoke evidence.
  Console/report telemetry includes HTTP, effective ID, outcome, finish reason, usage and cost.
- Decisions input/output and chat prompt/completion usage normalize correctly. Missing totals
  derive only from two known components, labelled `derived` versus `provider`. Missing cost/
  tokens remain unknown; provider costs/raw usage and historical ledger entries are preserved.

Verification: **255 tests passed**, one existing Starlette/AnyIO deprecation warning; Ruff,
Node syntax and a five-puzzle / 20-trial simulated suite passed. Expanded browser verification
passed at both desktop sizes and mobile with zero page/console errors. Its eight inference-path
requests were intercepted offline. The Abort test now waits for terminal status instead of
asserting an intermediate asynchronous state; no recording UI change was made.

### Exactly one authorized paid smoke

After offline checks, one Claude-only request used a fixed runtime 1,024-token override,
low effort and zero retries. It returned **HTTP 200 / VALID_RESPONSE / finish_reason=stop**,
move **F**, requested and effective ID `anthropic/claude-opus-5.5`. Provider-reported usage:
**882 input, 819 completion, 809 reasoning, 1,701 total tokens**, **$0.019908** cost.
No second inference, Jev/Luna retest, paid practice race or LIVE benchmark was run.

Private timestamped report:
`data/live-smoke-20261025T074836541858Z-e67f43de.json`.
Public sanitized [smoke evidence](docs/evidence/claude-selective-smoke-2026-10-25.json)
contains no key. Historical smoke reports and private `.env` were preserved.

A free key-metadata check after the call reported $0.033779438 cumulative spend,
$0.966220562 remaining, $1 lifetime limit with no reset. This inference key cannot update
its own limit; lower the existing total lifetime limit to **$0.95** in OpenRouter settings.
That cap includes past spend; it is not an extra allowance. Leave a margin for concurrent
requests/settlement. No management credentials were requested or persisted.

At the one observed cost, 150 additional Claude decisions alone extrapolate to $2.9862;
882 input and a full 1,024 output tokens at published $4/M and $20/M rates would instead
be $0.024008 per decision. Neither is a performance or future-cost guarantee. A sub-$1
five-puzzle benchmark requires favorable solving/termination behavior and may remain
incomplete when the provider cap is reached. Do not lower one model's 30-action allowance,
substitute results, reset budgets or hide failures. Review before explicitly starting the
single required five-puzzle Primary benchmark, then use free replay for recording.


## Local stale-server investigation — 2026-10-25

The checkout was clean on main at expected commit `4eea3f6274a3d7e30da013838ad9dc951ef4178d`;
fresh GitHub fetch confirmed no divergence. No pull, reset or discarded user changes were
needed. The project venv imports this checkout's `backend/models.py`, with the exact requested
allowlist and `state-action-v3-recent6`. Manager and smoke adapters share Router; no alternate
live validation path was found. The old rejection string does not occur in the current adapter.

The matching saved record is **cf72c4c5a9df468981e4cf617b5f3129**, started **2026-10-25
13:23:12.887522 PKT** (08:23:12.887522 UTC). It is a **five-puzzle LIVE suite**, aborted during
the first puzzle, with per-run request cap 120. It records **state-action-v2-compact**, low
Claude effort, **512 tokens**, zero retries and no six-move policy. The fix commit predates
this run (12:55:49 PKT). This proves an obsolete backend executed the run despite updated
disk code. An unrestarted server is the likely cause. At inspection no Uvicorn process or
listener on port 8000 remained, including elevated CIM/TCP checks; unrelated Colab Python
processes were left alone. The old server's original PID/interpreter/working directory
cannot now be recovered, so an obsolete alternate checkout cannot be ruled out. Replaying
this saved record will correctly continue to show its original errors.

| Model | Recorded status | Requests | Applied valid moves | HTTP / outcome | Known reported USD | Unknown-cost requests |
|---|---|---:|---:|---|---:|---:|
| Jev 1.13 | UNAVAILABLE | 1 | 0 | HTTP 200; old MODEL_ID_MISMATCH | 0.000033054 | 0 |
| GPT-6 Luna Decisions | UNAVAILABLE | 1 | 0 | HTTP 200; old MODEL_ID_MISMATCH | 0.000043100 | 0 |
| Cloudflare Clef | ABORTED | 9 | 8 | 8 HTTP 200 VALID; 1 CANCELLED | 0.000322020 | 1 |
| Claude Opus 5.5 | ABORTED | 3 | 2 | 2 HTTP 200 VALID; 1 CANCELLED | 0.007452000 | 1 |

Jev returned `typesafe/jev-1.13-20260917`; Luna returned
`openai/gpt-6-luna-decisions-20261006`. The requests used their original assigned IDs.
Clef/Claude returned their assigned IDs on successful responses. Cancelled requests have
no returned effective ID or HTTP status. There were zero recorded HTTP-error or malformed
JSON outcomes; the two identity failures were local validation errors before move parsing,
not evidence that the external models were unavailable. Historical decisions are not
reconstructed or rewritten as successes.

Claude executed R, then R'. Its two completed responses report 879 input tokens each,
10 and 11 completion tokens, total 1,779 tokens, and **0 reported reasoning tokens**.
The third request (ledger 18) was cancelled: its usage/cost are unknown. Clef's cancelled
request is ledger 21. This does not prove either cancellation was unbilled. Neither agent
reached 30 moves or completed solving. The other 16 planned trials are NOT_RUN.

Known run cost is **$0.007850174 plus 2 unknown charges**; complete total remains null.
Cumulative application ledger: **21 requests**, **$0.041705624 known plus those 2 unknown
charges**. By model, cumulative known USD: Jev 0.000099078, Luna 0.000129100, Clef
0.000349446, Claude 0.041128000. The persistent limit is **610**, used **21**, remaining
**589**; it was not raised. Five puzzles could require 600 requests at zero retries, so
the existing request budget does not cover the worst case. Lower actual usage may fit,
but a complete five-puzzle result below $1 cannot be guaranteed. Provider spending/limits
were not queried in this investigation. Reconcile the two unknown charges manually in
OpenRouter activity before relying on any dollar remainder.

The private `.env` now already has ALLOW_LIVE=true, OPENROUTER_MOCK_MODE=false,
API_RETRIES=0, CLAUDE_REASONING_EFFORT=low, CLAUDE_MAX_TOKENS=1024. No edit is required or
performed. Student identity remains Rayyan Merchant · 23K-0073. The stale run's 512 ceiling
is historical server configuration, not the current file's setting.

The only runtime addition is non-secret startup identity on existing read-only health plus
`preflight.py`: local-only GETs, read-only DB access, stale commit/policy/source/allowlist/
Python/path/config rejection and request-capacity warnings. No model adapter, prompt,
model-selected move, engine, BFS, 30-action allowance, dataset seed, metric formula,
recording UI, budget, persistence or historical record was changed.

Offline verification additionally exercises the exact UI POST/stream/read/replay/export
routes with dated Jev/Luna IDs, Clef and strict Claude JSON at 1,024 tokens, valid solving
completion, wrong-ID rejection, user abort with pending calls/unknown billing and all four
independent 30-action trials. Browser checks now also complete and replay a LIVE-mode race
using 120 intercepted dated-ID/Claude responses, alongside the existing eight failure
fixtures. All 128 browser requests are offline fixtures, zero actual OpenRouter requests.
Detailed normalized [read-only run audit](docs/evidence/local-run-investigation-2026-10-25.json)
retains the evidence boundary. Final verification: **281 tests passed**, Ruff and Node
syntax checks passed, five-puzzle simulated verification passed, and browser verification
passed with 128 intercepted fixture calls, zero real OpenRouter calls and zero page/console
errors. One existing Starlette/AnyIO deprecation warning remains. Logical row hashing after
the offline checks confirmed that production runs, request records and the budget table
were unchanged. Read-only final server preflight output is retained locally in `data/` after
starting the committed source, without adding a production race or benchmark.

### Follow-up: saved LIVE loop audit and Start/Abort timing

The later aborted primary suite was audited locally without OpenRouter calls. All 67
recorded moves agreed with saved decision events, step states and independent PyCuber
reconstruction; all 71 request contexts agreed with recorded recent history, remaining
allowance and the persistent journal. Raw HTTP bodies were not archived, so transmitted
bytes cannot be independently recovered. Observed loops are preserved model choices.
Luna's HTTP 502 was recorded without retry; aborted and NOT_RUN trials remain incomplete.
Timestamped exports and the detailed audit remain local under ignored `data/audits/`.

Browser verification exposed a separate Start/Abort timing defect: Abort could target a
previous run while the new start request was pending. Start now clears the previous ID
and keeps Abort disabled until the new ID arrives. A Node regression test reproduces the
old failure and passes with the fix; `run_verification.py` includes it when Node exists.
No prompts, model settings, moves, experiment logic or historical results were changed.

Verification: 281 Python tests passed (one existing AnyIO deprecation warning), Node
regression and JavaScript syntax checks passed, Ruff passed, and isolated browser checks
passed with 128 intercepted requests and no console errors. Production database logical
hashes matched before and after export/replay. No paid requests were made. Local runtime
readiness does not guarantee provider availability, solving performance or a sub-$1 suite.

### Observation policy v4 and first-action diagnostics

New policy `state-action-v4-facegrids` retains the authoritative facelet string and adds
lossless labeled 3x3 slash-row grids. Shared instructions define fixed-center color labels,
the exact engine-consistent outside-view top/right neighbors, the whole-cube goal, turn
directions and HTM. Redundant solved-state/metric input fields and repeated action wording
were removed. All 18 actions, last-six history, full internal histories, 30-move allowance,
assigned identities, Claude low/1,024, configured retries and strict parsing are preserved.
No solver hint, heuristic, successor preview, forced loop avoidance or move replacement
was introduced. The existing aggregation condition isolates v4 from historical policies;
the read-only preflight now expects v4 and detects a server still running old source.

`verify_cube_diagnostics.py` previews for free, and requires `--confirm-paid` for at most
six requests: two one-move states for each of Jev, Luna and Clef. Optional depth 2 is a
separate six-request first-action diagnostic. The observer scores only after a response;
neither the generating sequence nor correct actions/scoring data enter model context.
Diagnostics use the persistent request journal/budget, require zero retries, refuse an
active run or insufficient six-request capacity, skip permanent incompatibilities, retain
unknown billing, and save timestamped reports outside benchmark datasets. Claude remains
in the final assignment benchmark. No paid diagnostic or benchmark was executed.

Size measurement is a local **o200k_base proxy**, not provider-billed usage: empty-history
Decisions content is 321 -> 376 tokens; Claude including system text is 329 -> 384.
Six/seven-move histories are 336 -> 391 and 344 -> 399 respectively. Every case increases
55 proxy tokens despite 118 fewer characters. Provider-specific token/cost changes and
model-comprehension gains remain unmeasured. Exact policy, orientation table, commands,
scoring boundaries and size methodology: [PROMPT_POLICY_V4.md](docs/PROMPT_POLICY_V4.md).

Final offline verification: **322 Python tests passed**, Ruff and Node syntax/regression
checks passed, and the isolated five-puzzle/20-trial simulated verification passed. Browser
checks passed for Arena, Analysis, Slide, identity/fullscreen, replay, abort and responsive
views, with 128 intercepted calls, grid reconstruction assertions and no page/console
errors. One existing Starlette/AnyIO deprecation warning remains. Raw local outputs and
screenshots are retained under ignored `data/prompt-v4-verification/`; committed
[verification summary](docs/evidence/prompt-v4-verification.json) and
[size comparison](docs/evidence/prompt-v4-size-comparison.json) retain the evidence boundary.
Production runs, request journal and budget rows have matching before/after logical hashes;
the persistent counter remains 92. The private `.env` was not modified. Restart any
existing server to load v4 before an explicitly authorized future paid run.

### v4 diagnostic investigation and v5 general mechanics

The saved six-request v4 first-action diagnostic was audited without inference. Jev's
correct-action probabilities were 2% (tied rank 11) and 8% (tied rank 4); Clef's were
4.92% (rank 6) and 5.10% (tied rank 9). Response confidence is distinct from correctness
probability. Four valid but incorrect actions remain unchanged; Luna's two HTTP 502
responses remain infrastructure errors with unknown billing and no action/probabilities.
Existing logs/journal do not retain the raw error bodies/provider request IDs, so the
exact upstream cause cannot be established. Official OpenRouter documentation classifies
502 as model unavailability or an invalid upstream response, not proof of any one cause.

v4 explains orientation/direction but omits explicit adjacent-strip transfers and their
reversals. New `state-action-v5-permutations` appends only general sticker-permutation
rules: two common face cycles, six CW strip cycles, and their prime/half-turn composition.
The rules describe the environment for every possible state; they contain no current-state
successor, reference solution, heuristic, move preference or recommendation. The live
engine and every model-selected action are unchanged. All four models get equivalent
rules; assigned IDs, 30-action allowance, history, retries and Claude low/1,024 stay fixed.

v4 payloads remain available for offline baseline construction, with a frozen pre-change
hash regression. Historical v4 reports and benchmark conditions remain separate and intact.
The read-only preflight now expects v5; any existing server must restart to load it.
The local o200k_base proxy adds **148 tokens**: empty-history Decisions 376 -> 524, Claude
384 -> 532; six/seven-history comparisons have the same delta. Provider-specific overhead,
v5 model accuracy and cost are unmeasured. This is not a claimed fix for Luna's 502.

Verification: **360 Python tests passed**, Ruff and Node syntax/regression passed, the
isolated five-puzzle/20-trial simulated suite passed, and browser checks passed with 128
intercepted responses and no page/console errors. New tests reconstruct all 18 complete
permutations from the declared cycles on unique sticker identities and cross-check
scrambled transitions against PyCuber. One existing Starlette/AnyIO warning remains.
The production runs/request/budget logical hash and original diagnostic report hash match
their before snapshots; the persistent counter remains 98. No paid diagnostic, API retry,
model substitution or LIVE benchmark was executed. No private `.env` change was made.

Detailed [investigation and exact v5 addition](docs/V4_DIAGNOSTIC_AUDIT_AND_V5.md),
[probability audit](docs/evidence/v4-diagnostic-audit.json),
[token comparison](docs/evidence/prompt-v5-size-comparison.json) and
[verification summary](docs/evidence/prompt-v5-verification.json) are retained.
Raw local verification outputs/screenshots are in ignored `data/prompt-v5-verification/`.

### Optional native OpenAI Luna diagnostic

`verify_luna_openai.py` adds an explicitly opt-in, separate native diagnostic at
`https://api.openai.com/v1/decisions`, requesting only `gpt-6-luna` with server-side
`OPENAI_API_KEY`. The native input-json/question/choice/answer-array contract was checked
against the official OpenAI guide and API reference; it was not exercised on a live account.
The two existing one-turn states, exact frozen v4 state/instructions and all 18 ordered
action definitions are translated without adding v5 rules or solution information.

Default invocation is a free preview without database access or HTTP. `--confirm-paid`
allows at most two requests, no retries, no redirects or fallback, and requires the shared
live/zero-retry settings plus a native key. Each attempted call consumes the existing
persistent budget under `openai-direct/gpt-6-luna`. Reports are uniquely timestamped under
ignored `data/direct-openai/`, with no benchmark run insertion or OpenRouter adapter change.
Requested/effective identity, provider, native probabilities, confidence, request latency,
HTTP/API errors, request ID and native token usage are retained. Refusals and NOT_RUN
remain separate; model-selected moves are strictly validated and never corrected.
Missing USD costs remain unknown. Native reasoning details are mapped only in the local
accounting copy, while original usage is retained. Reflected credentials are redacted
before persistence; authorization headers and actual keys are never written to reports.
Cancellation preserves charged-request accounting and partial evidence.

Verification: the full offline regression run passed **413 tests**, Ruff, Node syntax/
regression checks, and the isolated simulated suite. Browser checks passed with 128
intercepted calls and no page/console errors. After the final optional-null-error handling
adjustment, all **53 native diagnostic tests** passed again. One existing Starlette/AnyIO
deprecation warning remains. Production database logical hashes match the starting
snapshot and the persistent request counter remains 98. The private `.env` was not
modified; `.env.example` adds only an empty optional native-key slot. No paid OpenAI or
OpenRouter inference was made, and no native API availability or solving result is claimed.

See [native contract, commands and evidence boundaries](docs/DIRECT_OPENAI_LUNA_DIAGNOSTIC.md)
and the [offline verification summary](docs/evidence/direct-openai-verification.json).
Raw local outputs/screenshots remain under ignored `data/direct-openai-verification/`.

## Direct Luna refusal investigation (October 25, authorized live checks)

The key was functional; a shipping/billing control returned the correct choice. Sending
v4 cube information as plain-text JSON still produced a typed refusal. The existing v5
mechanics policy returned valid but incorrect first actions on both diagnostic states
(`F`, `R'`). This verifies those responses, not improved solving or guaranteed future
availability. Four authorized calls consumed 1,493 provider-reported input tokens; all
USD costs are unknown. They were recorded as ledger entries 101–104, separate from
assignment benchmark results. No OpenRouter inference was performed.

The optional native CLI adds explicit fixed `--policy v4|v5` and `--case all|1|2`
selection. Defaults preserve v4 baseline behavior. Selected-case request ceilings,
remaining-budget guards, policy-specific report names, native answer retention and
status summaries are covered by offline tests. No key, `.env`, assignment adapter,
UI, model identity, mechanics, or historical result was changed. See
[diagnostic investigation](docs/DIRECT_OPENAI_LUNA_DIAGNOSTIC.md#authorized-live-investigation--october-25-2026).

Validation after the investigation: **418 tests passed** (one existing Starlette/AnyIO
deprecation warning), Ruff passed, Node regression and syntax checks passed. Isolated
browser verification passed with 128 intercepted fixture requests, zero real OpenRouter
requests, and no page/console errors. Raw browser evidence is under ignored
`data/luna-refusal-verification/docs/evidence/`. The production counter is 104 with 506
requests remaining under the unchanged configured cap. This is a request cap, not a USD
spending cap. Public live diagnostic evidence is in
`docs/evidence/direct-openai-refusal-investigation.json`; raw reports remain local.

## Configurable small suites

Removed the five-puzzle API minimum and aligned the UI with the existing 1–25 puzzle
schema. Three-puzzle suites now work; the default remains five. The assignment's required
sample and existing analysis threshold remain documented and unchanged. Actual puzzle
counts, per-model 30-action allowances, paid consent, budget exhaustion and statistics
continue to use the selected size. Three puzzles recommend 360 requests with zero retries;
an explicitly lower cap is honored and can produce incomplete trials.

Validation: 422 tests passed (one existing dependency deprecation warning), Ruff and Node
checks passed. An isolated Edge browser completed a three-puzzle simulated suite with
no page errors. A mocked live API test accepted the exact reported three-puzzle request
and retained all 12 model trials. No paid inference occurred. Screenshot retained locally
at `data/three-puzzle-verification/three-puzzle-analysis.png`.

### Analysis for small LIVE suites

Follow-up: removed the separate five-attempt analysis gate as requested. All five
questions now describe available live observations even for three-puzzle suites, with
actual sample counts and an explicit small-sample qualification. Missing model results
remain unknown, simulated fixtures remain non-evidence, and zero solved trials produce
an explicit unavailable shortest-solution comparison rather than a fabricated winner.
The five-puzzle assignment recommendation remains separate from displaying descriptive
results. Regression coverage includes three-puzzle samples with zero/one successes and
empty/unequal model coverage. Isolated Edge verification confirmed all five answers in
both Benchmark Analysis and Results Slide for a three-puzzle mocked live suite, with
12 intercepted HTTP-502 fixtures and zero paid calls. Screenshots remain local under
`data/three-puzzle-verification/`.

Final verification for the combined small-suite and analysis updates: **425 tests passed**,
Ruff passed, JavaScript checks passed, and the targeted browser checks passed. One existing
Starlette/AnyIO deprecation warning remains. All verification used fixtures or simulation.

## Production Luna route correction (October 26, 2026)

The earlier integration was diagnostic-only and did not change the race adapter. That
was the cause of the screenshot still showing OpenRouter HTTP 502. Per the explicit
request to use the OpenAI key for Luna, production environment startup now defaults
LUNA_PROVIDER to openai and uses OPENAI_API_KEY for Luna in both races and suites.
Jev, Clef and Claude remain on OpenRouter. No private environment file or API key was
modified; a safe presence/configuration check found both keys and the native route ready.

The production router and diagnostic CLI share a strict native Decisions parser. The
native payload translates the same fixed v5 observation/instructions/actions, including
six recent moves and the remaining 30-action allowance. Each request records the logical
assigned ID, native requested/effective ID, provider route, endpoint, response identity,
probabilities and response-reported usage. Reasoning details are normalized without
inventing USD costs. Refusals execute no move; unavailable identities and repeated
unsupported schemas fail closed. Native credential absence blocks live admission before
any other model can be charged. No automatic provider fallback exists.

The UI labels the native Luna route in live controls/cards, saved runs and result
provenance. Historical request records retain their original route during replay.
The provider route is part of saved experimental-condition metadata, so native-Luna
and historical OpenRouter-only suites are not silently pooled. This is a documented
provider deviation, not a claim that the OpenRouter endpoint was fixed. The application
retains the four logical model slots; the native model ID is explicitly gpt-6-luna.

All new verification used intercepted HTTP/fixtures, with no paid inference. Routing
tests cover UI start, three-puzzle suites, full 30 actions, six-move history, mandatory
consent, missing keys, identity/schema/refusal/HTTP failures, billing, cancellation,
and read-only replay/exports. Browser native Start/Replay verified four fixture calls:
Jev/Clef/Claude to OpenRouter and Luna to OpenAI, zero additional calls on replay and no
page errors. Screenshot: data/native-luna-race-verification/native-luna-race.png.

Verification completed: full regression run **433 passed**; after adding suite/cancellation
coverage and final CLI credential guards, **82 targeted tests passed**, including all
10 native production-route tests. Ruff and Node regression/syntax checks passed.
Full isolated browser verification passed (128 intercepted fixtures, no real provider
calls or page/console errors), as did the separate native Start/Replay browser check.
One existing Starlette/AnyIO dependency deprecation warning remains. No paid calls were
made during this correction. The private .env was not modified.
