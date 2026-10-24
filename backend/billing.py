"""Response-reported accounting only: no estimates or extra network calls."""
import math
from decimal import Decimal


def number(value):
    return value if (isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value) and value >= 0) else None


def reported(usage):
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("completion_tokens_details")
    details = details if isinstance(details, dict) else {}
    return {"prompt_tokens": number(usage.get("prompt_tokens")),
            "completion_tokens": number(usage.get("completion_tokens")),
            "total_tokens": number(usage.get("total_tokens")),
            "reasoning_tokens": number(details.get("reasoning_tokens")),
            "cost_usd": number(usage.get("cost"))}


def summarize(requests, unrecorded=0):
    requests = list(requests)
    values = [reported(q.get("usage")) for q in requests]
    costs = [v["cost_usd"] for v in values if v["cost_usd"] is not None]
    count = len(requests) + unrecorded
    unknown = count - len(costs)
    known = float(sum((Decimal(str(c)) for c in costs), Decimal(0))) if costs else None
    totals = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"):
        observed = [v[key] for v in values if v[key] is not None]
        totals[key] = {"known_total": sum(observed) if observed else None,
                       "unknown_requests": count - len(observed)}
    return {"request_count": count, "known_cost_usd": known,
            "unknown_cost_requests": unknown, "cost_complete": unknown == 0,
            "total_cost_usd": (known if count else 0) if unknown == 0 else None,
            "tokens": totals}


def run_billing(run):
    trials = [t for race in run["races"] for t in race["trials"]]
    by_model = {model: summarize(q for trial in trials
                if trial["model_id"] == model for q in trial["requests"])
                for model in {t["model_id"] for t in trials}}
    return {**summarize(q for t in trials for q in t["requests"]), "by_model": by_model}
