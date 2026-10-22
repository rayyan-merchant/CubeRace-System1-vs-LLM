# CubeRace: System-1 vs LLM

An original local Rubik's Cube racing application for AI Engineering Assignment 02.
Four concurrent agents receive the same cube and choose one move at a time. The arena,
benchmark dashboard and recording slide distinguish **LIVE** evidence from **SIMULATED**
functional fixtures throughout.

**Readiness:** local implementation and verification evidence are described in
[IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md). Live four-model performance,
student identity and the final screen recording require real user inputs. No model
performance is implied by the included simulated sample.

## Start locally

Python 3.10+ is required. Node.js is optional for JavaScript syntax verification.
Run all commands from this repository's root. No frontend build or external fonts/CDN needed.

Windows PowerShell:

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Use one server worker. `requirements.txt` alone installs the
runtime; the development file adds tests, lint, independent cube verification and Playwright.
The default is simulated and costs nothing. Opening a tab or reading statistics never
starts paid work. Set `STUDENT_NAME` and `STUDENT_ROLL` in the server `.env` and restart
to replace the conspicuous identity placeholders. Do not copy the reference student's identity.

## Using the application

1. Select warm-up (3–4 turns), primary (4–5), or extension (15–20), and a reproducible seed.
2. Generate Scramble creates the shared legal state. The proven primary distance appears
   separately; extension distance is N/A. The scramble is visible to viewers, never live agents.
3. Start Race launches four independent attempts. Cards show the cube, actual chosen moves,
   status, elapsed attempt time and request latency. Expand each net to inspect all six faces.
4. Playback speed only paces the browser event queue; it never changes measurements or API rate.
5. Abort cancels active requests and records terminal states. A second run cannot overlap an
   active run. Disconnecting a viewer releases its stream; the explicit server job continues
   and can be reconnected or aborted. Budget consumption never resets automatically.
6. Benchmark Analysis starts suites of 5–25 puzzles from the selected seed, tier and source.
   Seeds with duplicate/solved states are skipped deterministically to keep puzzles distinct.
   All four agents receive every puzzle. Select LIVE or SIMULATED evidence independently;
   primary, warm-up and extension statistics are separate. Single races are excluded.
7. Saved runs support replay, full JSON, trial CSV, move-step CSV and request CSV exports.
8. Results Slide uses the currently selected analysis source and tier, with identity always
   visible. Full-screen uses the entire document to retain the identity banner.

Simulation uses deterministic **synthetic-fixture-1…4** agents. The four cards remain assigned
model slots, visibly marked as synthetic. Scripts include inverse moves and deliberate
detours/failure solely to exercise updates, completion, gaps and the 30 limit. These scripts
are never called by live policy selection. Simulated API request latency stays N/A; actual
local fixture elapsed time is wall time, not invented model latency or empirical performance.

## Assigned models and live access

| Assigned model | Fixed ID | Interface |
|---|---|---|
| Jev 1.13 | `typesafe/jev-1.13` | Decisions |
| GPT-6 Luna Decisions | `openai/gpt-6-luna-decisions` | Decisions |
| Cloudflare Clef | `cloudflare/clef` | Decisions |
| Claude Opus 5.5 | `anthropic/claude-opus-5.5` | Chat completions |

Decisions: `POST https://openrouter.ai/api/alpha/decisions`.
Chat: `POST https://openrouter.ai/api/v1/chat/completions`.
See [verified official contracts and remaining live checks](docs/OPENROUTER_CONTRACT.md).
No model override, fallback or automatic live-to-mock conversion is implemented.
An HTTP error or unexpected effective ID remains visible; it never becomes another model's result.

To enable live mode, privately edit `.env`:

```dotenv
OPENROUTER_API_KEY=<your-private-key>
ALLOW_LIVE=true
OPENROUTER_MOCK_MODE=false
API_CALL_BUDGET=1200
API_RETRIES=1
```

Restart the server. The key stays on the server and is never sent to the browser. Confirm the
one-call-per-model smoke test before a full evaluation:

```powershell
.venv\Scripts\python.exe verify_live_api.py --confirm-paid
```

This command has no retries, at most four charged requests, and writes `data/live-smoke.json`.
It tests routing/schema, not solving. On Unix use `.venv/bin/python`. The main UI live start
requires checking an explicit paid-call authorization and a positive per-run cap.

Worst case calls = puzzles × 4 × 30 × (1 + retries). At one retry, a race is at most 240 and
a five-puzzle suite 1,200 requests. Token cost is model/response dependent: a request cap is
not a dollar cap. The lower of persistent and per-run remaining budgets governs every request,
including malformed responses, failed requests and retries. The persistent counter lives in
SQLite; restarting/replaying does not reset it. Increasing `API_CALL_BUDGET` explicitly raises
the cumulative ceiling. Preserve the database between live sessions.

## Metrics and fairness

- **State/actions:** 54 facelets, row-major URFDLB, fixed color centers; exactly 18 legal
  Singmaster actions. Half-turn metric (HTM): `R2` is one action. Every trial has exactly
  the same 30-action ceiling; early solves finish immediately.
- **Inputs:** identical initial states, current facelets, full agent-only history, goal,
  remaining moves and 18 action descriptions. Initial history is empty. No scramble,
  reference solution, search, heuristic or inverse-scramble hint enters a live request.
- **Optimum:** capped complete bidirectional BFS (depth 5, 150,000 states), isolated in
  puzzle preparation. Every returned solution is executed and checked. Proof-cap failure
  is explicit and prevents claiming a primary distance. Extension optimum is null;
  scramble length is stored only as a solution upper bound.
