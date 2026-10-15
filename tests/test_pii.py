from triage.pii import find_leaks, luhn_valid, redact


def test_redacts_email_phone_and_card() -> None:
    r = redact("Mail a.b@example.com, call +44 7700 900411 or 202-555-0115, card 4111 1111 1111 1111.")
    assert "[EMAIL]" in r.text and r.text.count("[PHONE]") == 2 and "[CARD ****1111]" in r.text
    assert "example.com" not in r.text and "900411" not in r.text
    assert r.counts == {"email": 1, "phone": 2, "card": 1}


def test_card_requires_luhn_and_keeps_last_four() -> None:
    assert luhn_valid("4242424242424242")
    assert not luhn_valid("4242424242424241")
    assert "[CARD ****4444]" in redact("5555-5555-5555-4444").text
    # 16 digits that fail Luhn are not a card, but still too long to leave in: generic number
    assert "4242424242424241" not in redact("ref 4242424242424241").text


def test_does_not_eat_amounts_dates_or_references() -> None:
    text = "Sent $1,200.50 on 10/10/2026 14:53, ref TRF-52880D, card ends in 8020, 3 days ago"
    assert redact(text).text == text


def test_find_leaks_is_format_insensitive() -> None:
    findings = redact("call +44 7700 900411").findings
    assert find_leaks(findings, "number is 447700900411") != []
    assert find_leaks(findings, "number is [PHONE]") == []
