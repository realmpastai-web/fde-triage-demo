"""Plain dataclasses shared across the pipeline. No framework types in the core."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class ActionKind(StrEnum):
    READ = "read"  # looks something up, no side effects -> auto
    INTERNAL_WRITE = "internal_write"  # changes our own systems (assign, note) -> auto, audited
    OUTBOUND = "outbound"  # touches the customer or their money -> human approval


@dataclass
class RawTicket:
    source: str
    source_id: str
    created_at: str
    customer_email: str | None
    channel: str
    subject: str
    body: str
    customer_phone: str | None = None
    first_response_minutes: float | None = None


@dataclass
class Ticket:
    id: str
    source: str
    source_ids: list[str]
    created_at: str | None
    channel: str
    customer_ref: str | None  # salted hash, never the email
    subject: str  # redacted
    body: str  # redacted
    language: str
    urgency: str  # low | medium | high
    urgency_signals: list[str] = field(default_factory=list)
    pii_redacted: dict[str, int] = field(default_factory=dict)
    first_response_minutes: float | None = None

    @property
    def text(self) -> str:
        return f"{self.subject}\n{self.body}".strip()


@dataclass
class Classification:
    category: str
    team: str
    priority: str
    confidence: float
    rationale: str
    provider: str
    needs_human_triage: bool = False
    cost_usd: float = 0.0


@dataclass
class Citation:
    n: int
    doc_id: str
    title: str
    section: str
    url: str
    score: float


@dataclass
class Draft:
    text: str
    citations: list[Citation]
    provider: str
    policy_violations: list[str] = field(default_factory=list)
    cost_usd: float = 0.0

    @property
    def blocked(self) -> bool:
        return bool(self.policy_violations)


@dataclass
class ProposedAction:
    name: str
    kind: ActionKind
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def requires_approval(self) -> bool:
        return self.kind is ActionKind.OUTBOUND


@dataclass
class TriageResult:
    ticket: Ticket
    classification: Classification
    draft: Draft
    actions: list[ProposedAction]
    latency_ms: float

    @property
    def cost_usd(self) -> float:
        return self.classification.cost_usd + self.draft.cost_usd

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["cost_usd"] = self.cost_usd
        for a in d["actions"]:
            a["kind"] = a["kind"].value if isinstance(a["kind"], ActionKind) else a["kind"]
        return d
