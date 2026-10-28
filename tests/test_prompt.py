"""The single production prompt preserves its content and interface fairness."""
import hashlib
import inspect
import json
import pytest
from backend.cube import SOLVED, MOVES, sequence
from backend.models import MODELS, payload


def test_production_payloads_remain_identical_after_repository_cleanup():
    cases = [payload(m, state, (list(MOVES) * 2)[:n])
             for state in (SOLVED, sequence(SOLVED, ["R", "F2", "D2", "F2"]))
             for n in (0, 6, 7, 29) for m in MODELS]
    assert hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest() == (
        "a707cf5f2a7a4b7e4863a367d36e2872c1af092620cbd215feea43e241d2ca8f")


def test_only_one_prompt_can_be_selected():
    assert set(inspect.signature(payload).parameters) == {"model", "state", "history", "settings"}
    with pytest.raises(TypeError):
        payload(MODELS[0], SOLVED, [], policy_version="alternative")
