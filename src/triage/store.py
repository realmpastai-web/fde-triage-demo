"""SQLite-backed approval queue. One row per ticket; the full triage result is stored as
JSON so the queue schema doesn't churn while the pipeline evolves."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import TriageResult

# pending_approval -> approved | rejected ; auto_closed for tickets with no outbound action
STATUSES = ("pending_approval", "approved", "rejected", "auto_closed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
  ticket_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  team TEXT NOT NULL,
  category TEXT NOT NULL,
  created_at TEXT,
  queued_at REAL NOT NULL,
  decided_at REAL,
  decided_by TEXT,
  result_json TEXT NOT NULL,
  final_reply TEXT
);
CREATE INDEX IF NOT EXISTS queue_status ON queue(status, priority);
"""


class Queue:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def put(self, result: TriageResult) -> str:
        needs = any(a.requires_approval for a in result.actions)
        status = "pending_approval" if needs else "auto_closed"
        c_ = result.classification
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO queue"
                " (ticket_id, status, priority, team, category, created_at, queued_at, result_json)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    result.ticket.id,
                    status,
                    c_.priority,
                    c_.team,
                    c_.category,
                    result.ticket.created_at,
                    time.time(),
                    json.dumps(result.to_dict(), ensure_ascii=False),
                ),
            )
        return status

    def get(self, ticket_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM queue WHERE ticket_id=?", (ticket_id,)).fetchone()
        return self._row(row) if row else None

    def list(self, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        q = "SELECT * FROM queue" + (" WHERE status=?" if status else "") + " ORDER BY priority, created_at LIMIT ?"
        args: tuple[Any, ...] = (status, limit) if status else (limit,)
        with self._conn() as c:
            return [self._row(r) for r in c.execute(q, args).fetchall()]

    def decide(self, ticket_id: str, status: str, actor: str, final_reply: str | None = None) -> None:
        with self._conn() as c:
            cur = c.execute(
                "UPDATE queue SET status=?, decided_at=?, decided_by=?, final_reply=? "
                "WHERE ticket_id=? AND status='pending_approval'",
                (status, time.time(), actor, final_reply, ticket_id),
            )
            if cur.rowcount != 1:
                raise ValueError(f"{ticket_id} is not pending approval")

    def counts(self) -> dict[str, int]:
        with self._conn() as c:
            return {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) n FROM queue GROUP BY status")}

    def clear(self) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM queue")

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["result"] = json.loads(d.pop("result_json"))
        return d
