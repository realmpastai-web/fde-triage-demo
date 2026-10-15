"""Reply policy checks (data/policies/reply-policy.md) and action classification.

Two separate gates:
- `check_draft` blocks drafts that break the client's reply policy. Blocked drafts still
  reach the queue, marked, so a human sees why.
- `propose_actions` turns a triage result into concrete actions, each tagged read /
  internal_write / outbound. Only outbound actions need approval; the rest run and are audited.
"""

from __future__ import annotations

import re

from .draft import INTERNAL_TERMS
from .models import ActionKind, Classification, Draft, ProposedAction, Ticket
from .pii import find_leaks, redact

FORBIDDEN_ASKS = re.compile(
    r"\b(?:send|share|tell|give|provide|reply with|confirm)\b[^.]{0,40}\b(?:full card number|card number|cvv|cvc|"
    r"security code|pin|password|one-time code|otp|verification code)\b",
    re.I,
)
REFUND_PROMISE = re.compile(
    r"\bwe (?:will|'ll)\s+(?:refund|reverse|reimburse|credit)\b|\byou will (?:get|receive) a refund\b", re.I
)
MOVE_MONEY = re.compile(
    r"\b(?:move|transfer)\b[^.]{0,30}\bto (?:a |another |this )?(?:safe|new|different) account\b", re.I
)
MAX_WORDS = 180
CLIENT_DOMAINS = ("@kestrel.example",)  # the client's own public addresses are not customer PII


def customer_text(draft_text: str) -> str:
    """The part the customer reads: drop the translation note and the sources block."""
    t = re.sub(r"^\[Customer wrote in .*?\]\s*", "", draft_text)
    return t.split("\nSources:")[0]


def check_draft(draft: Draft) -> list[str]:
    text = customer_text(draft.text)
    v: list[str] = []
    # The extractive drafter quotes "Kestrel will never ask for your PIN..." -- a statement, not an ask.
    for m in FORBIDDEN_ASKS.finditer(text):
        window = text[max(0, m.start() - 30) : m.end()].lower()
        if "never" not in window and "don't" not in window and "do not" not in window:
            v.append(f"asks for a secret: '{m.group(0)}'")
    if REFUND_PROMISE.search(text):
        v.append("promises a refund before review")
    if MOVE_MONEY.search(text) and "never" not in text[: text.lower().find("account") + 1].lower():
        v.append("tells customer to move money")
    if not draft.citations or not re.search(r"\[\d\]", text):
        v.append("no citation")
    if len(text.split()) > MAX_WORDS:
        v.append(f"over {MAX_WORDS} words")
    for term in INTERNAL_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", text):
            v.append(f"internal term in customer text: '{term}'")
    if [f for f in redact(text).findings if not f.value.lower().endswith(CLIENT_DOMAINS)]:
        v.append("contains PII")
    return v


def pii_leaks(original_text: str, outputs: list[str]) -> int:
    """Count raw PII values from the original ticket that appear in any output."""
    findings = redact(original_text).findings
    return sum(len(find_leaks(findings, o)) for o in outputs)


def propose_actions(ticket: Ticket, cls: Classification, draft: Draft) -> list[ProposedAction]:
    acts = [
        ProposedAction("lookup_customer", ActionKind.READ, {"customer_ref": ticket.customer_ref}),
        ProposedAction("assign_team", ActionKind.INTERNAL_WRITE, {"team": cls.team, "priority": cls.priority}),
        ProposedAction("add_internal_note", ActionKind.INTERNAL_WRITE, {"note": cls.rationale}),
    ]
    if cls.priority == "P1":
        acts.append(ProposedAction("page_on_call", ActionKind.INTERNAL_WRITE, {"team": cls.team}))
    text = ticket.text.lower()
    if cls.category in ("card_issue", "fraud_dispute") and re.search(
        r"lost|stolen|can't find|didn't make|never made|not mine|aren't mine|robaron|perdí|kho gaya|hacked", text
    ):
        acts.append(ProposedAction("freeze_card", ActionKind.OUTBOUND, {"customer_ref": ticket.customer_ref}))
    if not draft.blocked:
        acts.append(ProposedAction("send_reply", ActionKind.OUTBOUND, {"channel": ticket.channel}))
    return acts
