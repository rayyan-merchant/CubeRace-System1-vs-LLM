# Functional reference review

Reference: https://github.com/muhammad1234-max/AI-Engineering-Assignment2

Reviewed on 2026-10-22 from a separate read-only study checkout: README,
backend/app/cube_engine.py, openrouter_client.py, benchmark_runner.py, main.py,
frontend/index.html, frontend/static/js/cube_renderer.js and tests layout.
No source or benchmark data was imported into this repository.

Preserved functional ideas: a four-slot 2x2 arena, isometric SVG facelets, shared scramble,
presets, per-agent telemetry/history, speed controls, analysis, final statistics and identity.

Verified shortcomings in the inspected version:

- `MAX_RACE_MOVES = 60` and request default 60 conflict with PDF maximum 30.
- Luna substitutes GPT-4o-mini after provider errors; Claude substitutes Sonnet on credit failure.
- Mock selection uses a solver and invented model-specific latency/confidence distributions.
- Category resolution can depend on model-name substrings and environment overrides.
- Wildcard CORS and a mutable global runner weaken local state isolation.
- Cube renderer exposes three faces; this implementation also supplies a six-face net.

Other issues listed by the master brief were treated as required regression constraints;
they are not all claimed as independently reproduced reference defects.

Original implementation differences: geometric immutable string states; exact capped BFS
only for evaluation; typed registry; strict Decisions choice / chat JSON parsing; explicit
synthetic agent identities; persistent request counter; per-run snapshots; replayable SSE;
same-origin mutation protection; live-only empirical analysis; seed/tier-separated suite data.
