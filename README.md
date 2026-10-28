# CubeRace: System-1 vs LLM

**AI Engineering - Assignment 02**

**Student:** Rayyan Merchant | **Roll number:** 23K-0073

[![Demo Video](https://img.shields.io/badge/Demo_Video-B91C1C?style=for-the-badge&logo=youtube&logoColor=white)][demo-video] [![Benchmark Data](https://img.shields.io/badge/Benchmark_Data-0369A1?style=for-the-badge&logo=googledrive&logoColor=white)][benchmark-data] [![Results Slide](https://img.shields.io/badge/Results_Slide-92400E?style=for-the-badge&logo=googleslides&logoColor=white)][results-slide] [![Report](https://img.shields.io/badge/Report-334155?style=for-the-badge&logo=readthedocs&logoColor=white)][report] [![Source Code](https://img.shields.io/badge/Source_Code-181717?style=for-the-badge&logo=github&logoColor=white)][source-code]

## Overview

CubeRace is a controlled Rubik's Cube experiment comparing fast decision models with a
frontier LLM. It investigates whether faster move selection also produces better
solutions, using measured latency, completion time, solve rate, move count and distance
from a proven shortest solution.

The application provides a four-agent Race Arena, Benchmark Analysis dashboard and
fullscreen Results Slide. Each agent starts from the same scrambled cube, selects one
legal move at a time, and has a maximum of **30 actions**. Results are saved for replay
and machine-readable export.

## Deliverable links

The buttons above are ready for the final submission links. Until those URLs are added,
they point to this section; they do not indicate that recordings or results are uploaded.
Replace the four marked URL definitions at the bottom of this README.

| Deliverable | Submission content |
|---|---|
| Source Code | This GitHub repository: original application, setup instructions and environment template |
| Demo Video | Screen recording showing play in progress, the completion stage and a final statistics slide; student identity visible throughout |
| Benchmark Data | Recommended supporting evidence: exported run JSON and summary, step and request CSV files |
| Results Slide | The statistics slide shown at the end of the recording; an exported image/PDF may also be linked |
| Report | Optional written analysis, if requested separately; the five assignment questions must still be answered in the submitted experiment |

## Assignment coverage

| Assignment component | Implementation / evidence |
|---|---|
| Scrambled 3x3 cube and game controls | Four live-updating SVG cubes, shared scramble, current move, complete move history, status, start/abort and playback controls |
| Deterministic cube engine | 54 facelets in URFDLB order, 18 legal Singmaster actions, exact solved-state checks and seeded scrambles |
| Equal rules for four agents | Independent cube copies, equivalent observations, fixed history policy, common timeout/retry policy and a 30-action maximum |
| Decision and chat integrations | Typed Decisions choices for Jev/Luna/Clef; constrained JSON chat completion for Claude |
| Shortest-path reference | Complete bidirectional BFS for primary puzzles; reference solutions are never supplied to live agents |
| Statistical dashboard | Per-request mean latency, attempt time, moves, solve rate, solved-only optimality gap, sample/status counts and charts |
| Persistent evidence | SQLite, saved-run replay, JSON and CSV exports, effective model IDs, provider/settings provenance and reported billing |
| Final recording | Race Arena, Benchmark Analysis and fullscreen Results Slide with permanent student identity; recording/link must be supplied by the author |

The implementation supports the required workflow. A completed live experiment and the
final recording are separate deliverables; passing offline tests is not evidence that
all models solved the cube or that the live benchmark is complete.

## Models and API contract

The assignment specifies these model IDs and OpenRouter interfaces:

| Model | Category | Assigned OpenRouter ID | Required interface |
|---|---|---|---|
| Jev 1.13 | System-1 decision model | typesafe/jev-1.13 | Decisions API |
| OpenAI GPT-6 Luna Decisions | System-1 decision model | openai/gpt-6-luna-decisions | Decisions API |
| Cloudflare Clef | System-1 decision model | cloudflare/clef | Decisions API |
| Claude Opus 5.5 | Frontier LLM | anthropic/claude-opus-5.5 | Chat Completions API |

- Decisions: POST https://openrouter.ai/api/alpha/decisions
- Chat completions: POST https://openrouter.ai/api/v1/chat/completions

The three OpenRouter Decisions requests use identical question wording and action
criteria, differing only in model ID. Claude receives equivalent state/action information
and must return exactly one legal move through a strict JSON schema:

```json
{"move": "R'"}
```

Every selected action is validated before execution. Missing, malformed or illegal moves
are recorded as failures rather than extracted from reasoning or replaced by another
move. Effective model IDs are validated using explicit allowlists. No automatic model
or provider fallback is used. Confidence and choice probabilities are retained when the
provider supplies them; absent values remain unknown.

### Assignment submission provider profile

**For the all-OpenRouter experiment required by the assignment, explicitly set
LUNA_PROVIDER=openrouter before starting the server and collecting submission evidence.**

The project also supports direct OpenAI Decisions for Luna using OPENAI_API_KEY and the
native ID gpt-6-luna. The supplied .env.example currently defaults to that direct route.
It is an alternative provider condition, not an all-OpenRouter result. If direct OpenAI
results are submitted instead, disclose the deviation and obtain instructor approval.
Changing the route does not reclassify old saved runs; provider/settings conditions stay
separate in the analysis. API availability and successful solving are not guaranteed.

## Setup

Requirements: Python 3.10+, pip, and a modern browser. Node.js is optional for JavaScript
checks. The frontend has no build step or external font/CDN dependency.

```bash
git clone https://github.com/rayyan-merchant/CubeRace-System1-vs-LLM.git
cd CubeRace-System1-vs-LLM
```

### Windows PowerShell

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
test -f .env || cp .env.example .env
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Use one server worker. The default
SIMULATED mode is free and uses explicitly labeled scripted UI fixtures. Installing
requirements.txt alone is sufficient for runtime; requirements-dev.txt adds verification
tools. Restart the backend and refresh the browser after changing configuration.

## Environment configuration

Keep real credentials only in the server-side, ignored .env file. Do not put keys in the
frontend, README, exported evidence or recording. Creating/updating .env.example does
not overwrite an existing private .env.

For an explicitly authorized assignment-profile LIVE run, configure:

```dotenv
OPENROUTER_API_KEY=replace_with_your_key
LUNA_PROVIDER=openrouter
ALLOW_LIVE=true
OPENROUTER_MOCK_MODE=false
API_RETRIES=0
CLAUDE_REASONING_EFFORT=low
CLAUDE_MAX_TOKENS=2048
STUDENT_NAME=Rayyan Merchant
STUDENT_ROLL=23K-0073
```

| Setting | Default | Purpose |
|---|---|---|
| OPENROUTER_API_KEY | empty | OpenRouter credentials |
| OPENAI_API_KEY | empty | Required only for direct-OpenAI Luna |
| LUNA_PROVIDER | openai | Fixed Luna route; set openrouter for the assignment profile |
| ALLOW_LIVE | false | Enables live mode, subject to per-run consent |
| OPENROUTER_MOCK_MODE | true | Must be false for LIVE execution |
| API_CALL_BUDGET | 1200 | Persistent application-wide request ceiling |
| API_TIMEOUT_SECONDS | 30 | Shared request timeout |
| API_RETRIES | 0 | Shared retry allowance |
| CLAUDE_REASONING_EFFORT | low | Fixed effort; mandatory reasoning stays enabled |
| CLAUDE_MAX_TOKENS | 2048 | Fixed combined reasoning/completion ceiling |
| API_CONCURRENCY | 4 | Maximum concurrent model requests |
| STUDENT_NAME / STUDENT_ROLL | empty | Student metadata; recording banner identifies Rayyan Merchant / 23K-0073 |
| DATABASE_PATH | data/cuberace.sqlite3 | Persistent local storage |

## Experimental protocol

### Cube representation and action space

The current state is a 54-character row-major URFDLB facelet string plus lossless labeled
3x3 face grids. Legal actions are:

```text
U  U'  U2   R  R'  R2   F  F'  F2
D  D'  D2   L  L'  L2   B  B'  B2
```

The **Half-Turn Metric (HTM)** counts every listed quarter or half turn as one action.
The solving objective is to make every face match its fixed center. Every agent starts
with empty move history. Models see the same current-state information, action definitions,
remaining allowance and at most their six most recent executed moves. Full histories
are retained for metrics and replay.

There is one production prompt, documented in [docs/PROMPT.md](docs/PROMPT.md).
The live policy receives no scramble sequence, BFS path, inverse solution, heuristic
score, successor-state preview or another model's history. The cube engine executes the
model's selected legal action without overriding loops or substituting better moves.

### Puzzle sets

| Set | Scramble length | Purpose |
|---|---|---|
| Warm-up | 3-4 turns | Check adapters, move validation and engine behavior |
| Primary | 4-5 turns | Compare performance against a proven shortest-path reference |
| Extension | 15-20 turns | Observe behavior on more complex states |

Use the assignment's recommended minimum of **five distinct primary puzzles x four
models = 20 trials**; ten or more puzzles provide stronger evidence. The app supports
1-25 puzzles per suite and defaults to five. Smaller suites are labeled and analyzed
with their actual sample counts; they do not establish the recommended 20-trial sample.
Scramble length is not assumed to equal shortest distance. Primary references use
bidirectional BFS; an unproven extension optimum and its gap remain N/A.

Keep the prompt, provider route, timeout, retry allowance, action metric and Claude
settings fixed throughout a reported condition. Use the same initial puzzle state for
all four models. Never combine different settings/provider conditions without disclosure.

### Measurements

| Metric | Definition |
|---|---|
| Mean API decision latency | Mean measured request round-trip latency; excludes browser playback speed and reports request/error/retry counts |
| Attempt time | Elapsed time from trial start to its terminal outcome, in seconds; report solved and unsuccessful outcomes distinctly |
| Move count | Number of legal actions actually executed, up to 30 |
| Solve rate | Solved trials / terminal started trials x 100; failures are included, while NOT_RUN is excluded and reported separately |
| Optimality gap | Executed moves - proven shortest HTM distance, only when the model solved the cube and a reference was proven |

The dashboard labels means for all attempts and solved attempts separately. Missing
measurements are N/A, not invented zeros. Reaching 30 moves without solving is MOVE LIMIT.
REFUSED, OUTPUT LIMIT, API ERROR, UNAVAILABLE, ABORTED and NOT RUN retain distinct
meanings. A partial or aborted trial is not a completed 30-move failure.

## Running, saving and exporting the benchmark

1. In Race Arena, select difficulty and seed, then Generate Scramble. Inspect the four
   cubes and the shared observer-only scramble/reference.
2. Choose the data source. LIVE requires enabled credentials/configuration, a positive
   request cap and explicit consent for that run; consent is not silently reused.
3. In Benchmark Analysis, select Primary, five or more puzzles, and Run Benchmark Suite.
   Allow intended trials to finish. Preserve API failures, refusals and incomplete coverage.
4. Select matching LIVE evidence and difficulty filters. Review sample/status counts,
   tables, solve-rate and latency charts, and the five generated analysis answers.
5. In Saved Runs, export the selected run's JSON, CSV, steps.csv and requests.csv. Keep
   the original exports together so seeds, policy, provider and failure provenance remain
   auditable. Link the uploaded files through the Benchmark Data button.
6. Use saved Replay for demonstrations and identify it as playback of a saved run.
   Never present a SIMULATED fixture as measured model performance. Replaying, refreshing, viewing statistics,
   health checks and downloading exports make no additional inference requests.

### Questions the experiment answers

| Assignment question | Evidence to present |
|---|---|
| Which model makes decisions fastest? | Observed mean API request latency with sample and error counts |
| Which achieved the highest solve rate? | Solved/attempted counts and percentages for the same selected condition |
| Which found the shortest solutions and how close were they to optimum? | Mean solved move count and proven optimality gap; report unavailable if no solved/reference-backed trials exist |
| Was the fastest model also best in solution quality? | Compare observed latency, solve rate and solved-path quality; do not infer quality from speed alone |
| Which would you use in practice: fast decision model, frontier LLM or hybrid? | Evidence-based choice considering completion, path quality, latency, failures and cost; no claim of hybrid superiority without testing one |

These answers are generated from selected saved evidence. This README does not invent
winners, successful live runs or benchmark figures. An empty, failed or small sample
must be described with its limitations.

## Demo recording and submission checklist

The assignment states that all four recording requirements must be met:

- [ ] **In-progress stage:** show the models actively playing, with current moves,
  histories, cube updates and timings visible.
- [ ] **Completion stage:** show the final outcomes for the recorded run. Distinguish
  solved/move-limit attempts from provider errors, refusals and interrupted trials.
- [ ] **Final statistics slide:** end the recording on Results Slide, showing per-move
  latency, attempt time, move count, solve rate and optimality gap for the selected evidence.
- [ ] **Identity throughout:** keep **Rayyan Merchant - 23K-0073** clearly visible during
  the entire recording, including analysis and fullscreen presentation.

Before submitting:

- [ ] Review the recording from start to finish; the identity banner must never be hidden.
- [ ] Answer all five analysis questions using the actual experiment outcomes.
- [ ] Identify LIVE versus SIMULATED evidence and disclose any provider/protocol deviation.
- [ ] Use five or more primary puzzles for the recommended assignment sample; report
  infrastructure failures and incomplete coverage instead of silently omitting them.
- [ ] Upload the video and supporting results, check viewer permissions, and replace the
  deliverable button URLs. The statistics slide must appear inside the video even if a
  separate slide link is also supplied.
- [ ] Confirm a fresh clone starts using this README and .env.example; never publish .env,
  API keys or raw files containing credentials.

## Architecture and verification

| Component | Responsibility |
|---|---|
| FastAPI / asyncio / SSE | Local API, concurrent independent trials, cancellation and event streaming |
| Cube engine / BFS | Deterministic transitions, solved-state checks and observer-only references |
| Model adapters / httpx | Provider-specific wire schemas, strict action validation and request accounting |
| SQLite | Persistent runs, requests, budget counters and replay/export data |
| HTML / CSS / JavaScript | Arena, cube views, controls, dashboard, charts and presentation |

Run the offline checks from the repository root:

```powershell
.venv\Scripts\python.exe run_verification.py
.venv\Scripts\python.exe scripts/verify_browser.py
```

Tests cover cube invariants, independent move verification, shortest paths, fair payloads,
30-action limits, model identities, provider contracts, consent, retries, budgets, usage,
state isolation, failure handling, persistence and inference-free replay/exports. Browser
checks use intercepted responses and a separate temporary database. On Windows they use
installed Edge; elsewhere install Playwright Chromium with python -m playwright install
chromium. Generated verification files remain under ignored data/ directories.

With the local server running, the read-only readiness command is:

```powershell
.venv\Scripts\python.exe preflight.py
```

Preflight checks the loaded code, fixed settings, database, student identity, request
budget and server health. It makes no inference requests and does not prove external
API availability or cube-solving ability. An optional selective live smoke tool exists
in verify_live_api.py; it requires --confirm-paid and is not run by offline verification.

## Cost and security

At zero retries, the recommended request ceiling is puzzles x 4 models x 30 actions:
120 for one race, 360 for three puzzles, or 600 for five. With retries, multiply by
(1 + API_RETRIES). A lower explicit cap is honored and may leave trials incomplete.
Persistent counters never reset or increase automatically.

Request caps are not USD limits. Reported tokens, reasoning tokens and costs are saved;
missing costs remain unknown. Direct OpenAI charges are separate from OpenRouter key
limits. A fixed Claude completion ceiling can still be exhausted by mandatory reasoning.
Review actual provider spending before authorizing work; a total below $1 is not guaranteed.
No paid request is made by loading a page, reading results, replaying or running offline tests.

## Repository structure

```text
backend/                   API, cube engine, adapters, racing, persistence and metrics
frontend/                  Race Arena, Benchmark Analysis, Results Slide and SVG cubes
docs/PROMPT.md             The single production prompt and action protocol
tests/                     Offline engine, adapter, orchestration, billing and UI tests
scripts/verify_browser.py  Offline browser verification
run_verification.py        One-command offline verification
preflight.py               Read-only runtime readiness check
verify_live_api.py         Explicitly authorized selective paid smoke tool
.env.example              Server-side configuration template
data/                     Ignored local database, exports and verification output
```

## Acknowledgement

The assignment's functional reference is
[Muhammad Abbas's AI Engineering Assignment 2 application](https://github.com/muhammad1234-max/AI-Engineering-Assignment2).
CubeRace is independently implemented. The repository contains submission source, tests
and documentation; internal research and generated analysis are excluded.

<!-- Replace only the four URLs below with your uploaded deliverables. -->
[demo-video]: #deliverable-links
[benchmark-data]: #deliverable-links
[results-slide]: #deliverable-links
[report]: #deliverable-links
[source-code]: https://github.com/rayyan-merchant/CubeRace-System1-vs-LLM
