import json

import httpx
import pytest

from triage.classify import HeuristicClassifier, LLMClassifier, get_classifier
from triage.ingest import normalize
from triage.models import RawTicket
from triage.pipeline import Pipeline


def _t(subject: str, body: str) -> RawTicket:
    return RawTicket("t", subject, "", None, "email", subject, body)


@pytest.mark.parametrize(
    ("subject", "body", "category", "priority"),
    [
        ("Lost card", "I lost my card on the train, please block it", "card_issue", "P2"),
        ("Hacked", "Someone logged into my account and sent money out", "fraud_dispute", "P1"),
        ("Rent", "My rent transfer has been pending for 3 days, landlord is angry", "payments_transfer", "P2"),
        ("Pots", "What interest do savings pots pay?", "general_inquiry", "P4"),
        ("Crash", "The app crashes when I open statements", "technical_bug", "P3"),
    ],
)
def test_heuristic_routes_clear_cases(
    pipeline: Pipeline, subject: str, body: str, category: str, priority: str
) -> None:
    c = pipeline.classifier.classify(normalize(_t(subject, body)))
    assert (c.category, c.priority) == (category, priority)
    assert not c.needs_human_triage


def test_unclear_ticket_goes_to_human_triage(pipeline: Pipeline) -> None:
    c = pipeline.classifier.classify(normalize(_t("hello", "hi, quick one")))
    assert c.needs_human_triage and c.team == "Tier-1 Support"


def test_auto_mode_without_keys_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_classifier("auto"), HeuristicClassifier)


def test_llm_failure_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    def boom(*a: object, **k: object) -> None:
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "post", boom)
    c = LLMClassifier("openai").classify(normalize(_t("Lost card", "I lost my card, block it")))
    assert c.category == "card_issue" and "fallback" in c.rationale


def test_llm_out_of_schema_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    content = json.dumps({"category": "refund_please", "priority": "P0"})
    resp = httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
        request=httpx.Request("POST", "https://api.openai.com"),
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp)
    c = LLMClassifier("openai").classify(normalize(_t("Lost card", "I lost my card, block it")))
    assert c.provider == "heuristic" and c.category == "card_issue"


def test_llm_success_records_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    content = json.dumps({"category": "card_issue", "priority": "P2", "confidence": 0.9, "rationale": "lost card"})
    resp = httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
        },
        request=httpx.Request("POST", "https://api.openai.com"),
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp)
    c = LLMClassifier("openai").classify(normalize(_t("Lost card", "I lost my card")))
    assert c.provider == "llm:openai" and c.priority == "P2" and c.cost_usd == pytest.approx(0.00021)
