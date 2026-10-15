"""Durable invocation lifecycle and per-invocation tool call counters."""
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

class InvocationStore:
    def __init__(self, path=None):
        self.path = path or os.environ.get("DELEGATEGUARD_STATE", "delegateguard-state.sqlite3")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS closed_invocations (invocation_id TEXT PRIMARY KEY, closed_at REAL NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS tool_call_counts (invocation_id TEXT NOT NULL, tool TEXT NOT NULL, calls INTEGER NOT NULL, PRIMARY KEY(invocation_id, tool))")

    def close(self, invocation_id):
        if not isinstance(invocation_id, str) or not invocation_id:
            raise ValueError("invalid invocation id")
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("INSERT OR IGNORE INTO closed_invocations VALUES (?, ?)", (invocation_id, time.time()))

    def is_closed(self, invocation_id):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT 1 FROM closed_invocations WHERE invocation_id=?", (invocation_id,)).fetchone() is not None

    def reserve_call(self, info, invocation_id, tool):
        limits = [c[tool]["max_calls"] for c in info["constraints"] if tool in c and "max_calls" in c[tool]]
        if not limits:
            return True
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT calls FROM tool_call_counts WHERE invocation_id=? AND tool=?", (invocation_id, tool)).fetchone()
            if row and row[0] >= min(limits):
                db.rollback()
                return False
            db.execute("INSERT INTO tool_call_counts VALUES (?, ?, 1) ON CONFLICT(invocation_id, tool) DO UPDATE SET calls=calls+1", (invocation_id, tool))
            db.commit()
        return True
