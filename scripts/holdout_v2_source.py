"""Fresh held-out set v2 (21 tickets), written on 2026-10-16.

Why it exists: holdout v1 (data/golden/holdout_v1.jsonl) was looked at while diagnosing the
P1-recall failure, so it is now "seen" and only works as a regression set. v2 was written and
committed BEFORE the fraud-escalation rule was implemented and before any code ran against it.
Labels follow data/policies/routing-policy.md, including the fraud/takeover escalation section.
It deliberately includes P1s phrased unlike anything in golden or v1, and fraud lookalikes that
the policy says must stay P2/P3.

Pre-registered gate floors (set before the first run, not tuned to it):
  holdout_v2 P1 recall >= 80%, holdout_v2 P1 over-escalation <= 10% of non-P1 tickets.
What happened on the first run (2026-10-16), recorded so v2's status is clear: P1 recall 7/7, P1
precision 100%, but category/team accuracy 52.4% because all 7 P1s were routed to card/access/general
teams (P1 skips the low-confidence queue, so nothing caught it). The policy already says these
tickets belong to Fraud & Risk, so the classifier now reroutes them (85.7% after). That is one
policy-driven change made after seeing v2; no lexicon edits. v2 is therefore "seen once" for routing.

Do not edit labels to make numbers go up. Run to (re)write data/golden/holdout_v2.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

from golden_source import TEAM

H2 = [
    # --- genuine P1s (7) ---
    ("card used in Manchester", "My card was used at three shops in Manchester this afternoon. I'm at home in Leeds and the card is in my hand.", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("alert then locked out", "Got an alert that someone signed in from a device in Romania. Now my password doesn't work and my balance dropped by 400.", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("told a caller my code", "A man rang claiming to be Kestrel security and I read him the 6 digit code from my texts. Then he hung up.", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("withdrawals at 3am", "Two cash withdrawals of 250 that I did not take out, both at 3am. Please stop this.", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("PIN changed", "I just got a text that my PIN was changed and a new phone was added. I didn't do either and now I can't log in.", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("Alguien entró en mi cuenta", "Alguien entró en mi cuenta y cambió mi correo. No fui yo.", "fraud_dispute", "P1", "disputes-and-fraud", "es"),
    ("paise nikal gaye", "Mere account se 5000 nikal gaye, maine koi payment nahi kiya.", "fraud_dispute", "P1", "disputes-and-fraud", "hi"),
    # --- near-miss fraud lookalikes that must stay below P1 (6) ---
    ("what is this charge", "There's a 14.99 payment to 'PLX*DIGITAL' I don't recognise, but it might be one of my app subscriptions under a different name. Can you tell me who it is?", "fraud_dispute", "P2", "disputes-and-fraud", "en"),
    ("scam text", "Got a text saying my Kestrel card was suspended with a link to click. I didn't click it and deleted it. Just reporting it.", "fraud_dispute", "P2", "disputes-and-fraud", "en"),
    ("balance looks off", "My balance seems about 50 short compared to my spreadsheet. Probably my mistake but can you check?", "fraud_dispute", "P2", "disputes-and-fraud", "en"),
    ("new login email", "Got a 'new device signed in' email at 9pm. That was me on my new laptop, just checking that's expected?", "account_access", "P2", "account-access-2fa", "en"),
    ("hotel damage fee", "The hotel charged my card 180 for a 'damage fee' I never agreed to. I've emailed them twice.", "fraud_dispute", "P3", "disputes-and-fraud", "en"),
    ("left card in taxi", "Left my card in a taxi last night. I've frozen it in the app, no strange payments so far.", "card_issue", "P2", "card-lost-stolen", "en"),
    # --- ordinary mix (8) ---
    ("wages not in", "My employer paid my wages on Thursday and they're still not showing. I've got bills going out Monday.", "payments_transfer", "P2", "transfers-and-payments", "en"),
    ("transfer to Manila", "International transfer to my sister in Manila left on Tuesday, tracking still says in progress.", "payments_transfer", "P3", "transfers-and-payments", "en"),
    ("card rejected online", "Online shops keep rejecting my card at checkout but it works fine in person.", "card_issue", "P3", "card-payments-declined", "en"),
    ("address proof rejected", "Uploaded my council tax bill as proof of address and it was rejected with no reason given.", "kyc_verification", "P3", "identity-verification", "en"),
    ("monthly fee?", "Why am I paying 4.99 a month? I thought my account was free.", "billing_fees", "P4", "fees-and-plans", "en"),
    ("dark mode", "After the update the text in dark mode is unreadable on my Android, I can't read my balance.", "technical_bug", "P3", "app-troubleshooting", "en"),
    ("sole trader", "Do you have a business account for sole traders?", "general_inquiry", "P4", "accounts-and-features", "en"),
    ("Não consigo entrar", "Não consigo entrar na app desde que troquei de telemóvel.", "account_access", "P2", "account-access-2fa", "pt"),
]


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "data" / "golden" / "holdout_v2.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for i, (subject, body, cat, prio, doc, lang) in enumerate(H2, 1):
            fh.write(json.dumps({"id": f"V{i:03d}", "subject": subject, "body": body, "language": lang,
                                 "label": {"category": cat, "team": TEAM[cat], "priority": prio, "expected_doc": doc}},
                                ensure_ascii=False) + "\n")
    print(f"wrote {len(H2)} holdout v2 tickets to {out}")


if __name__ == "__main__":
    main()
