"""Non-secret startup identity for detecting stale local Python servers."""
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from . import models

ROOT = Path(__file__).resolve().parent.parent


def git_output(*args):
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                                timeout=5, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def runtime_info():
    return {"pid": os.getpid(), "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "python": str(Path(sys.executable).resolve()), "project_root": str(ROOT),
            "working_directory": str(Path.cwd().resolve()), "models_module": models.__file__,
            "git_commit": git_output("rev-parse", "HEAD"),
            "backend_dirty": git_output("status", "--porcelain", "--", "backend") != "",
            "policy_version": models.POLICY_VERSION, "history_window": models.HISTORY_WINDOW,
            "allowed_effective_ids": {k: sorted(v) for k, v in models.ALLOWED_EFFECTIVE_IDS.items()},
            "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted((ROOT / "backend").glob("*.py"))}}
