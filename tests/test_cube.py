from collections import Counter
import random
import pytest
from backend.cube import (SOLVED, MOVES, FACES, ProofLimit, apply, inverse, permutations,
                          scramble, sequence, shortest_path, validate)


@pytest.mark.parametrize("move", MOVES)
def test_move_group_and_conservation(move):
    state = sequence(SOLVED, scramble(7, 20))
    moved = apply(state, move)
    assert moved != state
    assert Counter(moved) == Counter(state)
    assert apply(moved, inverse(move)) == state
    assert sequence(state, [move] * 4) == state
    assert len(set(permutations()[move])) == 54
    assert all(moved[i * 9 + 4] == FACES[i] for i in range(6))


@pytest.mark.parametrize("face", FACES)
def test_half_turn_is_one_action(face):
    assert apply(SOLVED, face + "2") == sequence(SOLVED, [face, face])


def test_scramble_reproducibility_and_inverse():
    for seed in range(30):
        moves = scramble(seed, 20)
        assert moves == scramble(seed, 20)
        assert all(a[0] != b[0] for a, b in zip(moves, moves[1:]))
        assert sequence(sequence(SOLVED, moves), [inverse(m) for m in reversed(moves)]) == SOLVED
    assert scramble(1, 20) != scramble(2, 20)


@pytest.mark.parametrize("bad", ["X", "r", "R U", "R3", "", " U"])
def test_invalid_moves(bad):
    with pytest.raises(ValueError):
        apply(SOLVED, bad)


def test_bad_serialization():
    with pytest.raises(ValueError):
        validate("U" * 54)


@pytest.mark.parametrize("depth", range(6))
@pytest.mark.parametrize("seed", [7, 19, 2026])
def test_exact_solver(depth, seed):
    state = sequence(SOLVED, scramble(seed, depth))
    path = shortest_path(state)
    assert len(path) <= depth
    assert sequence(state, path) == SOLVED
    if path:
        with pytest.raises(ProofLimit):
            shortest_path(state, max_depth=len(path) - 1)


def test_proof_caps():
    with pytest.raises(ProofLimit):
        shortest_path(sequence(SOLVED, ["R", "U", "F"]), max_nodes=2)


@pytest.mark.parametrize("seed", [0, 18, 91])
def test_against_independent_pycuber(seed):
    import pycuber
    cube = pycuber.Cube()
    color_to_face = {str(cube.get_face(f)[1][1]): f for f in FACES}
    path = random.Random(seed).choices(MOVES, k=25)
    state = SOLVED
    for move in path:
        cube(move)
        state = apply(state, move)
        independent = "".join(color_to_face[str(sticker)] for f in FACES
                              for row in cube.get_face(f) for sticker in row)
        assert state == independent
