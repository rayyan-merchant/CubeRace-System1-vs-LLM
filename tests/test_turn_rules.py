"""Decode general prompt rules on unique sticker identities; never select actions."""
import importlib
import hashlib
import json
import pytest
import pycuber
from backend.cube import FACES, MOVES, SOLVED, apply, permutations, sequence
from backend.models import MODELS, payload, POLICY_VERSION
from backend.stats import aggregate
from tests.test_face_context import shared


def rules_module():
    assert importlib.util.find_spec("backend.turn_rules"), "Missing explicit general sticker rules"
    return importlib.import_module("backend.turn_rules")


def decode_cw(face):
    rules = rules_module()
    forward = list(range(54))
    def cycle(groups):
        for src, dst in zip(groups, groups[1:] + groups[:1]):
            for a, b in zip(src, dst):
                forward[a] = b
    base = FACES.index(face) * 9
    for c in rules.FACE_CW_CYCLES:
        cycle([[base + int(i) - 1] for i in c])
    strips = rules.STRIP_CW_CYCLES[face]
    cycle([[FACES.index(s[0]) * 9 + int(i) - 1 for i in s[1:]] for s in strips])
    return forward


@pytest.mark.parametrize("move", MOVES)
def test_rules_reconstruct_exact_engine_permutation(move):
    forward = decode_cw(move[0])
    assert len(set(forward)) == 54
    turns = 3 if move.endswith("'") else 2 if move.endswith("2") else 1
    expected = list(range(54))
    for _ in range(turns):
        expected = [forward[i] for i in expected]
    # Engine permutations map destination to source; prompt cycles map source to destination.
    assert expected == [permutations()[move].index(i) for i in range(54)]
    assert sum(i != dest for i, dest in enumerate(expected)) == 20


@pytest.mark.parametrize("move", MOVES)
def test_rules_on_scrambled_state_against_independent_library(move):
    rules = rules_module()
    forward = decode_cw(move[0])
    cube = pycuber.Cube()
    colors = {str(cube.get_face(f)[1][1]): f for f in FACES}
    history = ["R", "F2", "D'", "L", "B2", "U"]
    state = sequence(SOLVED, history)
    for action in history:
        cube(action)
    for _ in range(3 if move.endswith("'") else 2 if move.endswith("2") else 1):
        after = list(state)
        for src, dst in enumerate(forward):
            after[dst] = state[src]
        state = "".join(after)
    cube(move)
    independent = "".join(colors[str(s)] for f in FACES for row in cube.get_face(f) for s in row)
    assert state == independent
    assert all(">".join(s) in rules.TURN_RULES for s in rules.FACE_CW_CYCLES)
    assert all(">".join(strips) in rules.TURN_RULES for strips in rules.STRIP_CW_CYCLES.values())


def test_rules_are_state_independent_equivalent_and_v4_is_preserved():
    rules = rules_module()
    assert POLICY_VERSION == "state-action-v6-compact-choice"
    for state in (SOLVED, apply(SOLVED, "L2")):
        views = [shared(payload(m, state, [], policy_version="state-action-v5-permutations")) for m in MODELS]
        assert all(v == views[0] for v in views)
        baseline = shared(payload(MODELS[0], state, [], policy_version="state-action-v4-facegrids"))
        assert views[0]["state"] == baseline["state"]
        assert views[0]["question"]["criteria"] == baseline["question"]["criteria"]
        assert views[0]["question"]["instructions"] == baseline["question"]["instructions"] + rules.TURN_RULES
    with pytest.raises(ValueError):
        payload(MODELS[0], SOLVED, [], policy_version="unknown")
    base = {"mode": "live", "kind": "suite", "tier": "primary", "puzzle_count": 5, "races": []}
    old = {**base, "policy_version": "state-action-v4-facegrids"}
    original = json.dumps(old, sort_keys=True)
    stats = aggregate([{**base, "policy_version": POLICY_VERSION}, old])
    assert stats["excluded_policy_suites"] == 1 and stats["suite_count"] == 1
    assert json.dumps(old, sort_keys=True) == original


def test_frozen_v4_payloads_match_pre_change_baseline():
    state = sequence(SOLVED, ["R", "F2", "D2", "F2"])
    cases = {str(n): [payload(m, state, ["U", "U'", "R", "R2", "F2", "L", "D"][:n],
                             policy_version="state-action-v4-facegrids") for m in MODELS]
             for n in (0, 6, 7)}
    digest = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
    assert digest == "4028dfc49462aa94f1f48e34824ebf369abffc7822abf3dc8d24316279fa6181"


def test_active_compact_prompt_restores_grids_and_single_step_without_cycle_block():
    from backend.models import MODELS, payload, POLICY_VERSION, V4_INSTRUCTIONS, V5_POLICY_VERSION
    from backend.cube import SOLVED
    from backend.native_decisions import translate
    assert POLICY_VERSION == 'state-action-v6-compact-choice'
    active = payload(MODELS[0], SOLVED, [])
    old = payload(MODELS[0], SOLVED, [], policy_version=V5_POLICY_VERSION)
    question = active['questions']['next_move']
    assert 'executed next' in question['instructions']
    assert question['instructions'].endswith(V4_INSTRUCTIONS.split('Goal: ', 1)[1])
    assert 'source>destination' not in question['instructions']
    assert len(question['instructions']) < len(old['questions']['next_move']['instructions'])
    assert active['state'] == old['state'] and question['criteria'] == old['questions']['next_move']['criteria']
    native = translate(payload(MODELS[1], SOLVED, []))
    assert native['questions'][0]['instructions'] == question['instructions']
    assert native['input'][0]['content'][0]['data'] == active['state']


def test_frozen_v5_payloads_stay_identical_after_compact_restoration():
    from backend.models import V5_POLICY_VERSION
    state = sequence(SOLVED, ['R', 'F2', 'D2', 'F2'])
    cases = {str(n): [payload(m, state, ['U', "U'", 'R', 'R2', 'F2', 'L', 'D'][:n],
                              policy_version=V5_POLICY_VERSION) for m in MODELS] for n in (0, 6, 7)}
    assert hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest() == '11df10afde6283369ed69e2f51c77427e54c58b545f67af1ee7a06f5ec4f53bc'
