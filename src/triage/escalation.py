"""Fraud and account-takeover escalation: the P1 rule from routing-policy.md.

Policy (see "Fraud and account-takeover escalation" in data/policies/routing-policy.md): a ticket
is P1 when the customer reports (1) money moved without their consent, (2) someone else in
control of the account, (3) credentials or codes handed over, or (4) an impersonation scam in
progress. Under-ranking fraud costs more than over-ranking it, so when a condition plausibly
holds we escalate. The near misses the policy keeps below P1 are encoded as explicit vetoes, each
scoped to the one condition it qualifies.

Each condition is a conjunction of *families* of signals (e.g. "non-consent" AND "money moved"),
not a list of whole sentences, so it generalises to phrasings the golden set never used. Pure
and deterministic; it applies to the heuristic and, as a safety floor, to the LLM path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in parts), re.IGNORECASE)


# --- (1) money moved without consent -------------------------------------------------------
# The customer says they did not do / authorise / recognise something.
NON_CONSENT = _rx(
    r"\b(?:did ?n[o']?t|did not|never|have ?n[o']?t|haven't)\s+(?:make|made|authori[sz]e|authori[sz]ed|approve|"
    r"approved|do|recogni[sz]e|withdraw|spend|spent|buy|bought|order|ordered|sign up|signed up)\b",
    r"\b(?:did ?n[o']?t|did not|never)\s+(?:take|took) (?:it |them |this |that )?out\b",
    r"\b(?:do ?n[o']?t|don't|do not)\s+recogni[sz]e\b",
    r"\b(?:not|aren't|isn't|wasn't|weren't)\s+(?:mine|me)\b",
    r"\bno(?:t)? (?:one|body) i know\b",
    r"\bwithout my (?:permission|consent|knowledge|authori[sz]ation)\b",
    r"\bunauthori[sz]ed\b",
    r"\bnever (?:heard of|used|been to|shopped (?:at|with)|signed up)\b",
    r"\b(?:card|it)(?: is|'s| was) (?:still )?(?:in my (?:hand|wallet|pocket|bag|purse)|with me)\b",
    # es / pt / fr / hi
    r"\bno (?:hice|reconozco|autoric[eé])\b",
    r"\bn[aã]o (?:fiz|reconhe[cç]o|autorizei)\b",
    r"\b(?:n'ai pas fait|ne reconnais pas|pas autoris[ée]e?s?)\b",
    r"\bmaine (?:koi|ye|yeh)?\s*(?:payment|transaction|transfer)?\s*nahi? (?:kiya|kiye|ki)\b",
)
# Evidence that money actually moved (or that a card/account was used).
MONEY_MOVED = _rx(
    r"\b(?:payments?|charges?|charged|transactions?|transfers?|transferred|withdrawals?|withdrawn|withdrew|"
    r"debits?|debited|purchases?|bought|spent|taken|moved|sent|cash)\b",
    r"\bcard was used\b|\bused my card\b",
    r"\b\d+(?:[.,]\d{2})?\s*(?:eur|usd|gbp|inr|euros?|dollars?|pounds?|rs)?\b.*\b(?:out|gone|missing|left)\b",
    r"\bbalance (?:dropped|went down|fell)\b",
    r"\b(?:pagamento|pago|cargo|paiement|virement|transferencia|nikal|nikle|kat gaye)\w*",
)
# Merchant disputes the customer authorised, and Kestrel fee/plan disputes: P3/P4 per policy,
# even when worded as "I never agreed to" or "I didn't authorise the second charge".
AUTHORISED_DISPUTE = _rx(
    r"\b(?:charged|took (?:the )?payment) (?:me )?twice\b",
    r"\bdouble[- ]charged?\b",
    r"\bnever (?:arrived|delivered|received (?:the|my) (?:order|item|parcel))\b",
    r"\b(?:haven't|hasn't|have not|has not|not|never|still not) (?:been )?refunded\b|\brefund (?:from|by)\b",
    r"\breturned (?:it|the|a|an|my)\b|\bseller\b",
    r"\b(?:fee|fees|my subscription|my plan|membership)\b",
    r"\bwrong amount\b",
    # A declined or blocked attempt means no money moved: still fraud, but P2.
    r"\b(?:declined|was blocked|got blocked|was refused|was rejected)\b",
)
# The customer suggests the payment may be their own (descriptor confusion).
SELF_HEDGE = _rx(
    r"\b(?:might|may|could) (?:be|have been) (?:mine|me|one of my|my)\b",
    r"\b(?:probably|maybe|perhaps) (?:mine|my|me)\b",
    r"\bunder a different name\b",
)

# --- (2) someone else in control of the account -------------------------------------------
THIRD_PARTY_CONTROL = _rx(
    r"\bhacked\b",
    r"\b(?:taken over|took over)\b",
    r"\bsomeone(?: else)?\s+(?:has\s+)?(?:logged|signed|got|is|was|has been)\s+(?:in|into)\b",
    r"\bsomeone (?:else )?(?:in|inside|accessed|got into|has access to) my account\b",
    r"\bsomeone(?: else)?\s+(?:has\s+)?changed\b",
    r"\b(?:alguien|algu[eé]m|quelqu'un)\s+"
    r"(?:entr[oó]|entrou|acced[ií]\w*|s'est connect[ée]|cambi[oó]|mudou|a chang[ée])",
)
# A change to credentials or devices that the customer says they did not make.
ACCOUNT_CHANGE = _rx(
    r"\b(?:email|e-mail|password|phone(?: number)?|number|pin|device|phone|login details)\b"
    r".{0,40}\b(?:was|were|has been|got|been)?\s*(?:changed|added|reset|updated)\b",
    r"\bnew (?:phone|device) (?:was )?added\b",
    r"\b(?:cambi[oó] mi (?:correo|contraseña|tel[eé]fono)|mudou (?:meu|o) (?:email|senha))\b",
)
DENIED_BY_CUSTOMER = _rx(
    r"\bi did ?n[o']?t do (?:this|that|it|either|any of)\b",
    r"\bi did not do\b",
    r"\b(?:not|wasn't|weren't) (?:me|by me)\b",
    r"\bwithout me\b",
    r"\bno fui yo\b|\bn[aã]o fui eu\b|\bce n'[ée]tait pas moi\b",
    r"\bdidn'?t (?:request|change|add|ask for)\b",
)
LOCKED_OUT = _rx(
    r"\blocked out\b",
    r"\b(?:can't|cannot|can not|unable to) (?:log|sign) ?in\b",
    r"\bcan't get in\b|\bcannot get in\b",
    r"\bpassword (?:doesn't|does not|no longer|won't) work\b",
    r"\b(?:no puedo entrar|n[aã]o consigo entrar|je n'arrive plus [àa] me connecter)\b",
)
THIRD_PARTY_SIGN = _rx(
    r"\bsomeone (?:else|has|is|was|logged|signed|used|changed|got|tried)\b",
    r"\bsuspicious\b",
    r"\b(?:alert|email|text|sms|notification)\b.{0,40}\b(?:signed|logged|login|changed|new device)\b",
    r"\b(?:new|unknown|another) device\b",
    r"\bdidn'?t (?:request|change|do)\b",
)
SELF_CONFIRMED = _rx(r"\b(?:that|it) was (?:just )?me\b", r"\bwas me on\b")

# --- (3) credentials or codes handed over ---------------------------------------------------
CREDENTIAL_SHARED = _rx(
    r"\b(?:gave|shared|told|read|sent|texted|typed|entered|put)\b(?:\s+\w+){0,5}?\s+(?:the|my|a|him|her|them)?"
    r"\s*(?:\d[- ]digit\s+)?(?:code|codes|otp|pin|password|passcode|card details|card number|cvv|security code|"
    r"one[- ]time)\b",
    r"\b(?:entered|typed|put) (?:in )?my (?:details|card|login)\b.{0,40}\b(?:link|site|website|page)\b",
    r"\b(?:clicked|opened) (?:a|the|their) link\b.{0,60}\b(?:entered|typed|logged in|gave)\b",
    r"\bgave them a code\b",
)

# --- (4) impersonation scam in progress ----------------------------------------------------
IMPERSONATION = _rx(
    r"\b(?:called|rang|phoned|texted|messaged|emailed|contacted|whatsapp\w*)\b.{0,60}"
    r"\b(?:from kestrel|from (?:the|my|your) bank|claiming to be|pretending to be|said (?:they|he|she) (?:was|were)"
    r"|saying (?:they|he|she) (?:was|were)|police|fraud team|security team)",
    r"\bpretending to be\b|\bclaiming to be\b",
    r"\b(?:caller|someone|a man|a woman|a person|a guy)\b.{0,30}\bfrom ['\"]?(?:kestrel|the bank|your bank|my bank|"
    r"the fraud|the police|security)",
    # Nobody legitimate asks a customer to move money to a "safe account": the phrase is the scam.
    r"\bsafe account\b",
)
SCAM_ASK = _rx(
    r"\bsafe account\b",
    r"\b(?:asked|told|wanted|wants|want|instructed|asking|telling)\b.{0,40}\b(?:move|transfer|send|withdraw)\b",
    r"\b(?:asked|wanted|wants|asking)\b.{0,40}\b(?:code|otp|pin|password|card details)\b",
)
REFUSED = _rx(
    r"\bi (?:hung up|ignored|deleted|blocked|refused|reported)\b",
    r"\bdid ?n[o']?t (?:give|share|send|move|transfer|click|reply|answer|do (?:it|anything))\b",
    r"\bdid not (?:give|share|send|move|transfer|click|reply)\b",
    r"\bnothing (?:was )?(?:shared|sent|moved)\b",
)


@dataclass(frozen=True)
class Escalation:
    condition: str  # which policy condition fired
    evidence: str  # the text span that fired it, for the rationale shown to the agent

    def reason(self) -> str:
        return f"P1 fraud/takeover rule ({self.condition}): '{self.evidence}'"


def _span(m: re.Match[str] | None) -> str:
    return m.group(0).strip()[:60] if m else ""


def fraud_escalation(text: str) -> Escalation | None:
    """Return why this ticket meets a P1 condition of the fraud/takeover policy, or None."""
    low = " ".join(text.lower().split())

    # (3) credentials handed over: checked first, it is the most time-critical.
    if m := CREDENTIAL_SHARED.search(low):
        return Escalation("credentials shared", _span(m))

    # (2) someone else in control of the account.
    if not SELF_CONFIRMED.search(low):
        if m := THIRD_PARTY_CONTROL.search(low):
            return Escalation("third party in account", _span(m))
        if (m := ACCOUNT_CHANGE.search(low)) and DENIED_BY_CUSTOMER.search(low):
            return Escalation("account details changed by someone else", _span(m))
        if (m := LOCKED_OUT.search(low)) and THIRD_PARTY_SIGN.search(low):
            return Escalation("locked out with signs of a third party", _span(m))

    # (4) impersonation scam asking for money or codes, not yet refused.
    if (m := IMPERSONATION.search(low)) and SCAM_ASK.search(low) and not REFUSED.search(low):
        return Escalation("impersonation scam in progress", _span(m))

    # (1) money moved without consent, unless it is an authorised merchant/fee dispute or the
    # customer suggests it may be their own payment.
    if (
        (m := NON_CONSENT.search(low))
        and MONEY_MOVED.search(low)
        and not AUTHORISED_DISPUTE.search(low)
        and not SELF_HEDGE.search(low)
    ):
        return Escalation("money moved without consent", _span(m))
    return None
