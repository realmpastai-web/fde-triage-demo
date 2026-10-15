"""Wires the stages together. `Pipeline.triage()` is pure (no side effects); `run()` adds
the queue, the audit log and auto-execution of non-outbound actions."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .audit import AuditLog
from .classify import Classifier, get_classifier
from .config import Settings, load_settings
from .draft import Drafter, get_drafter, retrieve_for
from .ingest import IngestReport, ingest, load_raw_dir
from .models import ActionKind, Draft, Ticket, TriageResult
from .policy import check_draft, propose_actions
from .retrieval import Retriever
from .store import Queue


@dataclass
class Pipeline:
    retriever: Retriever
    classifier: Classifier
    drafter: Drafter

    @classmethod
    def build(cls, settings: Settings | None = None) -> Pipeline:
        s = settings or load_settings()
        retriever = Retriever.from_dir(s.docs_dir)
        return cls(retriever, get_classifier(s.llm_mode, retriever), get_drafter(s.llm_mode))

    def triage(self, ticket: Ticket) -> TriageResult:
        t0 = time.perf_counter()
        cls = self.classifier.classify(ticket)
        hits = retrieve_for(self.retriever, ticket, cls)
        draft = self.drafter.draft(ticket, cls, hits)
        draft.policy_violations = check_draft(draft)
        actions = propose_actions(ticket, cls, draft)
        return TriageResult(ticket, cls, draft, actions, latency_ms=(time.perf_counter() - t0) * 1000)


@dataclass
class Service:
    """The stateful app: pipeline + queue + audit. Used by both CLI and API."""

    settings: Settings
    pipeline: Pipeline
    queue: Queue
    audit: AuditLog
    outbox: Path = field(init=False)

    def __post_init__(self) -> None:
        self.outbox = self.settings.data_dir / "outbox.jsonl"

    @classmethod
    def create(cls, settings: Settings | None = None) -> Service:
        s = settings or load_settings()
        s.data_dir.mkdir(parents=True, exist_ok=True)
        return cls(s, Pipeline.build(s), Queue(s.db_path), AuditLog(s.audit_path))

    def process(self, ticket: Ticket, actor: str = "system:pipeline") -> TriageResult:
        r = self.pipeline.triage(ticket)
        c = r.classification
        self.audit.append(
            "triaged",
            actor,
            ticket.id,
            category=c.category,
            team=c.team,
            priority=c.priority,
            confidence=c.confidence,
            provider=c.provider,
            needs_human_triage=c.needs_human_triage,
            draft_provider=r.draft.provider,
            policy_violations=r.draft.policy_violations,
            citations=[x.doc_id for x in r.draft.citations],
            latency_ms=round(r.latency_ms, 2),
            pii_redacted=ticket.pii_redacted,
        )
        for a in r.actions:
            if a.kind is not ActionKind.OUTBOUND:
                self.audit.append(
                    "action_executed", actor, ticket.id, action=a.name, kind=a.kind.value, params=a.params
                )
            else:
                self.audit.append(
                    "action_proposed", actor, ticket.id, action=a.name, kind=a.kind.value, params=a.params
                )
        status = self.queue.put(r)
        self.audit.append("queued", actor, ticket.id, status=status)
        return r

    def run_ingest(self) -> IngestReport:
        report = ingest(load_raw_dir(self.settings.raw_dir))
        self.audit.append(
            "ingested",
            "system:ingest",
            None,
            raw=report.raw_count,
            tickets=len(report.tickets),
            duplicates_merged=report.duplicates_merged,
            pii_redacted=report.pii_redacted,
        )
        for t in report.tickets:
            self.process(t)
        return report

    def approve(self, ticket_id: str, reviewer: str, edited_reply: str | None = None) -> dict[str, Any]:
        row = self.queue.get(ticket_id)
        if not row:
            raise KeyError(ticket_id)
        result = row["result"]
        reply = edited_reply if edited_reply is not None else result["draft"]["text"]
        if edited_reply is not None:
            violations = check_draft(Draft(text=edited_reply, citations=[], provider="human"))
            violations = [v for v in violations if v != "no citation"]  # humans may drop citations
            if violations:
                self.audit.append("approval_blocked", f"human:{reviewer}", ticket_id, violations=violations)
                raise ValueError(f"edited reply violates policy: {violations}")
        self.queue.decide(ticket_id, "approved", f"human:{reviewer}", reply)
        self.audit.append("approved", f"human:{reviewer}", ticket_id, edited=edited_reply is not None)
        sent = []
        for a in result["actions"]:
            if a["kind"] == ActionKind.OUTBOUND.value:
                # Integration point: in production this calls the helpdesk / card-processor API.
                with self.outbox.open("a", encoding="utf-8") as fh:
                    fh.write(
                        json.dumps(
                            {
                                "ticket_id": ticket_id,
                                "action": a["name"],
                                "params": a["params"],
                                "reply": reply if a["name"] == "send_reply" else None,
                            }
                        )
                        + "\n"
                    )
                self.audit.append("action_executed", f"human:{reviewer}", ticket_id, action=a["name"], kind=a["kind"])
                sent.append(a["name"])
        return {"ticket_id": ticket_id, "status": "approved", "executed": sent}

    def reject(self, ticket_id: str, reviewer: str, reason: str) -> dict[str, Any]:
        self.queue.decide(ticket_id, "rejected", f"human:{reviewer}")
        self.audit.append("rejected", f"human:{reviewer}", ticket_id, reason=reason)
        return {"ticket_id": ticket_id, "status": "rejected"}

    def reset(self) -> None:
        """Demo only: clear queue and start a fresh audit file (old one is kept, renamed)."""
        self.queue.clear()
        if self.settings.audit_path.exists() and self.settings.audit_path.stat().st_size:
            self.settings.audit_path.rename(self.settings.audit_path.with_suffix(f".{int(time.time())}.jsonl"))
        self.audit = AuditLog(self.settings.audit_path)
        if self.outbox.exists():
            self.outbox.unlink()
