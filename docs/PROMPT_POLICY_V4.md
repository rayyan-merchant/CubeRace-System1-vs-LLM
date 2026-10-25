# CubeRace prompt policy v4

`state-action-v4-facegrids` supersedes `state-action-v3-recent6` for new requests.
This is an observation/prompt change, not a change to cube mechanics or action selection.
Previous saved runs and billing remain intact. Aggregation already groups by policy
version and the full fixed request settings, selecting the newest suite's condition and
counting excluded suites. Replaying an old run never invokes the new policy or inference.
Diagnostics have their own report/ledger identity and never enter the suite dataset.

## Model-visible information

The state contains only:

- `cube_facelets`: authoritative 54 stickers, in URFDLB face order, row-major per face.
- `faces`: six labeled strings, each `ABC/DEF/GHI` (top, middle, bottom rows; left to right).
  Removing slashes and joining URFDLB reproduces `cube_facelets` exactly. No rotation,
  reflection, color conversion or new observation is applied.
- `recent_moves`: that model's last six executed moves, initially empty.
- `moves_remaining`: 30 minus the complete executed history length.

Sticker letters name fixed center colors: U/up, R/right, F/front, D/down, L/left, B/back.
They are symbolic colors, not instructions to rotate. The goal is that every sticker on
each of the six faces matches that face's center. This replaces the redundant explicit
54-character solved-state string. HTM remains explicit in instructions instead of a
second `metric` field. Run/CSV metadata still records `metric=HTM` and the 30-action limit.

## Exact orientation

View each face from outside the cube. Its top and right edges neighbor these named faces:

| Face | Top neighbor | Right neighbor |
|---|---|---|
| U | B | R |
| R | U | B |
| F | U | R |
| D | F | R |
| L | U | F |
| B | U | L |

This follows the existing engine's coordinate geometry; it does not rotate the cube.
Tests derive these neighbors from the engine's sticker coordinates and independently
compare all grid rows with PyCuber after scrambled states and all 18 move variants.
Clockwise and counterclockwise turns are viewed directly at the named face from outside.
Every listed action, including a 180-degree turn, consumes one HTM move.

## Shared instructions

```text
Choose one move to solve all six faces within moves_remaining. Goal: each face matches its center. Letters denote fixed-center colors (URFDLB=up/right/front/down/left/back). cube_facelets is row-major URFDLB; faces uses '/' between rows. Outside views; top/right neighbors: U=B/R;R=U/B;F=U/R;D=F/R;L=U/F;B=U/L. Turns: degrees, CW clockwise, CCW counterclockwise, viewed at the named face. HTM: each listed turn=1 move; 30 max.
```

All 18 criteria retain their Singmaster keys: U/U'/U2, R/R'/R2, F/F'/F2, D/D'/D2,
L/L'/L2, B/B'/B2. Descriptions use the face name and `90 CW`, `90 CCW`, or `180`.
The common degree and viewing convention avoids repeating long definitions per action.
All three Decisions payloads are identical except `model`. Claude receives exactly the
same state and question through chat, with the unchanged strict one-move JSON schema.

Claude remains low effort / 1,024 completion tokens; configured retries, model IDs,
timeouts, legal-move validation and the 30-action limit are unchanged. No chain of thought,
scramble, BFS/reference result, heuristic, successor preview, loop penalty or move override
is supplied. The new encoding is recorded in run request settings and each request record.

## Size measurements and limits

[Local comparison](evidence/prompt-v4-size-comparison.json) compares v3 with v4 using
the same 54-sticker state and histories of lengths 0, 6 and 7. The latter two verify that
the six-move window stops context growth. Counts cover compact state/question JSON plus
Claude's unchanged system text, excluding provider framing and schema overhead.

| Model content | History length | v3 tokens (proxy) | v4 tokens (proxy) | Change |
|---|---:|---:|---:|---:|
| Each Decisions model | 0 | 321 | 376 | +55 |
| Each Decisions model | 6 or 7 | 336 | 391 | +55 |
| Claude, including system text | 0 | 329 | 384 | +55 |
| Claude, including system text | 6 or 7 | 344 | 399 | +55 |

For empty history, shared Decisions content shrank from 1,157 to 1,039 characters,
but the added structured grids and precise orientation notation tokenize less compactly.
This is a comprehension change with a measured proxy token increase, not a token saving.

The tokenizer is **tiktoken 0.12.0 / o200k_base**, used solely as a local size proxy, not
as the tokenizer of these four assigned models. Exact provider-billed token changes are
unknown until explicitly authorized live responses return usage. Additional face grids
and orientation rules can increase token counts despite shorter character counts. No
measured model-performance or monetary saving is claimed.

## Diagnostics and scoring isolation

`verify_cube_diagnostics.py` previews without opening the database or an HTTP client.
`--confirm-paid` separately authorizes only Jev/Luna/Clef, two states each, at most six
requests total. Default depth 1 uses two fixed one-turn states; optional `--depth 2` uses
two distinct fixed two-turn states. These are diagnostics, not warmup/primary samples.
Both use the exact new payload, empty agent history and full 30-action allowance; the
model is not told the generating sequence, depth or expected first move.

Only after receiving a valid action does the local observer apply it to a temporary
state for scoring. For depth 1 it must solve; for depth 2 one additional legal action
must be able to solve. The observer never feeds those computations back into requests,
never changes an action, and never requests a second action. Failures remain unscored
(`null`), incorrect legal moves are `false`, and valid correct first actions are `true`.
Reports show correct, valid and planned counts separately; API failure is not silently
counted as an incorrect move. The expected answers are not included in model input.

The CLI requires live configuration and zero retries, refuses an active saved run or
insufficient remaining six-request budget, never resets/increases budgets, and journals
requests through the existing Router/Store. Permanent model incompatibility skips that
model on the second case without fallback. HTTP failures have no automatic retry.
Reports have unique timestamped paths; reported usage/cost is retained and missing costs
remain unknown. No external inference was executed to prepare or test these diagnostics.

Claude is deliberately absent from this inexpensive diagnostic and remains present in
the required final assignment benchmark. Diagnostic success cannot establish four/five-turn
solving performance; fixed test states must not be used to tune and then claim held-out
benchmark accuracy.
