from triage.draft import ExtractiveDrafter, retrieve_for
from triage.ingest import normalize
from triage.models import Draft, RawTicket
from triage.pipeline import Pipeline
from triage.policy import check_draft


def test_retrieval_finds_right_doc(pipeline: Pipeline) -> None:
    hits = pipeline.retriever.search("my transfer has been pending for two days", k=1)
    assert hits[0].section.doc_id == "transfers-and-payments"
    hits = pipeline.retriever.search("tarjeta perdida, bloquearla", k=1)  # glossary expansion
    assert hits[0].section.doc_id == "card-lost-stolen"


def test_draft_is_grounded_and_policy_clean(pipeline: Pipeline) -> None:
    t = normalize(RawTicket("t", "1", "", None, "email", "Locked out", "Locked out after too many password attempts"))
    r = pipeline.triage(t)
    assert r.draft.citations and r.draft.citations[0].doc_id == "account-access-2fa"
    assert "[1]" in r.draft.text and "help.kestrel.example" in r.draft.text
    assert r.draft.policy_violations == []
    # Every sentence quoted from docs appears verbatim in the cited section.
    section = pipeline.retriever.sections
    assert any("locked for 30 minutes" in s.text for s in section) and "30 minutes" in r.draft.text


def test_non_english_ticket_gets_translation_note(pipeline: Pipeline) -> None:
    t = normalize(RawTicket("t", "2", "", None, "email", "Virement", "Mon virement est en attente depuis trois jours"))
    r = pipeline.triage(t)
    assert r.ticket.language == "fr" and r.draft.text.startswith("[Customer wrote in fr")


def test_policy_blocks_bad_drafts() -> None:
    def v(text: str) -> list[str]:
        return check_draft(Draft(text=text + " [1]", citations=[], provider="t"))

    assert any("secret" in x for x in v("Please reply with your full card number and CVV."))
    assert any("refund" in x for x in v("Don't worry, we will refund you today."))
    assert any("internal" in x for x in v("I've passed this to Fraud & Risk as P1."))
    assert any("PII" in x for x in v("We emailed jane@example.com."))
    assert not any("secret" in x for x in v("Kestrel will never ask for your PIN or password."))
    assert "no citation" in check_draft(Draft(text="Hello.", citations=[], provider="t"))


def test_extractive_drafter_only_uses_doc_sentences(pipeline: Pipeline) -> None:
    t = normalize(RawTicket("t", "3", "", None, "email", "ATM fee", "Why was I charged an ATM fee?"))
    cls = pipeline.classifier.classify(t)
    hits = retrieve_for(pipeline.retriever, t, cls)
    d = ExtractiveDrafter().draft(t, cls, hits)
    corpus = " ".join(h.section.text for h in hits)
    quoted = [s.rsplit(" [", 1)[0] for s in d.text.split("\n\n")[1].split("] ") if s.rstrip().endswith(("[1", "[2"))]
    assert quoted and all(q.split(". ")[-1].strip() in corpus for q in quoted)
