"""Geometric facelet permutations. Face orientation follows the standard URFDLB net."""
import random
from collections import Counter
from functools import lru_cache

FACES = "URFDLB"
SOLVED = "".join(f * 9 for f in FACES)
MOVES = tuple(f + s for f in FACES for s in ("", "'", "2"))


def inverse(move):
    if move not in MOVES:
        raise ValueError("Illegal Singmaster action")
    return move if move.endswith("2") else move[0] if move.endswith("'") else move + "'"


def _geometry():
    items = []
    for face in FACES:
        for row in range(3):
            for col in range(3):
                a, b = col - 1, row - 1
                pos, normal = {
                    "U": ((a, 1, b), (0, 1, 0)),
                    "R": ((1, -b, -a), (1, 0, 0)),
                    "F": ((a, -b, 1), (0, 0, 1)),
                    "D": ((a, -1, -b), (0, -1, 0)),
                    "L": ((-1, -b, a), (-1, 0, 0)),
                    "B": ((-a, -b, -1), (0, 0, -1)),
                }[face]
                items.append((pos, normal))
    return items


def _rotate(v, axis, sign):
    x, y, z = v
    if axis == 0:
        return x, -sign * z, sign * y
    if axis == 1:
        return sign * z, y, -sign * x
    return -sign * y, sign * x, z


@lru_cache(maxsize=1)
def permutations():
    geo = _geometry()
    lookup = {v: i for i, v in enumerate(geo)}
    result = {}
    for face in FACES:
        axis, layer = {"U": (1, 1), "D": (1, -1), "R": (0, 1),
                       "L": (0, -1), "F": (2, 1), "B": (2, -1)}[face]
        perm = list(range(54))
        for src, (pos, normal) in enumerate(geo):
            if pos[axis] == layer:
                dest = lookup[(_rotate(pos, axis, -layer), _rotate(normal, axis, -layer))]
                perm[dest] = src
        for suffix, turns in (("", 1), ("2", 2), ("'", 3)):
            p = list(range(54))
            for _ in range(turns):
                p = [p[i] for i in perm]
            result[face + suffix] = tuple(p)
    return result


def validate(state):
    # Public operations only use engine-generated reachable states. This checks serialization,
    # not arbitrary cubie parity; accepting arbitrary browser-supplied states is intentionally absent.
    if len(state) != 54 or Counter(state) != Counter(SOLVED):
        raise ValueError("Expected 54 URFDLB facelets, nine of each color")
    return state


def apply(state, move):
    if move not in MOVES:
        raise ValueError("Illegal Singmaster action")
    return "".join(state[i] for i in permutations()[move])


def sequence(state, moves):
    for move in moves:
        state = apply(state, move)
    return state


def scramble(seed, length):
    rng = random.Random(seed)
    path = []
    for _ in range(length):
        path.append(rng.choice([m for m in MOVES if not path or m[0] != path[-1][0]]))
    return tuple(path)


class ProofLimit(Exception):
    pass


def shortest_path(state, max_depth=5, max_nodes=150_000):
    """Complete layer-by-layer bidirectional BFS; returned path solves the input.

    Each side holds full shortest paths. A full layer is scanned before choosing its
    minimum intersection. No pruning heuristic or scramble knowledge is used.
    """
    if state == SOLVED:
        return ()
    left, right = {state: ()}, {SOLVED: ()}
    fronts = [[state], [SOLVED]]
    tables = [left, right]
    for depth in range(max_depth):
        side = depth % 2
        own, other = tables[side], tables[1 - side]
        new, candidates = [], []
        for current in fronts[side]:
            path = own[current]
            for move in MOVES:
                if path and move[0] == path[-1][0]:
                    continue
                child = apply(current, move)
                if child in own:
                    continue
                own[child] = path + (move,)
                new.append(child)
                if child in other:
                    lp, rp = (own[child], other[child]) if side == 0 else (other[child], own[child])
                    candidates.append(lp + tuple(inverse(m) for m in reversed(rp)))
                if len(left) + len(right) > max_nodes:
                    raise ProofLimit("Exact solver node cap exceeded; no distance claimed")
        fronts[side] = new
        if candidates:
            answer = min(candidates, key=len)
            assert sequence(state, answer) == SOLVED
            return answer
    raise ProofLimit("Exact solver depth cap exceeded; no distance claimed")
