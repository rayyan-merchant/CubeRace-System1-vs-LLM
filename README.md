# CubeRace: System-1 vs LLM

An original local Rubik's Cube racing application for AI Engineering Assignment 02.
Four concurrent agents receive the same cube and choose one move at a time. The arena,
benchmark dashboard and recording slide distinguish **LIVE** evidence from **SIMULATED**
functional fixtures throughout.

**Readiness:** local implementation and verification evidence are described in
[IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md). Live four-model performance and the final screen recording require real user inputs. No model
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
starts paid work. The frontend recording banner is explicitly set to **Rayyan Merchant · 23K-0073**,
as requested by the student, and stays visible on every tab and in full screen. The server
`STUDENT_NAME` / `STUDENT_ROLL` metadata settings do not override this presentation banner.

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
API_RETRIES=0
CLAUDE_REASONING_EFFORT=low
CLAUDE_MAX_TOKENS=1024
```

Restart the server. The key stays on the server and is never sent to the browser. For a first
routing check only, the default smoke command tests all four models:

```powershell
.venv\Scripts\python.exe verify_live_api.py --confirm-paid
```

This command has no retries, at most four charged requests, and writes a new timestamped
`data/live-smoke-<UTC timestamp>-<unique suffix>.json`. Existing reports, including the old
`data/live-smoke.json`, are preserved. To avoid repeating already-checked models, select only
those needing verification:

```powershell
.venv\Scripts\python.exe verify_live_api.py --models claude --confirm-paid
.venv\Scripts\python.exe verify_live_api.py --models jev,luna --confirm-paid
```

These send at most one and two requests respectively. Short names are `jev,luna,clef,claude`;
assigned full IDs also work. Unknown, empty or duplicate selections fail before inference.
Output reports requested/effective IDs, status, HTTP status, finish reason, usage and cost.
`OUTPUT_LIMIT` remains a failure; reasoning text is never mined for a move.
It tests routing/schema, not solving. On Unix use `.venv/bin/python`. The main UI live start
requires checking an explicit paid-call authorization and a positive per-run cap.

Worst case calls = puzzles × 4 × 30 × (1 + retries). Zero retries is the default: a race
is at most 120 requests and a five-puzzle suite at most 600. One optional retry raises these
to 240 and 1,200 respectively. Token cost is model/response dependent: a request cap is
not a dollar cap. The lower of persistent and per-run remaining budgets governs every request,
including malformed responses, failed requests and retries. The persistent counter lives in
SQLite; restarting/replaying does not reset it. Increasing `API_CALL_BUDGET` explicitly raises
the cumulative ceiling. Preserve the database between live sessions.

## Minimum-spend workflow and fixed Claude settings

1. Rehearse with simulated fixtures for free. Check the identity banner and recording layout first.
2. Privately enable live access only when ready. Set `API_RETRIES=0`,
   `CLAUDE_REASONING_EFFORT=low`, `CLAUDE_MAX_TOKENS=1024` and restart. Never disable
   Claude's mandatory reasoning. Supported efforts are `low`, `medium`, `high`, `xhigh`, `max`;
   invalid efforts fail at startup. Settings are fixed across the entire run, never adapted
   to a model's successes/failures. A changed setting is a new experimental condition.
3. After a previous four-model smoke, verify only models that need retesting. Start with
   **one Claude-only request** at 1,024 tokens; review its actual cost and whether it returns
   valid final JSON before considering a benchmark. Jev/Luna-only verification is optional
   and separately paid. No selection means all four; do not repeat it unnecessarily.
4. For five primary puzzles, explicitly set the UI per-run cap to **600** and check paid-call
   consent immediately before starting the suite. The UI displays recommendations; it never
   increases your chosen cap or persistent budget. Consent clears after each start and on
   plan edits. With a fresh counter, smoke plus suite requires at most **604 requests**.
   You may manually choose `API_CALL_BUDGET=604` for this workflow; with existing usage,
   deliberately set a sufficient cumulative ceiling. Never delete/reset the database to
   bypass the budget. Earlier solves can use fewer requests; no dollar saving is promised.
5. Keep the completed run. Use Saved runs → Replay, downloads and Results Slide for
   demonstrations. Refresh, statistics, exports, page loads and replay never call inference.
   No benchmark or failed trial restarts automatically. A new Start is a new paid execution.

Claude sends `reasoning: {"effort":"low"}` and `max_tokens:1024` by default, plus the same
strict 18-move JSON schema. OpenRouter's public model metadata confirms mandatory reasoning,
these efforts, `max_tokens`, and structured outputs. The ceiling covers reasoning plus
visible output on most providers: an empty/truncated response can still be billed. A
`finish_reason: length` is retained as an output-limit failure without automatically retrying
or raising the ceiling. Changing ceilings requires a deliberate new experimental condition.
The user reported that 512 tokens were exhausted entirely by mandatory reasoning, with
no final JSON. The 1,024 ceiling is an experimental change, not a guaranteed fix or saving.
Update `CLAUDE_MAX_TOKENS=1024` in your existing private `.env` manually, then restart the
server. Defaults and `.env.example` do not override an explicit older `.env` setting.

Payloads keep the authoritative 54-character state plus lossless labeled face grids,
an explicit whole-cube goal, remaining allowance, HTM and all 18 action meanings.
Every model sees only its **last six executed moves**, initially empty. The full
history still determines `moves_remaining` and is preserved internally for metrics, replay
and exports. No conversational transcript, reasoning request or solution hint is sent.
The three Decisions payloads have identical wording and criteria; Claude gets equivalent
information through compact JSON. Action definitions share degree/CW/CCW conventions.
The redundant solved-state string and metric field are omitted: the instructions define
the goal (every face matches its fixed center) and HTM once.

The fixed policy is `state-action-v5-permutations`. Saved runs record the history window, Claude
settings and identity-allowlist version; request records include their visible move history,
window, remaining allowance and policy version. Old/full-history or different-setting suites
are not pooled with the new condition. Analysis selects the newest saved suite's condition
and shows exclusions.

v5 appends general sticker-permutation rules to v4, shared by all four models. It supplies
no state-specific successor, scoring heuristic, recommendation or solution. The saved v4
diagnostic audit, exact addition, token overhead and Luna 502 limits are documented in
[V4_DIAGNOSTIC_AUDIT_AND_V5.md](docs/V4_DIAGNOSTIC_AUDIT_AND_V5.md).
The [v4 baseline](docs/PROMPT_POLICY_V4.md) remains intact and is not pooled with v5.
Restart an existing server
before using the revised policy; `python preflight.py` detects old loaded source.

### First-action diagnostics (separate from the assignment benchmark)

Preview two one-move states for Jev, Luna and Clef, with **zero requests**:

```powershell
.venv\Scripts\python.exe verify_cube_diagnostics.py
```

Only after explicitly approving paid execution, run:

```powershell
.venv\Scripts\python.exe verify_cube_diagnostics.py --confirm-paid
```

This authorizes at most **six requests** (two per Decisions model), with no retries or
Claude calls. It preserves the persistent request counter and writes a unique timestamped
`data/cube-diagnostic-depth1-*.json` report. A valid action is scored after the response;
no scramble, correct move, scoring oracle or successor state is sent to any model.
Wrong legal moves are recorded unchanged. Errors/NOT_RUN remain distinct from incorrect
valid actions. The diagnostic does not execute a race or enter benchmark aggregates.

Optional two-move diagnostics are a **separate** six-request execution:

```powershell
.venv\Scripts\python.exe verify_cube_diagnostics.py --depth 2
# Paid only after separate explicit approval:
.venv\Scripts\python.exe verify_cube_diagnostics.py --depth 2 --confirm-paid
```

They score whether the returned first action leaves a cube solvable in one further move;
they do not request that second move. Diagnostics do not replace the final five-puzzle,
four-model assignment benchmark, which still includes Claude. Offline fixtures establish
implementation correctness, not improved external model accuracy or lower billed costs.

### Optional direct OpenAI Luna diagnostic

An optional **direct OpenAI Luna** diagnostic uses the native Decisions API, the frozen
v4 observation policy by default (or explicit `--policy v5`), and these same two one-turn states. It never replaces the assigned
OpenRouter adapter or enters assignment benchmark statistics:

```powershell
# Free preview; no credentials or HTTP needed:
.venv\Scripts\python.exe verify_luna_openai.py
# Only after explicit approval: at most TWO paid direct OpenAI requests, no retries:
.venv\Scripts\python.exe verify_luna_openai.py --confirm-paid
# Explicit v5 mechanics policy, ONE selected state / at most ONE paid request:
.venv\Scripts\python.exe verify_luna_openai.py --policy v5 --case 2 --confirm-paid
```

It requires server-side `OPENAI_API_KEY` plus the existing live/zero-retry controls;
no OpenRouter key is required. Calls consume the persistent request cap under the distinct
`openai-direct/gpt-6-luna` ledger identity. Timestamped reports go to `data/direct-openai/`.
Native costs remain unknown unless reported. Direct-provider charges are outside any
OpenRouter key spending limit. See [native contract, safeguards and evidence boundaries](docs/DIRECT_OPENAI_LUNA_DIAGNOSTIC.md).

Authorized checks on October 25 found a working key: a classification control answered,
v4 cube input still refused, and v5 produced valid but incorrect moves on both one-turn
states. This establishes response compatibility for those two v5 calls, not reliable
solving or a guaranteed refusal fix. V4 results remain separate and unchanged.

### Reported billing, not estimated spending

Decisions usage `input_tokens` / `output_tokens` normalizes to prompt/completion counts;
chat usage `prompt_tokens` / `completion_tokens` uses the same normalized fields. A missing
total is derived only when both components are known. `total_tokens_source` distinguishes
`provider` from `derived`; summaries count these sources. Provider costs are retained as
reported; historical raw usage is interpreted read-only, never rewritten.

The server stores raw response `usage`, native prompt/completion/total tokens, reasoning
tokens, and `usage.cost` per request, including charged errors/malformed/limited outputs.
It exposes known cost and unknown-request counts by model, run, selected suites and the
persistent application ledger (including smoke). A missing cost is **unknown**, even when
some other costs are known; only a reported zero is zero. A complete total is null when
any request cost is unknown. Token subtotals likewise show missing observations.

Current official OpenRouter docs say usage is automatic. The chat payload retains the
compatible legacy `usage:{"include":true}` opt-in (deprecated/no effect); the typed Decisions
payload adds no undocumented field. No extra inference or generation lookup retrieves
billing. Existing counters without ledger entries are shown as unattributed unknown costs.
Requests are atomically journaled before sending, so an interrupted request is counted and
remains unknown until a response is recorded. The request ceiling is **not a dollar cap**.

HTTP 400/401/402/403/404/422 or an effective-ID mismatch stop that model on later puzzles
of the same run. Two consecutive unsupported response envelopes do so too. The observed
failure remains a started trial; subsequent skipped puzzles are `NOT_RUN` with a reason,
excluded from attempted denominators and shown beside planned counts. Transient errors,
illegal moves, malformed action JSON, output truncation and move limits never quarantine
an agent on an assumption about future solving quality. A new explicitly approved run
may retry after you fix compatibility; no result is substituted or fabricated.

## A total API budget below $1

A request-count cap is not a dollar cap. In [OpenRouter key settings](https://openrouter.ai/settings/keys),
set the existing key's **total lifetime limit to $0.95** (or $0.90 for a larger margin),
with no reset. This is a cumulative limit including money already spent, not an additional
$0.95 allowance. Do not create another key or reset the request ledger to bypass spending.
The [key limits endpoint](https://openrouter.ai/docs/api/reference/limits) reports spending;
changing a limit via API requires a management key. Regular inference keys cannot update it.
Leave margin for concurrent requests and billing settlement; do not promise a strict final
settled total solely from an estimate.

At $4/M input and $20/M output, 882 input plus the full 1,024 completion tokens costs
**$0.024008 per Claude decision**, excluding other fees. This is an estimate using the
user's earlier input size and [published pricing](https://openrouter.ai/anthropic/claude-opus-5.5/),
not a measured future request. 150 such Claude decisions alone would be $3.6012. A five-puzzle
suite can therefore exceed $1 even with zero retries and concise prompts. One valid smoke
move does not establish solve rate, typical token use, or successful completion under $1.

Review the selective Claude smoke's actual billed cost before starting **one five-puzzle
Primary suite**. Skip paid practice races and unnecessary smoke repeats. Keep all models'
30-action allowance and the same context policy. If the provider cap is reached, retain
actual failure and NOT_RUN counts; the evidence is incomplete. Never substitute simulations
or alter one model's allowance. Use saved replay for recording. No benchmark is started by
this workflow automatically.

## Metrics and fairness

- **State/actions:** 54 facelets, row-major URFDLB, fixed color centers; exactly 18 legal
  Singmaster actions. Half-turn metric (HTM): `R2` is one action. Every trial has exactly
  the same 30-action ceiling; early solves finish immediately.
- **Inputs:** identical initial states, current facelets, last six agent-only executed moves, goal,
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
backend/store.py   SQLite snapshots, restart recovery, atomic request budget and billing journal
backend/billing.py Response-reported cost/token subtotals with explicit unknown observations
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

Runs pytest, Ruff, optional Node syntax and Start/Abort regression checks, and an isolated full five-puzzle simulated
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

- Verify **Rayyan Merchant · 23K-0073** remains visible on every tab and in full screen.
- Retain the existing smoke logs and only necessary selective retests; then run the required primary suite within the provider spend cap.
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


## Recording layout and methodology

The recording UI retains CubeRace's original colors, four model cards and cube renderer.
Race Arena uses the heading **Rubik's Cube Benchmark**; Results Slide uses **Benchmark Results**.
Source and difficulty filters in Benchmark Analysis also select the slide's evidence.
Its puzzle count is the actual planned puzzle count in the selected fixed-condition suites,
not a hardcoded five. Empty filters show zero puzzles and unavailable metrics.

SIMULATED cards, tables and slides show the assigned model slots, but synthetic results
are explicitly labelled and never support model-performance conclusions. Missing metrics
remain N/A. Completed execution does not imply successful model completion: failure and
NOT_RUN counts remain visible in the comparison tables.

Detailed methodology lives here rather than above the demo controls: each suite uses the
arena source, difficulty and starting seed; subsequent seeds advance deterministically.
Live agents receive URFDLB row-major facelets, fixed centers, their last six executed moves
and the same legal actions, never the scramble or reference solution. Cube nets use U white,
R red, F green, D yellow, L orange, B blue. Rankings use measured completion time; playback
speed affects only rendering. All terminal started trials, including infrastructure failures,
form the solve-rate denominator; NOT_RUN is excluded and counted separately. Optimality gaps
use solved trials with a proven reference. Aggregates exclude suites with different fixed
settings; the exclusion count is shown when relevant. Results are descriptive and do not
establish statistical significance. Single races are saved/replayable but excluded from suites.

The live request plan retains explicit per-run consent, a user-entered cap, recommended
race/suite caps, retry count, persistent request usage and known/unknown billing. It is hidden
on Results Slide; opening that slide, replaying, exporting or refreshing starts no inference.
API schema documentation remains available at `/openapi.json`.


### Authorized Claude-only result — 2026-10-25

One paid request at low effort / 1,024 tokens returned HTTP 200, `VALID_RESPONSE`, move `F`,
`finish_reason=stop`, requested/effective `anthropic/claude-opus-5.5`. Usage: **882 input,
819 completion, 809 reasoning, 1,701 total tokens**, reported cost **$0.019908**. The smoke
used an explicit runtime setting; the private `.env` was not edited. Retained sanitized
[evidence](docs/evidence/claude-selective-smoke-2026-10-25.json) is adapter smoke evidence,
not a solve-rate benchmark. Jev/Luna fixes were verified with offline fixtures only.
No further paid inference or live benchmark was executed by this patch.

The key reported **$0.033779438 cumulative spend**, **$0.966220562 remaining**, with a
**$1 no-reset lifetime limit** after that call. The normal inference key cannot lower its
own limit; the user must change it to $0.95 in OpenRouter settings before the benchmark.
At this single observed request cost, 35 additional Claude decisions would cost $0.69678,
40 would cost $0.79632, and 150 would cost $2.9862, **excluding** prior spending and the
other models. These are extrapolations, not measured benchmark costs or guarantees. Solve
behavior and token use may vary. The full 30-action allowance remains in force for everyone.


## Local preflight before recording or approving paid work

Run the server from this exact checkout, then check it from a second PowerShell terminal:

```powershell
Set-Location -LiteralPath "C:\Users\RayyanMerchant.Inter\Downloads\AI Eng A2\CubeRace-System1-vs-LLM"
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```powershell
Set-Location -LiteralPath "C:\Users\RayyanMerchant.Inter\Downloads\AI Eng A2\CubeRace-System1-vs-LLM"
.venv\Scripts\python.exe preflight.py
```