- **Latency:** mean monotonic HTTP round-trip time across all actual request attempts,
  including retries, HTTP errors and timed-out/cancelled requests when timing is available.
  Backoff, queue wait, simulation delay and browser animation are excluded from that metric.
- **Attempt time:** monotonic trial start to terminal outcome, including request queueing,
  retries/backoff, local state/persistence work and validation. It is not just summed API time.
- **Solve rate:** solved / all terminal started trials ×100. API/budget/cancellation failures
  remain visible in this denominator; NOT_RUN/PENDING are excluded and planned counts shown.
  Failures cannot silently improve the rate. Missing observations are N/A, not zero.
- **Moves:** executed valid actions only. Means for all terminal attempts and solved attempts
  are separate columns; malformed requests/retries never increment executed moves.
- **Gap:** executed moves minus proven shortest distance, only for solved and proven trials.
  Unsolved or unproven trials have null gap; proven-solved sample count is shown.
- **Ranks:** solved agents ordered by actual completion time, then moves. Race-only ranks
  have no cross-suite scientific significance. Failed/unsolved agents receive no medal.
- **Evidence:** immutable puzzle metadata, seed, timestamp, source, requested/effective IDs,
  mode, policy version, request telemetry and status history persist with results. Raw
  provider response bodies and credentials are intentionally not logged.

The five assignment questions are generated from the selected measured aggregates. Without
live evidence all answers explicitly say insufficient data. Observed latency and solve-rate
leaders are descriptive; ties and small samples are not statistical proof. The app does not
claim an untested hybrid is superior. See `backend/stats.py` for definitions.

## Architecture and persistence

```text
frontend/          Original vanilla-JS arena, SVG/net renderer, dashboard and slide
backend/cube.py    Pure move permutations, deterministic scrambles, exact proof
backend/models.py Fixed registry, common contract, strict HTTP adapters and telemetry
backend/races.py   Per-run lifecycle, concurrent independent trials, cancellation/events
backend/store.py   SQLite snapshots, restart recovery, atomic persistent request budget
backend/stats.py   Mode/tier-separated suite aggregates and five-question analysis
backend/main.py    Local API, validation, origin protection, SSE and exports
tests/            Offline engine, adapter and end-to-end tests
docs/evidence/    Clearly tagged simulated verification evidence and UI screenshots
```

Runtime data is in `data/cuberace.sqlite3`, excluded from Git. Server shutdown aborts work;
interrupted snapshots are marked on restart. SSE supports `Last-Event-ID`/`after` replay.
This is a local single-user tool, bound to loopback by default, with same-origin mutation
checks and a restrictive content policy. It is not a hosted multi-tenant service. Do not
expose it to a network without adding authentication, authorization and deployment review.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/health`, `/api/config` | Read-only health and non-secret settings |
| GET | `/api/puzzle?seed=2026&tier=primary` | Reproducible shared puzzle / exact reference |
| POST | `/api/runs` | Explicit start: mode, kind, tier, seed, puzzles, call_cap, confirm_paid_calls |
| GET | `/api/runs`, `/api/runs/{id}` | Saved run inventory / full record |
| GET | `/api/runs/{id}/events` | Replayable SSE lifecycle |
| POST | `/api/runs/{id}/abort` | Cancel this run |
| GET | `/api/stats?mode=live&tier=primary` | Pure suite aggregates; never starts work |
| GET | `/api/runs/{id}/export/{format}` | `json`, `csv`, `steps.csv`, `requests.csv` |
| GET | `/openapi.json` | Machine-readable API schema |

## Verification

```powershell
.venv\Scripts\python.exe run_verification.py
```

Runs pytest, Ruff, optional Node syntax checks and an isolated full five-puzzle simulated
suite. Writes clearly marked raw evidence to `docs/evidence/` without touching live data.
For only tests use `python -m pytest -q`. CI repeats this on pushes. Never interpret these
offline HTTP fixtures as successful live account/API tests.

Browser checks (optional, headless Edge/Chromium):

```powershell
.venv\Scripts\python.exe scripts/verify_browser.py
```

The script starts an isolated local server/database, drives a race and suite, checks all
tabs at 1366×768, 1920×1080 and a mobile viewport, and saves real screenshots/browser evidence.
Use `python -m playwright install chromium` if Edge is unavailable. Existing user browser
profiles and logged-in accounts are not used.

## Recording and submission checklist

- Set the real student name and roll; verify both remain visible on every tab and full screen.
- Run and retain the four-call live smoke log, then five or more primary puzzles × four models.
- Inspect errors and gaps; export raw JSON/CSVs. Record unavailable routes as incomplete.
- Record an in-progress race with all four cards, moves and timers visible.
- Record completed attempts, including honest move-limit or error outcomes.
- End with the Results Slide showing **LIVE primary suite evidence**, sample counts, metrics
  and answers to all five questions. Avoid confusing simulated rehearsal with live evidence.
- Keep the identity banner visible throughout the recording, including analysis screens.
- Submit the video and this GitHub repository as instructed by the course. The application
  does not invent identity, record or upload a submission video automatically.

The assignment PDF is authoritative; the user's implementation brief supplied the detailed
constraints. Functional inspiration: [Muhammad Abbas's reference repository](https://github.com/muhammad1234-max/AI-Engineering-Assignment2).
See [independent reference review](docs/REFERENCE_REVIEW.md). No reference author identity,
benchmark outcomes or source code is submitted as this project's work.
