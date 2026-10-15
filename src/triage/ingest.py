"""Ingest and normalise the client's exports.

Two sources with different schemas (helpdesk CSV, chat-widget JSON) become one list of
redacted, de-duplicated `Ticket`s. The order matters: clean -> redact -> detect -> dedupe,
so nothing after `normalize()` ever holds raw PII.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .detect import detect_language, detect_urgency
from .models import RawTicket, Ticket
from .pii import redact

CUSTOMER_SALT = "kestrel-demo-salt"  # per-client secret in a real deployment
CHANNELS = {
    "email": "email",
    "web_form": "web",
    "web form": "web",
    "web": "web",
    "app": "in_app",
    "in-app": "in_app",
    "in_app": "in_app",
    "chat": "chat",
}
DATE_FORMATS = ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%m-%d-%Y %I:%M %p", "%d/%m/%Y %H:%M"]
_QUOTE_START = re.compile(r"^\s*On .{0,120}wrote:\s*$", re.MULTILINE)
_SIGNOFF = re.compile(r"\n\s*(?:Sent from my \w+|--|Thanks,|Regards,?|Best,|Cheers,)\s*(?:\n.*)?$", re.DOTALL | re.I)
_TAG = re.compile(r"<[^>]+>")


def load_csv(path: Path) -> list[RawTicket]:
    out: list[RawTicket] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            frt = row.get("First Response (min)") or ""
            out.append(
                RawTicket(
                    source="helpdesk_csv",
                    source_id=row.get("Ticket ID", "").strip(),
                    created_at=row.get("Created", "").strip(),
                    customer_email=(row.get("Customer Email") or "").strip() or None,
                    channel=row.get("Channel", ""),
                    subject=row.get("Subject", ""),
                    body=row.get("Description", ""),
                    first_response_minutes=float(frt) if frt.strip() else None,
                )
            )
    return out


def load_chat_json(path: Path) -> list[RawTicket]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    out: list[RawTicket] = []
    for conv in data.get("conversations", []):
        customer_msgs = [m["text"] for m in conv.get("messages", []) if m.get("from") == "customer"]
        if not customer_msgs:
            continue
        user = conv.get("user") or {}
        frs = conv.get("first_response_seconds")
        out.append(
            RawTicket(
                source="chat_json",
                source_id=str(conv.get("conversation_id")),
                created_at=str(conv.get("started_at", "")),
                customer_email=user.get("email"),
                customer_phone=user.get("phone"),
                channel="chat",
                subject=customer_msgs[0] if len(customer_msgs) > 1 else "",
                body="\n".join(customer_msgs[1:] if len(customer_msgs) > 1 else customer_msgs),
                first_response_minutes=frs / 60 if isinstance(frs, (int, float)) else None,
            )
        )
    return out


def parse_date(value: str) -> datetime | None:
    v = value.strip()
    if not v:
        return None
    if v.isdigit():
        return datetime.fromtimestamp(int(v), tz=UTC)
    v = v.replace("Z", "+00:00")
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(v, fmt)
        except ValueError:
            continue
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # export is documented as UTC
    return None


def clean_text(text: str) -> str:
    t = html.unescape(_TAG.sub(" ", text))
    m = _QUOTE_START.search(t)
    if m:
        t = t[: m.start()]
    t = "\n".join(line for line in t.splitlines() if not line.lstrip().startswith(">"))
    t = _SIGNOFF.sub("", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def iso_utc(dt: datetime) -> str:
    """Explicit ISO-8601 UTC formatting (stable across environments)."""
    u = dt.astimezone(UTC)
    return "%04d-%02d-%02dT%02d:%02d:%02d+00:00" % (u.year, u.month, u.day, u.hour, u.minute, u.second)


def customer_ref(email: str | None) -> str | None:
    if not email:
        return None
    return "cus_" + hashlib.sha256((CUSTOMER_SALT + email.strip().lower()).encode()).hexdigest()[:12]


def normalize(raw: RawTicket) -> Ticket:
    subject = redact(clean_text(raw.subject))
    body = redact(clean_text(raw.body))
    text = f"{subject.text}\n{body.text}"
    urgency = detect_urgency(text)
    counts: dict[str, int] = {}
    for r in (subject, body):
        for k, v in r.counts.items():
            counts[k] = counts.get(k, 0) + v
    dt = parse_date(raw.created_at)
    return Ticket(
        id=f"T-{hashlib.sha1(f'{raw.source}:{raw.source_id}'.encode()).hexdigest()[:8]}",
        source=raw.source,
        source_ids=[raw.source_id],
        created_at=iso_utc(dt) if dt else None,
        channel=CHANNELS.get(raw.channel.strip().lower(), "other"),
        customer_ref=customer_ref(raw.customer_email),
        subject=subject.text,
        body=body.text,
        language=detect_language(text),
        urgency=urgency.level,
        urgency_signals=urgency.signals,
        pii_redacted=counts,
        first_response_minutes=raw.first_response_minutes,
    )


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower())) - {"please", "reply"}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


@dataclass
class IngestReport:
    tickets: list[Ticket]
    raw_count: int
    duplicates_merged: int
    undated: int
    pii_redacted: dict[str, int] = field(default_factory=dict)
    languages: dict[str, int] = field(default_factory=dict)
    channels: dict[str, int] = field(default_factory=dict)


def dedupe(
    tickets: list[Ticket], threshold: float = 0.85, window: timedelta = timedelta(days=3)
) -> tuple[list[Ticket], int]:
    """Merge near-identical tickets from the same customer inside a time window.

    The kept ticket records every source id, so nothing is silently dropped.
    """
    kept: list[tuple[Ticket, set[str], datetime | None]] = []
    merged = 0
    for t in sorted(tickets, key=lambda x: x.created_at or ""):
        toks = _tokens(t.text)
        dt = datetime.fromisoformat(t.created_at) if t.created_at else None
        for k, ktoks, kdt in kept:
            same_customer = k.customer_ref is not None and k.customer_ref == t.customer_ref
            close = dt is None or kdt is None or abs(dt - kdt) <= window
            if same_customer and close and jaccard(toks, ktoks) >= threshold:
                k.source_ids.extend(t.source_ids)
                merged += 1
                break
        else:
            kept.append((t, toks, dt))
    return [k for k, _, _ in kept], merged


def ingest(raw: list[RawTicket]) -> IngestReport:
    normalized = [normalize(r) for r in raw]
    tickets, merged = dedupe(normalized)
    report = IngestReport(
        tickets=tickets,
        raw_count=len(raw),
        duplicates_merged=merged,
        undated=sum(1 for t in tickets if t.created_at is None),
    )
    for t in normalized:
        for k, v in t.pii_redacted.items():
            report.pii_redacted[k] = report.pii_redacted.get(k, 0) + v
    for t in tickets:
        report.languages[t.language] = report.languages.get(t.language, 0) + 1
        report.channels[t.channel] = report.channels.get(t.channel, 0) + 1
    return report


def load_raw_dir(raw_dir: Path) -> list[RawTicket]:
    raw: list[RawTicket] = []
    for p in sorted(raw_dir.glob("*.csv")):
        raw.extend(load_csv(p))
    for p in sorted(raw_dir.glob("*.json")):
        raw.extend(load_chat_json(p))
    return raw
