"""The fraud/takeover P1 rule (routing-policy.md, "Fraud and account-takeover escalation").

Wording here is deliberately different from golden, holdout_v1 and holdout_v2, so these test the
signal families, not memorised sentences. Near misses must stay below P1: the safety bias is
a tie-breaker, not a licence to page Fraud & Risk for every mention of a payment.
"""

import json

import httpx
import pytest

from triage.classify import LLMClassifier, assign_priority
from triage.escalation import fraud_escalation
from triage.ingest import normalize
from triage.models import RawTicket
from triage.pipeline import Pipeline


@pytest.mark.parametrize(
    ("text", "condition"),
    [
        # (1) money moved without consent
        ("Someone spent 320 on my card at an electronics store. I never authorised it.", "money moved without consent"),
        ("There are four transactions from a casino site I've never used.", "money moved without consent"),
        (
            "My card was used at a petrol station 200 miles away while it was in my wallet",
            "money moved without consent",
        ),
        ("A transfer of 900 went out of my account without my permission last night", "money moved without consent"),
        ("I don't recognise these card payments to an airline, please help", "money moved without consent"),
        ("Hay dos pagos que no reconozco en mi cuenta", "money moved without consent"),
        # (2) someone else in control
        ("I think my account has been taken over, my balance is zero", "third party in account"),
        ("My email address was changed this morning and it wasn't me", "account details changed by someone else"),
        (
            "I'm locked out and got a warning about a login from an unknown device",
            "locked out with signs of a third party",
        ),
        # (3) credentials handed over
        ("I shared my one-time passcode with a woman who said she was from delivery", "credentials shared"),
        ("I typed my card details into a site from a text message link", "credentials shared"),
        # (4) impersonation scam in progress
        ("Someone phoned claiming to be from the fraud team and wants me to transfer my balance", "impersonation scam"),
        ("A caller from 'the bank' told me to move everything to a safe account, what do I do?", "impersonation scam"),
    ],
)
def test_p1_conditions_fire(text: str, condition: str) -> None:
    esc = fraud_escalation(text)
    assert esc is not None, text
    assert esc.condition.startswith(condition)


@pytest.mark.parametrize(
    "text",
    [
        # payment the customer suggests may be their own
        "I don't recognise a 9.99 charge, could be my music app under a different name?",
        # phishing attempt the customer shut down
        "Someone rang pretending to be Kestrel asking for my code. I hung up and didn't give them anything.",
        "Had an email claiming to be from you asking me to move money. I deleted it and didn't reply.",
        # new-login alert the customer says was them
        "I got an alert about a new device signed in, but that was me on my tablet.",
        # lost card with nothing disputed
        "I lost my card at the gym, no payments I don't know about yet. Please block it.",
        # merchant disputes the customer authorised (policy: P3)
        "The shop charged me twice for one order and I want my money back",
        "Paid for concert tickets that were never delivered, the seller won't answer",
        "Returned my shoes three weeks ago and still haven't been refunded",
        # fee / plan disputes (policy: P4 or billing)
        "You charged me a fee I never agreed to on my plan",
        # an attempt that was declined: no money moved
        "Someone tried to use my card online but the payment was declined",
        # locked out with no third-party sign
        "Locked out after too many wrong passwords, I need someone to help me get back in",
        # balance discrepancy, no third party
        "My balance looks lower than I expected, can you explain?",
        # the customer's own action, no fraud
        "I sent 50 to the wrong friend, can I get it back?",
        "The app didn't send my transfer and now the money is pending",
    ],
)
def test_near_misses_do_not_fire(text: str) -> None:
    assert fraud_escalation(text) is None, fraud_escalation(text)


@pytest.mark.parametrize(
    ("text", "category", "priority"),
    [
        ("I lost my card at the gym, no payments I don't know about yet. Please block it.", "card_issue", "P2"),
        ("The shop charged me twice for one order and I want my money back", "fraud_dispute", "P3"),
        ("I don't recognise a 9.99 charge, could be my music app under a different name?", "fraud_dispute", "P2"),
    ],
)
def test_near_misses_keep_policy_priority(text: str, category: str, priority: str) -> None:
    assert assign_priority(category, text, "low")[0] == priority


def test_rule_applies_whatever_the_category() -> None:
    p, why = assign_priority("card_issue", "My card was used in three shops I've never been to", "low")
    assert p == "P1" and "fraud/takeover rule" in why


def test_p1_fraud_routes_to_fraud_team_and_skips_human_queue(pipeline: Pipeline) -> None:
    raw = RawTicket(
        "t", "x", "", None, "email", "help", "Someone logged into my account from abroad and I can't sign in"
    )
    c = pipeline.classifier.classify(normalize(raw))
    assert (c.category, c.team, c.priority) == ("fraud_dispute", "Fraud & Risk", "P1")
    assert not c.needs_human_triage


def test_llm_under_ranking_is_raised_by_the_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    content = json.dumps({"category": "card_issue", "priority": "P3", "confidence": 0.9, "rationale": "card"})
    resp = httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
        request=httpx.Request("POST", "https://api.openai.com"),
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp)
    raw = RawTicket("t", "x", "", None, "email", "card", "Two payments I didn't make showed up on my card today")
    c = LLMClassifier("openai").classify(normalize(raw))
    assert c.provider == "llm:openai" and (c.category, c.priority) == ("fraud_dispute", "P1")
    assert "raised by" in c.rationale
