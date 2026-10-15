"""Append-only, hash-chained audit log (JSONL).

Every decision (triage, auto-executed action, approval, rejection, send) is one line.
Each line carries the SHA-256 of the previous line, so editing or deleting history breaks
`verify()`. That is tamper-evident, not tamper-proof: for the real thing, ship the file to
WORM storage or the client's SIEM as well.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

GENESIS = "0" * 64
_lock = threading.Lock()


def _hash(line: str) -> str:
    return hashlib.sha256(line.encode()).hexdigest()


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

    def _last_hash(self) -> str:
        last = ""
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line.rstrip("\n")
        return _hash(last) if last else GENESIS

    def append(self, event: str, actor: str, ticket_id: str | None = None, **data: Any) -> dict[str, Any]:
        with _lock:
            entry = {
                "ts": round(time.time(), 3),
                "event": event,
                "actor": actor,
                "ticket_id": ticket_id,
                "data": data,
                "prev": self._last_hash(),
            }
            line = json.dumps(entry, sort_keys=True, ensure_ascii=False)
            with self.path.open("a", encoding="utf-8") as fh:  # append mode only, never rewrite
                fh.write(line + "\n")
            return entry

    def read(self, ticket_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        with self.path.open(encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        if ticket_id:
            rows = [r for r in rows if r.get("ticket_id") == ticket_id]
        return rows[-limit:] if limit else rows

    def verify(self) -> tuple[bool, int, str]:
        """Returns (ok, entries_checked, message)."""
        prev = GENESIS
        n = 0
        with self.path.open(encoding="utf-8") as fh:
            for n, line in enumerate((ln.rstrip("\n") for ln in fh if ln.strip()), 1):
                entry = json.loads(line)
                if entry.get("prev") != prev:
                    return False, n, f"chain broken at entry {n}"
                prev = _hash(line)
        return True, n, "ok"
