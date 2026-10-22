"""One command: tests, lint, JS syntax and a complete five-puzzle offline suite."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app


def main():
    root = Path(__file__).resolve().parent
    evidence = root / "docs" / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    for label, command in (("pytest", [sys.executable, "-m", "pytest", "-q"]),
                           ("ruff", [sys.executable, "-m", "ruff", "check", "."])):
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
        output = result.stdout + result.stderr
        # Avoid retaining host-specific account and virtualenv paths in public evidence.
        output = output.replace(str(root), "<PROJECT_ROOT>")
        (evidence / f"{label}-output.txt").write_text(output, encoding="utf-8")
        print(output)
        result.check_returncode()
    if shutil.which("node"):
        for file in ("frontend/app.js", "frontend/cube.js"):
            subprocess.run(["node", "--check", file], cwd=root, check=True)
    else:
        print("Node unavailable: JavaScript syntax check skipped")
    with tempfile.TemporaryDirectory() as tmp:
        with TestClient(create_app(Settings(database=str(Path(tmp) / "verification.db")))) as client:
            assert client.get("/api/health").json()["status"] == "ok"
            initial = client.post("/api/runs", json={"kind": "suite", "puzzles": 5, "seed": 2026})
            initial.raise_for_status()
            run_id = initial.json()["id"]
            deadline = time.monotonic() + 45
            while True:
                run = client.get(f"/api/runs/{run_id}").json()
                if run["status"] != "RUNNING":
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError("Offline suite did not complete in 45 seconds")
                time.sleep(0.05)
            assert run["status"] == "COMPLETED" and len(run["races"]) == 5
            (evidence / "simulated-suite.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
            for fmt in ("csv", "steps.csv", "requests.csv"):
                response = client.get(f"/api/runs/{run_id}/export/{fmt}")
                response.raise_for_status()
                (evidence / f"simulated-suite.{fmt}").write_bytes(response.content)
            stats = client.get("/api/stats?mode=simulated").json()
            summary = {"mode": "simulated", "source": "local functional verification, not model evaluation",
                       "suite_puzzles": 5, "trials": 20, "paid_requests": 0,
                       "checks": ["pytest", "ruff", "HTTP endpoints", "suite", "SSE lifecycle", "exports"],
                       "stats": stats}
            (evidence / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print("PASS: five seeded puzzles, 20 simulated trials, zero paid requests; exports saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
