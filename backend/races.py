import asyncio
import time
import uuid
from datetime import datetime, timezone
from .cube import SOLVED, MOVES, apply, sequence, scramble, shortest_path, inverse
from .models import MODELS, ModelFailure, Router, POLICY_VERSION, request_policy
from .billing import run_billing, summarize


def puzzle(seed, tier):
    lo, width = {"warmup": (3, 2), "primary": (4, 2), "extension": (15, 6)}[tier]
    moves = scramble(seed, lo + seed % width)
    initial = sequence(SOLVED, moves)
    path = shortest_path(initial) if tier != "extension" else None
    return {"seed": seed, "tier": tier, "scramble": list(moves), "initial_state": initial,
            "shortest_distance": len(path) if path is not None else None,
            "proof_method": "complete bidirectional BFS, HTM" if path is not None else None,
            "solution_upper_bound": len(moves)}


class Manager:
    def __init__(self, settings, store, client):
        self.settings, self.store = settings, store
        self.router = Router(settings, store, client)
        self.active = {}

    async def start(self, config):
        # Serialize run admission: preparation has no external side effects.
        if self.active:
            raise ValueError("A run is active; abort it or wait for completion")
        run = {"id": uuid.uuid4().hex, "schema_version": 1,
               "timestamp": datetime.now(timezone.utc).isoformat(), "source": "CubeRace: System-1 vs LLM",
               "mode": config.mode, "kind": config.kind, "tier": config.tier,
               "seed": config.seed, "puzzle_count": config.puzzles,
               "metric": "HTM", "move_limit": 30, "policy_version": POLICY_VERSION,
               "condition": "no-scramble-agent-history-only", "status": "RUNNING",
               "request_policy": request_policy(self.settings),
               "budget": {"used": 0, "cap": config.call_cap}, "races": [], "events": []}
        run["budget"]["run_id"] = run["id"]
        # Reserve admission before yielding to the proof worker.
        self.active[run["id"]] = {"run": run, "task": None, "stop": asyncio.Event(),
                                  "blocked_models": {}, "schema_failures": {}}
        try:
            seen_states = set()
            next_seed = config.seed
            for i in range(config.puzzles):
                for _ in range(100):
                    p = await asyncio.to_thread(puzzle, next_seed, config.tier)
                    next_seed += 1
                    if p["initial_state"] not in seen_states and p["initial_state"] != SOLVED:
                        break
                else:
                    raise ValueError("Cannot generate enough distinct non-solved puzzles")
                seen_states.add(p["initial_state"])
                p.update(index=i, trials=[])
                for j, model in enumerate(MODELS):
                    p["trials"].append({"model_id": model.id, "label": model.label,
                        "effective_agent_id": None if config.mode == "live" else f"synthetic-fixture-{j + 1}",
                        "mode": config.mode, "status": "PENDING", "state": p["initial_state"],
                        "moves": [], "requests": [], "steps": [], "elapsed_ms": None,
                        "optimality_gap": None, "rank": None, "error": None})
                run["races"].append(p)
            self.store.save(run)
            self.active[run["id"]]["task"] = asyncio.create_task(self.execute(run))
            return run
        except BaseException:
            self.active.pop(run["id"], None)
            raise

    def emit(self, run, event, data):
        run["billing"] = run_billing(run)
        run["events"].append({"id": len(run["events"]) + 1, "event": event, "data": data})
        self.store.save(run)

    async def trial(self, run, race, trial, model, index):
        start = time.perf_counter()
        trial["status"] = "RUNNING"
        # Deterministic scripted UI exercise, explicitly unrelated to model quality.
        # An inverse script is used ONLY in simulation, never fed into Router.decide.
        script = []
        if run["mode"] == "simulated":
            script = [inverse(m) for m in reversed(race["scramble"])]
            if index == 1:
                script = ["U", "U'"] + script
            if index == 2:
                script = ["R"] * 30
            if index == 3:
                script = ["F", "F'"] + script
        try:
            while len(trial["moves"]) < 30:
                if self.active[run["id"]]["stop"].is_set():
                    raise asyncio.CancelledError
                if trial["state"] == SOLVED:
                    trial["status"] = "SOLVED"
                    break
                if run["mode"] == "simulated":
                    await asyncio.sleep(0.015)
                    move = script[len(trial["moves"]) % len(script)]
                else:
                    move = await self.router.decide(model, trial["state"], trial["moves"],
                                                    trial["requests"], run["budget"],
                                                    self.active[run["id"]]["schema_failures"])
                    trial["effective_agent_id"] = trial["requests"][-1]["effective_model_id"]
                if self.active[run["id"]]["stop"].is_set():
                    raise asyncio.CancelledError
                if move not in MOVES:
                    raise ModelFailure("API_ERROR", "Invalid action rejected by engine boundary")
                self.emit(run, "move_decided", {"race": race["index"], "model": index, "move": move})
                trial["state"] = apply(trial["state"], move)
                trial["moves"].append(move)
                latencies = [q["latency_ms"] for q in trial["requests"] if q["latency_ms"] is not None]
                step = {"step": len(trial["moves"]), "move": move, "state": trial["state"],
                        "avg_api_latency_ms": sum(latencies) / len(latencies) if latencies else None,
                        "elapsed_ms": (time.perf_counter() - start) * 1000}
                trial["steps"].append(step)
                self.emit(run, "move_applied", {"race": race["index"], "model": index, **step})
                if trial["state"] == SOLVED:
                    trial["status"] = "SOLVED"
                    break
            if trial["status"] == "RUNNING":
                trial["status"] = "MOVE_LIMIT"
        except asyncio.CancelledError:
            trial["status"] = "ABORTED"
        except ModelFailure as exc:
            trial["status"], trial["error"] = exc.status, str(exc)
            if exc.permanent:
                self.active[run["id"]]["blocked_models"][model.id] = str(exc)
            self.emit(run, "error", {"race": race["index"], "model": index,
                                      "status": exc.status, "message": str(exc)})
        except Exception:
            trial["status"], trial["error"] = "API_ERROR", "Internal trial failure; see local verification"
        finally:
            trial["billing"] = summarize(trial["requests"])
            trial["elapsed_ms"] = (time.perf_counter() - start) * 1000
            if trial["status"] == "SOLVED" and race["shortest_distance"] is not None:
                trial["optimality_gap"] = len(trial["moves"]) - race["shortest_distance"]
            self.emit(run, "model_finished", {"race": race["index"], "model": index, "trial": trial})

    async def execute(self, run):
        try:
            for race in run["races"]:
                if self.active[run["id"]]["stop"].is_set():
                    break
                run["budget"]["race_index"] = race["index"]
                self.emit(run, "race_started", {"race": race["index"], "puzzle": race,
                                                "mode": run["mode"]})
                tasks = []
                for i, (t, m) in enumerate(zip(race["trials"], MODELS)):
                    reason = self.active[run["id"]]["blocked_models"].get(m.id)
                    if reason:
                        t.update(status="NOT_RUN", error=f"Earlier permanent incompatibility: {reason}",
                                 billing=summarize([]))
                        self.emit(run, "model_finished", {"race": race["index"], "model": i, "trial": t})
                    else:
                        tasks.append(asyncio.create_task(self.trial(run, race, t, m, i)))
                self.active[run["id"]]["trials"] = tasks
                await asyncio.gather(*tasks)
                solved = sorted((t for t in race["trials"] if t["status"] == "SOLVED"),
                                key=lambda t: (t["elapsed_ms"], len(t["moves"])))
                for rank, trial in enumerate(solved, 1):
                    trial["rank"] = rank
                self.emit(run, "race_finished", {"race": race["index"], "trials": race["trials"]})
            aborted = self.active[run["id"]]["stop"].is_set()
            for race in run["races"]:
                for trial in race["trials"]:
                    if trial["status"] == "PENDING":
                        trial["status"] = "NOT_RUN"
            run["status"] = "ABORTED" if aborted else "COMPLETED"
            complete = all(t["status"] in ("SOLVED", "MOVE_LIMIT")
                           for r in run["races"] for t in r["trials"])
            run["evidence_status"] = ("SIMULATED_ONLY" if run["mode"] == "simulated" else
                                      "COMPLETE" if complete else "INCOMPLETE")
            self.emit(run, "aborted" if aborted else "run_finished", {"status": run["status"]})
        finally:
            run["billing"] = run_billing(run)
            self.store.save(run)
            self.active.pop(run["id"], None)

    async def abort(self, run_id):
        context = self.active.get(run_id)
        if context:
            context["stop"].set()
            for task in context.get("trials", []):
                task.cancel()
            if context["task"]:
                await context["task"]
        return self.store.get(run_id)

    async def close(self):
        for run_id in list(self.active):
            await self.abort(run_id)
