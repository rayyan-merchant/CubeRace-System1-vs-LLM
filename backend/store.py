"""Local snapshots and a persistent, atomic application-wide charged-request counter."""
import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY, used INTEGER)")
        self.db.execute("INSERT OR IGNORE INTO budget VALUES (1,0)")
        self.db.commit()

    def consume(self, ceiling):
        with self.db:
            cur = self.db.execute("UPDATE budget SET used=used+1 WHERE id=1 AND used < ?", (ceiling,))
        return cur.rowcount == 1

    def used(self):
        return self.db.execute("SELECT used FROM budget WHERE id=1").fetchone()[0]

    def save(self, run):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO runs VALUES (?,?)",
                            (run["id"], json.dumps(run, allow_nan=False)))

    def get(self, run_id):
        row = self.db.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT body FROM runs ORDER BY rowid DESC")]

    def recover(self):
        for run in self.all():
            if run["status"] == "RUNNING":
                run["status"] = "INTERRUPTED"
                for race in run["races"]:
                    for trial in race["trials"]:
                        if trial["status"] == "RUNNING":
                            trial["status"] = "ABORTED"
                            trial["error"] = "Server restarted; attempt interrupted"
                self.save(run)

    def close(self):
        self.db.close()
