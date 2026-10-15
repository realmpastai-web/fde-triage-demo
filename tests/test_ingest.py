from pathlib import Path

from triage.config import REPO_ROOT
from triage.detect import detect_language, detect_urgency
from triage.ingest import clean_text, ingest, load_raw_dir, normalize, parse_date
from triage.models import RawTicket


def test_parse_messy_dates() -> None:
    for v in [
        "2026-09-28T01:26:00Z",
        "2026-09-28T01:26:00+00:00",
        "09-28-2026 01:26 AM",
        "28/09/2026 01:26",
        "2026-09-28 01:26:00",
        "1790558760",
    ]:
        dt = parse_date(v)
        assert dt is not None and dt.tzinfo is not None, v
    assert parse_date("not a date") is None


def test_clean_text_strips_html_quotes_and_signatures() -> None:
    raw = "<p>My card isn&#39;t working</p>\n\nThanks,\nMaria\n+44 7700 900123\n\nOn Mon, Support wrote:\n> old"
    assert clean_text(raw) == "My card isn't working"


def test_normalize_never_keeps_raw_email() -> None:
    t = normalize(
        RawTicket("csv", "1", "", "Maria.Garcia@Example.com", "EMAIL", "Help", "my email is maria.garcia@example.com")
    )
    assert t.customer_ref and t.customer_ref.startswith("cus_")
    assert "example.com" not in t.text and t.channel == "email" and t.pii_redacted == {"email": 1}


def test_language_and_urgency() -> None:
    assert detect_language("Perdí mi tarjeta ayer, ¿pueden bloquearla por favor?") == "es"
    assert detect_language("Mon virement est en attente depuis trois jours") == "fr"
    assert detect_language("Mera account login nahi ho raha hai") == "hi"
    assert detect_language("My card was declined at the shop") == "en"
    assert detect_urgency("Rent is due tomorrow, URGENT!!").level == "high"
    assert detect_urgency("What interest do pots pay?").level == "low"


def test_ingest_client_export_dedupes_and_redacts() -> None:
    rep = ingest(load_raw_dir(REPO_ROOT / "data" / "raw"))
    assert rep.raw_count >= 150
    assert rep.duplicates_merged >= 5
    assert len(rep.tickets) == rep.raw_count - rep.duplicates_merged
    assert rep.undated == 0
    merged = [t for t in rep.tickets if len(t.source_ids) > 1]
    assert merged, "merged tickets keep every source id"
    assert {"en", "es"} <= set(rep.languages)


def test_dedupe_needs_same_customer(tmp_path: Path) -> None:
    a = RawTicket(
        "csv", "1", "2026-09-01T10:00:00Z", "a@example.com", "email", "Locked", "I am locked out of my account"
    )
    b = RawTicket(
        "csv", "2", "2026-09-01T11:00:00Z", "b@example.com", "email", "Locked", "I am locked out of my account"
    )
    c = RawTicket(
        "csv",
        "3",
        "2026-09-01T12:00:00Z",
        "a@example.com",
        "email",
        "Locked",
        "I am locked out of my account please reply",
    )
    rep = ingest([a, b, c])
    assert len(rep.tickets) == 2 and rep.duplicates_merged == 1
