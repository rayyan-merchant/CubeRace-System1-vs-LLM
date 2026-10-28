# CubeRace: System-1 vs LLM

A local Rubik's Cube benchmark for AI Engineering Assignment 02. Four independent agents
start from the same cube state, select one legal move at a time, and receive at most
30 actions per trial. The application includes a race arena, benchmark analysis, a
results slide, persistent runs, replay and exports.

## Setup

Python 3.10+ is required. Node.js is optional for JavaScript verification. Run commands
from the repository root.

### Windows PowerShell

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Linux or macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
test -f .env || cp .env.example .env
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open [CubeRace](http://127.0.0.1:8000). Use one server worker. The frontend requires no
build step, external fonts or CDN. For runtime-only installation, use requirements.txt.

## Configuration

All credentials stay server-side in the ignored .env file. Never commit that file.

| Variable | Default | Purpose |
|---|---|---|
| OPENROUTER_API_KEY | empty | Jev, Clef and Claude credentials |
| OPENAI_API_KEY | empty | Luna credentials when using direct OpenAI |
| LUNA_PROVIDER | openai | Fixed Luna route: openai or openrouter; no automatic fallback |
| ALLOW_LIVE | false | Enables live execution after explicit per-run consent |
| OPENROUTER_MOCK_MODE | true | Blocks live mode until set to false |
| API_CALL_BUDGET | 1200 | Persistent application-wide request ceiling |
| API_TIMEOUT_SECONDS | 30 | Request timeout |
| API_RETRIES | 0 | Configurable retry allowance; zero by default |
| CLAUDE_REASONING_EFFORT | low | Fixed reasoning effort; mandatory reasoning remains enabled |
| CLAUDE_MAX_TOKENS | 2048 | Fixed combined reasoning/completion ceiling |
| API_CONCURRENCY | 4 | Maximum concurrent model requests |
| STUDENT_NAME / STUDENT_ROLL | empty | Student metadata |
| DATABASE_PATH | data/cuberace.sqlite3 | SQLite database |

Changing defaults does not overwrite an existing .env. For example, set
CLAUDE_MAX_TOKENS=2048 there if an existing file still specifies a lower ceiling.
Restart the server after configuration changes and refresh the browser.

## Models and providers

| Agent | Logical assigned ID | Default API |
|---|---|---|
| Jev 1.13 | typesafe/jev-1.13 | OpenRouter Decisions |
| GPT-6 Luna Decisions | openai/gpt-6-luna-decisions | OpenAI Decisions, native ID gpt-6-luna |
| Cloudflare Clef | cloudflare/clef | OpenRouter Decisions |
| Claude Opus 5.5 | anthropic/claude-opus-5.5 | OpenRouter Chat Completions |

Luna uses the direct OpenAI route by default, as configured for this project. This is a
provider deviation from the assignment's all-OpenRouter specification and must be
identified in the submitted methodology. Setting LUNA_PROVIDER=openrouter before a run
selects the assigned OpenRouter route instead. Provider identity and effective model IDs
are recorded; no model or provider is silently substituted. Dated Jev/Luna OpenRouter
IDs are accepted only through explicit allowlists.

## Using the application

- **Race Arena:** choose difficulty and seed, generate a scramble, select the source,
  and start or abort a race. Shared scramble and proven shortest distance are observer
  information. Four independent model cards show cube state, moves, timing and history.
- **Benchmark Analysis:** select the puzzle count and run a suite. Filters, model tables,
  solve-rate/latency charts, the five assignment answers and billing use saved results.
- **Results Slide:** presents selected evidence and its actual sample size. Student
  identity remains visible, including fullscreen presentation.
- **Saved runs:** replay without inference or export JSON, summary CSV, steps CSV and
  request CSV. Historical runs remain readable without their original prompt builders.

The default source is SIMULATED. Its scripted results are UI fixtures, not measured model
performance. LIVE mode requires provider credentials, ALLOW_LIVE=true,
OPENROUTER_MOCK_MODE=false, an explicit request cap and a checked consent control for
that run. Page loads, refreshes, statistics, exports, health checks and replay do not
initiate paid inference.

Suite size is configurable from 1 to 25, with five as the default. Smaller suites receive
descriptive analysis with their actual sample counts; the assignment still requires at
least five distinct primary puzzles. Warm-up uses 3-4 scramble turns, Primary 4-5, and
Extension 15-20. Scramble length is not assumed to equal optimal distance.

## Prompt, fairness and metrics

There is one production prompt, defined in backend/models.py and documented in
[Prompt and experiment protocol](docs/PROMPT.md). All models receive equivalent current
54-facelet state, labeled face grids, last six executed agent moves, remaining allowance,
18 actions, turn conventions and solving objective. Initial agent history is empty.
The full executed history is retained for metrics, replay and export.

The cube uses URFDLB facelet order and Half-Turn Metric: each listed quarter or half turn
counts as one action. The engine applies exactly the selected legal move. Live agents
receive no scramble, BFS solution, inverse policy, heuristic score or successor-state
preview. The bidirectional BFS reference solver is observer-only. Unproven extension
optima and gaps remain unavailable rather than estimated.

Reported metrics include solve rate, mean API request latency, attempt duration, executed
moves and proven optimality gap for solved trials. Terminal started failures are included
in attempted-trial denominators; NOT_RUN is excluded and shown separately. Refusals,
API errors, output limits, aborts and move-limit failures remain distinct. Aborted trials
are not described as completed 30-action failures. Small samples support descriptive
observations, not significance or general performance claims.

Prompt-policy IDs and fixed settings remain in saved metadata for provenance. Results
from different recorded prompt/provider/settings conditions are not silently pooled.
No benchmark winners, costs or successful live API results are fabricated.

## Request limits and billing

At zero retries, a full race recommends 4 models x 30 actions = 120 requests; three puzzles
recommend 360 and five recommend 600. With retries, multiply by (1 + API_RETRIES). A lower
explicit cap is honored and may leave trials incomplete. Neither application-wide nor
per-run caps reset or increase automatically.

These are request ceilings, not USD limits. Response-reported input/output/reasoning
tokens and costs are retained. Missing costs remain unknown, not zero. Direct OpenAI
charges are separate from OpenRouter spending limits. Mandatory reasoning can consume
Claude's entire completion budget; 2,048 tokens do not guarantee a final JSON move.
Luna can return a typed refusal without explaining why. A legal move is not evidence of
a good move, and a working integration does not guarantee solving.

Review provider spending before authorizing a live suite. An under-$1 total is not
guaranteed. Retain incomplete evidence if a limit or provider failure interrupts a run.
Use saved replay for recording rather than repeating paid races.

## Verification

All automated checks use fixtures, interception or simulated mode:

```powershell
.venv\Scripts\python.exe run_verification.py
.venv\Scripts\python.exe scripts/verify_browser.py
.venv\Scripts\python.exe preflight.py
```

The verification command runs pytest, Ruff, optional Node checks and an isolated
five-puzzle simulated suite. Browser verification requires Playwright and an installed
Edge browser on Windows, or Playwright Chromium elsewhere. On supported platforms,
install the browser separately with python -m playwright install chromium.

Generated logs, screenshots and exports go to ignored data/ directories. CI runs the
offline verification and does not publish local analysis artifacts. Preflight only checks
local runtime identity, configuration, database, remaining request budget and server
health; it cannot establish external API availability or future model correctness.

An optional selective smoke command is provided for explicitly authorized paid checks:

```powershell
# PAID: at most one request per selected model; zero retries.
.venv\Scripts\python.exe verify_live_api.py --models luna --confirm-paid
```

Without --confirm-paid, it makes no inference request. Omitting --models selects all four models.
Use this only with explicit spending approval; it does not replace the assignment suite.

## Project structure

```text
backend/                 API, cube engine, adapters, racing, accounting and persistence
frontend/                Arena, analysis, results slide and cube visualization
docs/PROMPT.md           Current prompt and protocol
scripts/verify_browser.py  Offline browser verification
tests/                   Engine, contract, orchestration, accounting and UI regressions
preflight.py             Read-only local readiness check
run_verification.py      Offline verification entry point
verify_live_api.py       Explicitly authorized selective smoke check
data/                    Ignored local database, exports and verification output
```

The functional reference was [Muhammad Abbas's assignment application](https://github.com/muhammad1234-max/AI-Engineering-Assignment2).
CubeRace is an independently implemented application. Its current repository contains
application source, tests and submission documentation; local research notes and generated
analysis are excluded.
