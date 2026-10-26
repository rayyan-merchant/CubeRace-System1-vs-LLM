"""Native OpenAI Decisions wire contract; no solver or provider fallback."""
from .cube import MOVES
from .billing import number

ENDPOINT = "https://api.openai.com/v1/decisions"
MODEL = "gpt-6-luna"


class NativeSchemaError(ValueError):
    pass


class NativeIdentityError(ValueError):
    pass


class NativeRefusal(ValueError):
    pass


def translate(baseline):
    question = baseline["questions"]["next_move"]
    return {"model": MODEL,
            "input": [{"role": "user", "content": [{"type": "input_json", "data": baseline["state"]}]}],
            "questions": [{"type": "choice", "name": "next_move", "instructions": question["instructions"],
                           "choices": [{"value": move, "description": description}
                                       for move, description in question["criteria"].items()]}]}


def parse_native(body):
    if not isinstance(body, dict):
        raise NativeSchemaError("Expected native Decision object")
    if body.get("model") != MODEL:
        raise NativeIdentityError("Missing or unrecognized native model identity; no substitution")
    answers = body.get("answers")
    if not isinstance(answers, list) or len(answers) != 1 or not isinstance(answers[0], dict):
        raise NativeSchemaError("Expected one native answer in an array")
    answer = answers[0]
    if answer.get("name") != "next_move":
        raise NativeSchemaError("Unexpected native question name")
    if answer.get("type") == "refusal":
        raise NativeRefusal("OpenAI declined the next_move question")
    if answer.get("type") != "choice":
        raise NativeSchemaError("Expected native choice answer")
    move = answer.get("choice")
    if not isinstance(move, str) or move not in MOVES:
        raise ValueError("Expected exactly one legal move")
    confidence = number(answer.get("confidence"))
    values = answer.get("probabilities")
    if confidence is None or confidence > 1 or not isinstance(values, list) or len(values) != 18:
        raise NativeSchemaError("Missing or invalid native confidence/probabilities")
    probabilities = {}
    for item in values:
        if not isinstance(item, dict):
            raise NativeSchemaError("Invalid native probability entry")
        action, probability = item.get("value"), number(item.get("probability"))
        if (not isinstance(action, str) or action not in MOVES or action in probabilities
                or probability is None or probability > 1):
            raise NativeSchemaError("Invalid or duplicate native probability option")
        probabilities[action] = probability
    return move, {"confidence": confidence, "probabilities": probabilities,
                  "provider_probabilities": values}
