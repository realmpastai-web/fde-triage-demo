"""FastAPI service: queue, approvals, metrics, audit, and a one-page dashboard.

No auth in the demo. In a client deployment this sits behind their SSO proxy and the
reviewer name comes from the identity header, not the request body.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .ingest import normalize
from .models import RawTicket
from .pipeline import Service

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Kestrel support triage", version="0.1.0")
_svc: Service | None = None


def svc() -> Service:
    global _svc
    if _svc is None:
        _svc = Service.create()
        if not _svc.queue.counts():  # first boot: load the client export so the demo isn't empty
            _svc.run_ingest()
    return _svc


class NewTicket(BaseModel):
    subject: str = ""
    body: str = Field(min_length=1)
    customer_email: str | None = None
    channel: str = "web"


class Decision(BaseModel):
    reviewer: str = Field(min_length=1)
    reason: str | None = None
    edited_reply: str | None = None


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return (STATIC / "dashboard.html").read_text(encoding="utf-8")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "classifier": svc().pipeline.classifier.name, "drafter": svc().pipeline.drafter.name}


@app.get("/api/queue")
def queue(status: str | None = "pending_approval", limit: int = 200) -> list[dict[str, Any]]:
    rows = svc().queue.list(status=status or None, limit=limit)
    return [
        {
            "ticket_id": r["ticket_id"],
            "status": r["status"],
            "priority": r["priority"],
            "team": r["team"],
            "category": r["category"],
            "created_at": r["created_at"],
            "subject": r["result"]["ticket"]["subject"],
            "language": r["result"]["ticket"]["language"],
            "confidence": r["result"]["classification"]["confidence"],
            "needs_human_triage": r["result"]["classification"]["needs_human_triage"],
            "blocked": bool(r["result"]["draft"]["policy_violations"]),
        }
        for r in rows
    ]


@app.get("/api/tickets/{ticket_id}")
def ticket(ticket_id: str) -> dict[str, Any]:
    row = svc().queue.get(ticket_id)
    if not row:
        raise HTTPException(404, "not found")
    row["audit"] = svc().audit.read(ticket_id=ticket_id)
    return row


@app.post("/api/tickets")
def create_ticket(t: NewTicket) -> dict[str, Any]:
    raw = RawTicket("api", uuid.uuid4().hex[:10], "", t.customer_email, t.channel, t.subject, t.body)
    r = svc().process(normalize(raw), actor="api")
    return r.to_dict()


@app.post("/api/tickets/{ticket_id}/approve")
def approve(ticket_id: str, d: Decision) -> dict[str, Any]:
    try:
        return svc().approve(ticket_id, d.reviewer, d.edited_reply)
    except KeyError as e:
        raise HTTPException(404, "not found") from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/api/tickets/{ticket_id}/reject")
def reject(ticket_id: str, d: Decision) -> dict[str, Any]:
    try:
        return svc().reject(ticket_id, d.reviewer, d.reason or "no reason given")
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/api/metrics")
def metrics() -> dict[str, Any]:
    s = svc()
    rows = s.queue.list(status=None, limit=10_000)
    by_p: dict[str, int] = {}
    by_team: dict[str, int] = {}
    lat: list[float] = []
    for r in rows:
        if r["status"] == "pending_approval":
            by_p[r["priority"]] = by_p.get(r["priority"], 0) + 1
            by_team[r["team"]] = by_team.get(r["team"], 0) + 1
        lat.append(r["result"]["latency_ms"])
    lat.sort()
    return {
        "status_counts": s.queue.counts(),
        "pending_by_priority": dict(sorted(by_p.items())),
        "pending_by_team": dict(sorted(by_team.items(), key=lambda kv: -kv[1])),
        "triage_latency_ms_p50": lat[len(lat) // 2] if lat else None,
        "flagged_for_human": sum(1 for r in rows if r["result"]["classification"]["needs_human_triage"]),
        "audit_entries": len(s.audit.read()),
        "audit_chain_ok": s.audit.verify()[0],
        "classifier": s.pipeline.classifier.name,
    }


@app.get("/api/audit")
def audit(limit: int = 50, ticket_id: str | None = None) -> list[dict[str, Any]]:
    return list(reversed(svc().audit.read(ticket_id=ticket_id, limit=limit)))
