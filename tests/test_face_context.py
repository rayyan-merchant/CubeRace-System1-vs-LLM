"""Lossless observation formatting, not action-selection assistance."""
import json
import pytest
import pycuber
from backend.cube import FACES, SOLVED, MOVES, apply, sequence, _geometry
from backend.models import MODELS, payload, POLICY_VERSION, request_policy
from backend.config import Settings
from backend.stats import aggregate


def shared(body):
    return ({"state": body["state"], "question": body["questions"]["next_move"]}
            if "state" in body else json.loads(body["messages"][1]["content"]))


@pytest.mark.parametrize("moves", [[], ["R"], ["U'"], ["F2", "L", "B'", "D2"]]
                         + [["R", "F2", "L", "B'", "D2", move] for move in MOVES])
def test_face_grids_round_trip_and_independent_orientation(moves):
    state = sequence(SOLVED, moves)
    context = shared(payload(MODELS[0], state, []))["state"]
    assert context["cube_facelets"] == state
    faces = context.get("faces")
    assert isinstance(faces, dict), "Model context needs labeled lossless face grids"
    assert list(faces) == list(FACES)
    assert "".join(faces[f].replace("/", "") for f in FACES) == state
    cube = pycuber.Cube()
    colors = {str(cube.get_face(f)[1][1]): f for f in FACES}
    for move in moves:
        cube(move)
    for f in FACES:
        rows = faces[f].split("/")
        assert len(rows) == 3 and all(len(row) == 3 for row in rows)
        assert rows == ["".join(colors[str(s)] for s in row) for row in cube.get_face(f)]


def test_documented_top_right_neighbors_match_engine_geometry():
    from backend.models import FACE_ORIENTATION
    geo = _geometry()
    normals = {f: geo[i * 9 + 4][1] for i, f in enumerate(FACES)}
    for i, f in enumerate(FACES):
        center = geo[i * 9 + 4][0]
        top = tuple(a - b for a, b in zip(geo[i * 9 + 1][0], center))
        right = tuple(a - b for a, b in zip(geo[i * 9 + 5][0], center))
        assert FACE_ORIENTATION[f] == "/".join(next(n for n in FACES if normals[n] == v)
                                               for v in (top, right))
    instructions = shared(payload(MODELS[0], SOLVED, []))["question"]["instructions"]
    assert all(f"{f}={neighbors}" in instructions for f, neighbors in FACE_ORIENTATION.items())


@pytest.mark.parametrize("length", [0, 6, 7, 29])
def test_equivalent_compact_context_and_unchanged_settings(length):
    history = (list(MOVES) * 2)[:length]
    original = history.copy()
    bodies = [payload(m, apply(SOLVED, "R"), history) for m in MODELS]
    views = [shared(b) for b in bodies]
    assert all(v == views[0] for v in views)
    assert all({**b, "model": MODELS[0].id} == bodies[0] for b in bodies[:3])
    state, question = views[0]["state"], views[0]["question"]
    assert set(state) == {"cube_facelets", "faces", "recent_moves", "moves_remaining"}
    assert state["recent_moves"] == original[-6:] and history == original
    assert state["moves_remaining"] == 30 - length
    assert set(question["criteria"]) == set(MOVES)
    assert "each face matches its center" in question["instructions"]
    assert "fixed-center colors" in question["instructions"]
    assert "HTM" in question["instructions"]
    assert bodies[3]["max_tokens"] == 1024
    assert bodies[3]["reasoning"] == {"effort": "low"}
    assert bodies[3]["response_format"]["json_schema"]["strict"]


def test_new_condition_excludes_old_policy_without_mutation():
    assert POLICY_VERSION == "state-action-v4-facegrids"
    assert request_policy(Settings())["state_encoding"] == "URFDLB-row-major-slash-grids-v1"
    base = {"mode": "live", "kind": "suite", "tier": "primary", "puzzle_count": 5,
            "races": [], "request_policy": request_policy(Settings())}
    current = {**base, "policy_version": POLICY_VERSION}
    previous = {**base, "policy_version": "state-action-v3-recent6"}
    original = json.dumps(previous, sort_keys=True)
    stats = aggregate([current, previous])
    assert stats["suite_count"] == 1 and stats["excluded_policy_suites"] == 1
    assert json.dumps(previous, sort_keys=True) == original
