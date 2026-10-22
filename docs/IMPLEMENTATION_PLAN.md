# CubeRace: System-1 vs LLM Implementation Plan

Goal: implement the supplied master brief against the authoritative four-page assignment.
Architecture: a pure permutation cube engine; a capped exact evaluation solver isolated from
live policy; explicit HTTP adapters; independent concurrent trials; replayable SSE; SQLite
snapshots and atomic persistent request budget; same-origin static frontend.

Implementation runs directly on main, explicitly authorized by the user. No deployment.

1. Engine: build geometric URFDLB permutations and deterministic seeded legal scrambles.
   Verify inverses, independent library agreement and exact distances at depths zero to five.
2. Adapters: implement the exact four routes, shared prompt contract, strict parsing,
   recorded request timing, bounded retries and persistent budgets. Verify with HTTP fixtures.
3. Orchestration: immutable puzzle records, four independent states, 30 executed moves,
   cancellation, suites, SSE replay, persisted outcomes, provenance and exports.
4. UI: original responsive 2x2 SVG arena, benchmark analysis and presentation, identity
   banner, separate animation pacing, clear simulated labels and explicit live call plan.
5. Verification: run pytest, lint, a five-puzzle simulated suite and actual browser checks;
   preserve machine-readable evidence and screenshots. Write setup and readiness reports.
6. Commit and push tested milestones to the user's existing repository main branch.

Constraints: no solution assist in live selection, no model fallback, no invented empirical
results, no credentials in Git, no live calls without explicit spending authorization.
