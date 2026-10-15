"""PII detection and redaction.

Runs before anything else touches a ticket, so classifiers, retrieval, LLM calls, the
queue and the audit log only ever see redacted text. Covers emails, phone numbers and
payment card numbers (Luhn-checked, last four kept because agents need them and PCI DSS
allows it). Names and street addresses are NOT redacted here; see README trade-offs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# 13-19 digits with optional single spaces/dashes between groups.
CARD_RE = re.compile(r"(?<![\w-])\d(?:[ -]?\d){12,18}(?![\w-])")
# Optional +country, optional (area), then 2-4 more groups. Validated by digit count below.
PHONE_RE = re.compile(r"(?<![\w+])(?:\+\d{1,3}[ .-]?)?(?:\(\d{1,4}\)[ .-]?)?\d{2,5}(?:[ .-]?\d{2,5}){1,3}(?![\w])")
LONG_NUMBER_RE = re.compile(r"(?<![\w])\d{11,}(?![\w])")


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


@dataclass
class PiiFinding:
    kind: str  # email | phone | card | number
    value: str


@dataclass
class Redaction:
    text: str
    findings: list[PiiFinding] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.kind] = out.get(f.kind, 0) + 1
        return out


def redact(text: str) -> Redaction:
    findings: list[PiiFinding] = []

    def _email(m: re.Match[str]) -> str:
        findings.append(PiiFinding("email", m.group(0)))
        return "[EMAIL]"

    def _card(m: re.Match[str]) -> str:
        digits = _digits(m.group(0))
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            findings.append(PiiFinding("card", m.group(0)))
            return f"[CARD ****{digits[-4:]}]"
        return m.group(0)

    def _phone(m: re.Match[str]) -> str:
        raw = m.group(0)
        n = len(_digits(raw))
        # Real phone numbers have 8-15 digits and at least one separator, a "+" or
        # parentheses. Bare digit runs (amounts, references) are left to LONG_NUMBER_RE.
        if 8 <= n <= 15 and (raw.startswith("+") or re.search(r"[ .()-]", raw)):
            findings.append(PiiFinding("phone", raw))
            return "[PHONE]"
        return raw

    def _long(m: re.Match[str]) -> str:
        findings.append(PiiFinding("number", m.group(0)))
        return "[NUMBER]"

    out = EMAIL_RE.sub(_email, text)
    out = CARD_RE.sub(_card, out)
    out = PHONE_RE.sub(_phone, out)
    out = LONG_NUMBER_RE.sub(_long, out)
    return Redaction(out, findings)


def find_leaks(original_findings: list[PiiFinding], output: str) -> list[PiiFinding]:
    """Return the original PII values that still appear in `output`.

    Digits-only comparison for cards/phones so a reformatted number still counts as a leak.
    """
    leaks: list[PiiFinding] = []
    out_lower = output.lower()
    out_digits = _digits(output)
    for f in original_findings:
        if f.kind == "email":
            if f.value.lower() in out_lower:
                leaks.append(f)
        else:
            d = _digits(f.value)
            if len(d) >= 8 and d in out_digits:
                leaks.append(f)
    return leaks
