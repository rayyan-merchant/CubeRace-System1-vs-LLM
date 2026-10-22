# CubeRace: System-1 vs LLM — Implementation Report

Date: 2026-10-22. Target: `rayyan-merchant/CubeRace-System1-vs-LLM`, branch `main`.
Verified source milestone: `c64dd2e` (engine, adapters, orchestration, UI, tests and setup).
Implementation follows the supplied master brief and all four pages of `assignment-02.pdf`.
The PDF's recording screenshots were also rendered and inspected; their pictured older
model names do not override the four assigned IDs in the PDF's requirements table.

## Acceptance status

| Area | Status | Evidence / boundary |
|---|---|---|
| Original complete local application | PASS | FastAPI API, vanilla frontend, cube engine, orchestration, analysis, persistence and exports |
| Legal cube engine / exact primary reference | PASS | 18 legal moves, HTM, independent PyCuber comparisons, complete capped BFS tests through depth 5 |
| Offline automated tests | PASS | 183 tests; actual output in `docs/evidence/pytest-output.txt` |
| Lint and JavaScript parsing | PASS | Ruff output retained; Node checked both JavaScript modules |
| Full five-puzzle functional benchmark | PASS | 20 simulated trials, zero paid requests, raw JSON and three CSV exports retained |
| Browser verification | PASS | Real headless Edge race/suite/replay/download/abort flows; no page or console errors |
| Four assigned API interfaces | PASS with offline fixtures | Official contracts reviewed; exact routes and IDs, schema validation, retry/cap/failure tests |
| Live routing/account acceptance | BLOCKED | No API key configured; preflight exits BLOCKED before any external request |
| Empirical four-model comparison | BLOCKED | No live trials, performance figures or model winners claimed |
| Student name and roll | PENDING USER INPUT | Conspicuous placeholders; `.env` settings supported across all views |
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
183 passed, 1 warning
All checks passed!
PASS: five seeded puzzles, 20 simulated trials, zero paid requests; exports saved.

python scripts/verify_browser.py
Browser workflow and viewport evidence: docs/evidence/browser-verification.json

python verify_live_api.py --confirm-paid
BLOCKED: configure OPENROUTER_API_KEY, ALLOW_LIVE=true, OPENROUTER_MOCK_MODE=false
```

The last command verified the no-credentials gate; it made zero paid calls. The warning
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
All four arena cards fit within 1366×768 (bottom 736.75 px) and 1920×1080 (bottom 1025 px).
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
marked simulated and retain identity placeholders. They are not live model evaluation
evidence or a substitute for the required student recording.

## Reference and official contract review

The reference repository was studied separately; no reference source, author identity or
performance data was imported. The review confirmed its 60-move setting, model substitution
paths and invented model-specific mock telemetry. See [reference review](docs/REFERENCE_REVIEW.md).

Official OpenRouter documentation/model pages verified the Decisions payload/choice response,
the assigned IDs/routes, chat-completions schema and Claude structured-output support.
Sources and limits are recorded in [the contract review](docs/OPENROUTER_CONTRACT.md).
Page visibility and offline fixtures do not establish account-specific availability.
Unexpected effective model IDs fail closed; dated alias equivalence is not assumed.

## Remaining work requiring real external inputs

1. Privately set the OpenRouter key, `ALLOW_LIVE=true`, `OPENROUTER_MOCK_MODE=false`,
   real `STUDENT_NAME` and `STUDENT_ROLL`; restart the local server.
2. Explicitly authorize the four-call smoke command. Inspect retained response IDs,
   effective IDs and errors in `data/live-smoke.json` before allocating a full suite.
3. Set a sufficient cumulative budget after accounting for smoke/warm-up calls. With one
   retry, five primary puzzles have a maximum of 1,200 requests. The UI requires explicit
   confirmation and a per-run cap. Token cost is not determined by request count alone.
4. Run at least five primary puzzles across all four assigned models. Preserve JSON and
   CSV exports. If routes fail, keep the evidence incomplete and report those failures.
5. Record in-progress and completed stages, then the LIVE primary results slide, keeping
   real student name and roll visible throughout. Review the video and submit it manually.

Operational limits: single local server worker/user, snapshots held in SQLite with bounded
suite size (25); no hosted authentication, deployment, dollar-denominated spend ceiling,
statistical significance test or automated final-video submission. Live outputs may be
malformed, unavailable or unable to solve; those are honest recorded outcomes.
