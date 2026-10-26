import asyncio
import csv
import io
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .config import Settings
from .cube import ProofLimit
from .models import MODELS
from .races import Manager, puzzle
from .stats import aggregate
from .store import Store
from .billing import summarize
from .runtime import runtime_info

ROOT = Path(__file__).resolve().parent.parent


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["simulated", "live"] = "simulated"
    kind: Literal["race", "suite"] = "race"
    tier: Literal["warmup", "primary", "extension"] = "primary"
    seed: int = Field(default=2026, ge=0, le=2**31 - 100)
    puzzles: int = Field(default=1, ge=1, le=25)
    call_cap: int = Field(default=0, ge=0, le=12000)
    confirm_paid_calls: bool = False

    @model_validator(mode="after")
    def coherent(self):
        if self.kind == "race" and self.puzzles != 1:
            raise ValueError("A race uses one puzzle")
        return self


def create_app(settings=None, transport=None):
    settings = settings or Settings.env()
    # Capture once, never recompute from changed files when an old server is queried.
    startup_runtime = runtime_info()
    startup_runtime["database"] = str(Path(settings.database).resolve())

    @asynccontextmanager
    async def lifespan(app):
        store = Store(settings.database)
        store.recover()
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            app.state.store = store
            app.state.manager = Manager(settings, store, client)
            yield
            await app.state.manager.close()
        store.close()

    app = FastAPI(title="CubeRace: System-1 vs LLM", lifespan=lifespan)
    def credentials_ready():
        return bool(settings.key.strip() and (
            settings.luna_provider != "openai" or settings.openai_key.strip()))

    @app.middleware("http")
    async def local_guard(request, call_next):
        host = request.url.hostname
        if host not in {"127.0.0.1", "localhost", "::1", "testserver"}:
            return JSONResponse({"detail": "Local application: unrecognized Host"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.url.netloc:
                return JSONResponse({"detail": "Cross-origin mutation refused"}, status_code=403)
        response = await call_next(request)
        # Local experiment controls and ES modules must not outlive a source update.
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "name": "CubeRace: System-1 vs LLM", "runtime": startup_runtime}

    @app.get("/api/config")
    async def config():
        return {"models": [asdict(m) for m in MODELS], "move_limit": 30,
            "student_name": settings.student_name or "SET STUDENT_NAME",
            "student_roll": settings.student_roll or "SET STUDENT_ROLL",
            "identity_configured": bool(settings.student_name.strip() and settings.student_roll.strip()),
            "live_enabled": bool(credentials_ready() and settings.allow_live and not settings.mock_mode),
            "luna_provider": settings.luna_provider,
            "live_source_label": "Live APIs (Luna: OpenAI)" if settings.luna_provider == "openai" else "Live OpenRouter",
            "default_mode": "simulated", "budget_limit": settings.budget,
            "budget_used": app.state.store.used(), "retries": settings.retries,
            "recommended_race_cap": len(MODELS) * 30 * (1 + settings.retries),
            "claude_reasoning_effort": settings.claude_reasoning_effort,
            "claude_max_tokens": settings.claude_max_tokens,
            "billing": app.state.store.billing()}

    @app.get("/api/puzzle")
    async def get_puzzle(seed: int = 2026, tier: Literal["warmup", "primary", "extension"] = "primary"):
        try:
            return await asyncio.to_thread(puzzle, seed, tier)
        except ProofLimit as exc:
            raise HTTPException(422, str(exc))

    @app.post("/api/runs", status_code=201)
    async def start(body: StartRequest):
        if body.mode == "live":
            if not credentials_ready() or not settings.allow_live or settings.mock_mode:
                raise HTTPException(409, "Live disabled: configure required provider keys, ALLOW_LIVE=true and OPENROUTER_MOCK_MODE=false")
            if not body.confirm_paid_calls or body.call_cap < 1:
                raise HTTPException(422, "Explicit paid-call confirmation and positive cap required")
            if app.state.store.used() >= settings.budget:
                raise HTTPException(409, "Persistent API budget exhausted")
        try:
            run = await app.state.manager.start(body)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        except ProofLimit as exc:
            raise HTTPException(422, str(exc))
        return {"id": run["id"], "status": run["status"], "mode": run["mode"]}

    def fetch(run_id):
        run = app.state.store.get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        run["billing"] = app.state.store.run_billing(run)
        return run

    @app.get("/api/runs")
    async def runs():
        return [{**{k: r[k] for k in ("id", "timestamp", "mode", "tier", "kind", "status", "puzzle_count")},
                 "billing": app.state.store.run_billing(r)}
                for r in app.state.store.all()]

    @app.get("/api/runs/{run_id}")
    async def result(run_id: str):
        return fetch(run_id)

    @app.post("/api/runs/{run_id}/abort")
    async def abort(run_id: str):
        fetch(run_id)
        await app.state.manager.abort(run_id)
        return {"status": fetch(run_id)["status"]}

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str, request: Request, after: int = 0):
        fetch(run_id)
        try:
            cursor = max(after, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise HTTPException(422, "Invalid event cursor")

        async def stream():
            nonlocal cursor
            while True:
                if await request.is_disconnected():
                    # Streaming is a replayable subscriber. Work belongs to the explicit
                    # start, not the connection; releasing this generator leaks no task.
                    return
                run = fetch(run_id)
                for item in run["events"][cursor:]:
                    cursor = item["id"]
                    yield f"id: {cursor}\nevent: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
                if run["status"] != "RUNNING":
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.08)
        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/stats")
    async def stats(mode: Literal["live", "simulated"] = "live",
                    tier: Literal["warmup", "primary", "extension"] = "primary"):
        return aggregate(app.state.store.all(), mode, tier)

    @app.get("/api/runs/{run_id}/export/{format}")
    async def export(run_id: str, format: Literal["json", "csv", "steps.csv", "requests.csv"]):
        run = fetch(run_id)
        headers = {"Content-Disposition": f'attachment; filename="cuberace-{run_id}.{format}"'}
        if format == "json":
            return JSONResponse(run, headers=headers)
        rows = []
        for race in run["races"]:
            for trial in race["trials"]:
                base = {"run_id": run_id, "timestamp": run["timestamp"], "source": run["source"],
                        "mode": run["mode"], "policy_version": run["policy_version"],
                        "condition": run["condition"], "metric": "HTM", "move_limit": 30,
                        "seed": race["seed"], "tier": race["tier"],
                        "initial_state": race["initial_state"], "scramble": " ".join(race["scramble"]),
                        "model_id": trial["model_id"], "effective_agent_id": trial["effective_agent_id"],
                        "request_policy": run.get("request_policy"),
                        "status": trial["status"], "shortest_distance": race["shortest_distance"]}
                if format == "steps.csv":
                    rows.extend({**base, **step} for step in trial["steps"])
                elif format == "requests.csv":
                    rows.extend({**base, **q} for q in trial["requests"])
                else:
                    rows.append({**base, "executed_moves": len(trial["moves"]),
                        "moves": " ".join(trial["moves"]), "elapsed_ms": trial["elapsed_ms"],
                        "optimality_gap": trial["optimality_gap"], "rank": trial["rank"],
                        "request_count": len(trial["requests"]),
                        **summarize(trial["requests"])})
        out = io.StringIO(newline="")
        fields = list(dict.fromkeys(k for row in rows for k in row)) or ["mode", "run_id"]
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()})
        return Response(out.getvalue(), media_type="text/csv", headers=headers)

    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "frontend" / "index.html")

    return app


app = create_app()
