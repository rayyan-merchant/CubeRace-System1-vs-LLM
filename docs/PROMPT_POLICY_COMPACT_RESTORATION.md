# Compact prompt restoration and fixed Claude budget

The production policy is `state-action-v6-compact-choice`. It restores v4-style labeled
face grids and removes the v5 sticker-cycle appendix. The first sentence now asks for
one next action rather than ambiguously asking one choice to solve an entire cube.
This is a prompt-design correction, not demonstrated evidence of fewer refusals or
better solving. The frozen v4 and v5 payloads remain available and hash-tested; previous
results are never rewritten or pooled with the new condition.

## Exact shared instructions

```text
Which listed face turn should be executed next to solve this Rubik's Cube, within moves_remaining? Goal: each face matches its center. Letters denote fixed-center colors (URFDLB=up/right/front/down/left/back). cube_facelets is row-major URFDLB; faces uses '/' between rows. Outside views; top/right neighbors: U=B/R;R=U/B;F=U/R;D=F/R;L=U/F;B=U/L. Turns: degrees, CW clockwise, CCW counterclockwise, viewed at the named face. HTM: each listed turn=1 move; 30 max.
```

All four models receive the same current 54 facelets, six labeled grids, last six executed
agent moves, remaining allowance and all 18 action descriptions. Native Luna translates
this same question into OpenAI's native choice schema. Claude uses the equivalent context
and strict one-move JSON schema. There are no scramble sequences, search hints, current
successor states, heuristics, recommended moves, chain-of-thought requests or loop overrides.

## Claude output ceiling

The user explicitly authorized a fixed 2,048-token completion ceiling on October 26.
Reasoning remains low; mandatory reasoning stays enabled; retries remain zero. The fixed
limit is recorded before a run and never grows in response to failures. Output exhaustion
now has terminal status OUTPUT_LIMIT, distinct from connectivity/API failures. Historical
API_ERROR records with OUTPUT_LIMIT outcomes display the accurate label without changing
stored metrics or exports. A larger budget may still be exhausted and increases possible
spending. It does not guarantee valid JSON or a solved puzzle.

The private .env is left untouched. To persist the authorized setting across manual starts,
change only `CLAUDE_MAX_TOKENS=2048` there. The locally restarted server can use a process
variable override meanwhile, without changing that file. Provider-key spending limits and
persistent request counters are unchanged.

## Offline verification and cost boundaries

Exact prompt-character comparisons are in
[evidence](evidence/compact-prompt-restoration.json). Token estimates are not reported for
this revision because the local tokenizer is unavailable. No billed-token reduction,
provider success or solving improvement has been measured. All new validation is offline.

The native diagnostic keeps v4 as its default baseline. To inspect the new condition
without credentials, database access or inference:

```powershell
.venv\Scripts\python.exe verify_luna_openai.py --policy current --case 1
```

Adding --confirm-paid would authorize one paid request, but no such request was made
for this change. The production smoke command follows the new policy and native Luna
route; no benchmark should be described as verified by these offline fixtures.