Preflight performs only GET requests to the local server and read-only SQLite queries.
It never starts a run, contacts OpenRouter, changes `.env`, resets accounting or increases
budgets. Health now includes a startup snapshot of the server PID, Python executable,
project/module/working-directory paths, database path, Git commit, backend source hashes,
policy version and exact model allowlist. It is captured once: updating files on disk
cannot make an old in-memory server falsely identify itself as new.

The check compares that snapshot with the current local checkout and verifies frozen server
configuration, live enablement, zero retries, Claude low/1,024, student identity, 30 actions,
database availability, absence of an active run and remaining request budget. An older
server without runtime metadata fails preflight even when its basic health says OK. Never
infer the running version from `git log` in a different terminal alone.

`local_runtime_ready: true` establishes local configuration/runtime consistency, not live
API availability or solving quality. `five_puzzle_worst_case_covered` separately says
whether the existing counter has room for 600 requests at zero retries; a warning never
raises the budget. Unknown charges remain unknown. Provider USD limits and balances are
not queried by this offline preflight. Budget-limited or aborted trials are incomplete,
not 30-move failures. Historical replay intentionally retains the original policy/statuses.

After changing source or `.env`, stop **only this server** with Ctrl+C in its terminal,
then restart with the command above. If that terminal is unavailable, inspect the exact
port owner first:

```powershell
$taskListener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$taskListener | Select-Object LocalAddress, LocalPort, OwningProcess
$taskListener | ForEach-Object {
    Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $_.OwningProcess) |
        Select-Object ProcessId, ParentProcessId, ExecutablePath, CommandLine
}
```

Only after verifying that PID belongs to the intended CubeRace Uvicorn command, stop that
specific PID with `Stop-Process -Id <verified-PID>`. Do not stop all Python processes or use
an unverified port owner. If nothing listens on 8000, there is no server to terminate.
An unexpected process/checkout must be investigated before restarting. No force-pull,
reset, database deletion or automatic paid retest is part of this procedure.
