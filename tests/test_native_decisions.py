"""Native provider response validation with offline fixtures."""
import pytest
from backend import native_decisions as native
from backend.cube import MOVES
from tests.test_models import native_response


@pytest.mark.parametrize("bad", ["R U", " R", "R\n", "r", True, None, ["R"]])
def test_native_illegal_moves_rejected(bad):
    module = native
    with pytest.raises(ValueError):
        module.parse_native(native_response(bad))


@pytest.mark.parametrize("move", MOVES)
def test_native_legal_move_is_never_replaced_by_probability_ranking(move):
    selected, metadata = native.parse_native(native_response(move))
    assert selected == move and len(metadata["probabilities"]) == 18


@pytest.mark.parametrize("bad", ["extra_answer", "wrong_name", "map_probabilities", "duplicate", "unknown",
                                 "negative", "nan", "boolean_confidence"])
def test_native_schema_and_probability_validation(bad):
    body = native_response()
    answer = body["answers"][0]
    if bad == "extra_answer":
        body["answers"].append(answer.copy())
    elif bad == "wrong_name":
        answer["name"] = "different"
    elif bad == "map_probabilities":
        answer["probabilities"] = {"R": 1}
    elif bad == "duplicate":
        answer["probabilities"][1]["value"] = answer["probabilities"][0]["value"]
    elif bad == "unknown":
        answer["probabilities"][0]["value"] = "X"
    elif bad in ("negative", "nan"):
        answer["probabilities"][0]["probability"] = -1 if bad == "negative" else float("nan")
    else:
        answer["confidence"] = True
    with pytest.raises(ValueError):
        native.parse_native(body)
