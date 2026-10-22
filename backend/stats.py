from collections import Counter
from statistics import mean
from .models import MODELS


def avg(items):
    values = [x for x in items if x is not None]
    return mean(values) if values else None


def aggregate(runs, mode="live", tier="primary"):
    # Primary suites form the scientific sample; warmups/races/extensions cannot silently pool.
    selected = [r for r in runs if r["mode"] == mode and r["tier"] == tier and r["kind"] == "suite"]
    rows = []
    for model in MODELS:
        trials = [t for r in selected for p in r["races"] for t in p["trials"]
                  if t["model_id"] == model.id and t["status"] not in ("PENDING", "NOT_RUN", "RUNNING")]
        solved = [t for t in trials if t["status"] == "SOLVED"]
        requests = [q for t in trials for q in t["requests"]]
        rows.append({"model_id": model.id, "label": model.label,
            "agent": model.label if mode == "live" else f"Synthetic fixture {len(rows) + 1}",
            "attempted": len(trials), "solved": len(solved),
            "planned": sum(r["puzzle_count"] for r in selected),
            "solve_rate": 100 * len(solved) / len(trials) if trials else None,
            "avg_api_latency_ms": avg(q["latency_ms"] for q in requests),
            "request_count": len(requests),
            "avg_attempt_ms": avg(t["elapsed_ms"] for t in trials),
            "mean_moves_all": avg(len(t["moves"]) for t in trials),
            "mean_moves_solved": avg(len(t["moves"]) for t in solved),
            "mean_optimality_gap": avg(t["optimality_gap"] for t in solved),
            "proven_solved_count": sum(t["optimality_gap"] is not None for t in solved),
            "malformed": sum(q["outcome"] == "MALFORMED" for q in requests),
            "retries": sum(q["retry"] > 0 for q in requests),
            "statuses": dict(Counter(t["status"] for t in trials))})
    return {"mode": mode, "tier": tier, "kind": "suite", "rows": rows,
            "suite_count": len(selected), "analysis": analysis(rows, mode),
            "denominator": "All terminal started trials, including infrastructure failures; NOT_RUN excluded"}


def analysis(rows, mode):
    insufficient = "Insufficient live measured data; no model conclusion is supported."
    answers = [insufficient] * 5
    if mode != "live":
        return ["Simulated UI fixtures are not evidence of OpenRouter model performance."] * 5
    sampled = [r for r in rows if r["request_count"]]
    if sampled:
        fastest = min(sampled, key=lambda r: r["avg_api_latency_ms"])
        answers[0] = f"Lowest observed mean request latency: {fastest['label']} ({fastest['avg_api_latency_ms']:.1f} ms). Retries and errors included."
    if all(r["attempted"] >= 5 for r in rows):
        best = max(r["solve_rate"] for r in rows)
        winners = ", ".join(r["label"] for r in rows if r["solve_rate"] == best)
        answers[1] = f"Highest observed solve rate: {winners}, {best:.1f}%. Review status counts and missing trials."
        quality = [r for r in rows if r["proven_solved_count"]]
        if quality:
            shortest = min(quality, key=lambda r: r["mean_moves_solved"])
            answers[2] = f"Fewest mean solved moves: {shortest['label']}, {shortest['mean_moves_solved']:.2f}; mean proven gap {shortest['mean_optimality_gap']:.2f} HTM. Solved subsets may differ."
        if sampled:
            answers[3] = f"Fastest observed: {fastest['label']}; highest solve rate: {winners}. This is descriptive evidence, without a significance claim."
        successful = [r for r in rows if r["solved"]]
        if successful:
            choice = min(successful, key=lambda r: (-r["solve_rate"], r["mean_moves_solved"],
                                                    r["avg_api_latency_ms"] or float("inf")))
            answers[4] = (f"For a completion-first application, provisionally choose {choice['label']}: "
                f"{choice['solve_rate']:.1f}% solved in {choice['attempted']} attempts, "
                f"{choice['mean_moves_solved']:.2f} mean solved moves and "
                f"{choice['avg_api_latency_ms']:.1f} ms mean request latency. "
                "Check errors, cost and larger repeated samples before adoption. "
                "A hybrid was not evaluated, so no hybrid advantage is established.") if choice["avg_api_latency_ms"] is not None else insufficient
        else:
            answers[4] = "No evaluated model solved a puzzle. No model or hybrid can be recommended from this sample; investigate failures and collect further evidence."
    return answers
