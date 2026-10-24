"""Local snapshots and a persistent, atomic application-wide charged-request counter."""
import json
import sqlite3
from pathlib import Path
from .billing import summarize, run_billing, reported


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY, used INTEGER)")
        self.db.execute("INSERT OR IGNORE INTO budget VALUES (1,0)")
        self.db.execute("CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY, model TEXT, body TEXT)")
        self.db.commit()

    def consume(self, ceiling):
        with self.db:
            cur = self.db.execute("UPDATE budget SET used=used+1 WHERE id=1 AND used < ?", (ceiling,))
        return cur.rowcount == 1

    def used(self):
        return self.db.execute("SELECT used FROM budget WHERE id=1").fetchone()[0]

    def reserve(self, ceiling, model, run_id=None, race_index=None, retry=0):
        # Count and journal before sending: a crash leaves unknown cost, never a free request.
        with self.db:
            cur = self.db.execute("UPDATE budget SET used=used+1 WHERE id=1 AND used < ?", (ceiling,))
            if not cur.rowcount:
                return None
            return self.db.execute("INSERT INTO requests(model,body) VALUES (?,?)",
                                   (model, json.dumps({"usage": None, "outcome": "PENDING",
                                                       "run_id": run_id, "race_index": race_index,
                                                       "requested_model_id": model, "retry": retry,
                                                       "latency_ms": None, "http_status": None,
                                                       "billing": reported(None)}))).lastrowid

    def record_request(self, request_id, record):
        with self.db:
            self.db.execute("UPDATE requests SET body=? WHERE id=?",
                            (json.dumps(record, allow_nan=False), request_id))

    def billing(self):
        entries = [(model, json.loads(body)) for model, body in self.db.execute("SELECT model,body FROM requests")]
        # Old installations may have paid attempts without a ledger. Their costs stay unknown.
        missing = max(0, self.used() - len(entries))
        return {**summarize((q for _, q in entries), missing),
                "legacy_unattributed_requests": missing,
                "by_model": {model: summarize(q for m, q in entries if m == model)
                             for model in sorted({m for m, _ in entries})}}

    def run_billing(self, run):
        entries = [(m, json.loads(b)) for m, b in self.db.execute("SELECT model,body FROM requests")]
        entries = [(m, q) for m, q in entries if q.get("run_id") == run["id"]]
        if not entries:
            return run_billing(run)
        models = {t["model_id"] for race in run["races"] for t in race["trials"]}
        return {**summarize(q for _, q in entries),
                "by_model": {m: summarize(q for model, q in entries if model == m) for m in models}}

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
                journal = [(key, m, json.loads(b)) for key, m, b in
                           self.db.execute("SELECT id,model,body FROM requests")]
                if "budget" in run:
                    run["budget"]["used"] = max(run["budget"]["used"], sum(
                        q.get("run_id") == run["id"] for _, _, q in journal))
                for index, race in enumerate(run["races"]):
                    for trial in race["trials"]:
                        recovered = [{**q, "ledger_id": key} for key, model, q in journal
                                     if q.get("run_id") == run["id"] and q.get("race_index") == index
                                     and model == trial.get("model_id")]
                        if recovered:
                            by_id = {q.get("ledger_id"): q for q in trial.get("requests", [])}
                            by_id.update({q["ledger_id"]: q for q in recovered})
                            trial["requests"] = list(by_id.values())
                            trial["billing"] = summarize(trial["requests"])
                        if trial["status"] == "RUNNING" or (trial["status"] == "PENDING" and recovered):
                            trial["status"] = "ABORTED"
                            trial["error"] = "Server restarted; attempt interrupted"
                        elif trial["status"] == "PENDING":
                            trial["status"] = "NOT_RUN"
                self.save(run)

    def close(self):
        self.db.close()
