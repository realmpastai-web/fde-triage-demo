"""Held-out set v1 (20 tickets). Written AFTER the lexicon was tuned on golden.jsonl and never used to
edit the lexicon. Now SEEN: it was inspected in Oct 2026 while fixing P1 recall, so it is a regression
set only; scripts/holdout_v2_source.py is the newer one. The gap between golden and holdout accuracy is the honest number: it is
what the heuristic does on phrasing it has not seen. Run to (re)write data/golden/holdout_v1.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

from golden_source import TEAM

H = [
    ("Help", "My debit card isn't in my bag or my coat. I'm worried someone picked it up.", "card_issue", "P2", "card-lost-stolen", "en"),
    ("payment fails", "Every time I try to buy something on the bus app the payment bounces back.", "card_issue", "P3", "card-payments-declined", "en"),
    ("money hasn't shown up", "My friend paid me back 60 dollars on Friday via bank transfer and it's not in my account.", "payments_transfer", "P3", "transfers-and-payments", "en"),
    ("Mortgage payment", "Payment to my mortgage lender has been stuck since Monday, they'll charge me a penalty tomorrow.", "payments_transfer", "P2", "transfers-and-payments", "en"),
    ("cannot get in", "App says my credentials are wrong but I'm sure they're right. Now it won't let me try again.", "account_access", "P2", "account-access-2fa", "en"),
    ("2FA", "Two-factor codes aren't coming through, I changed my number last month.", "account_access", "P2", "account-access-2fa", "en"),
    ("documents", "How long does it normally take for you to check my ID? It's been 3 days.", "kyc_verification", "P3", "identity-verification", "en"),
    ("photo keeps failing", "Your app says my face doesn't match my passport. It is literally my face.", "kyc_verification", "P3", "identity-verification", "en"),
    ("Why the extra charge", "I withdrew cash in Tokyo and lost more than I expected. Was there a charge?", "billing_fees", "P4", "fees-and-plans", "en"),
    ("cancel subscription", "How do I stop paying for the premium plan?", "billing_fees", "P4", "fees-and-plans", "en"),
    ("strange payments", "Three small payments to an online game I've never heard of appeared overnight.", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("refund from shop", "Returned a jacket to UrbanWear a month ago, they still haven't refunded me.", "fraud_dispute", "P3", "disputes-and-fraud", "en"),
    ("Was this phishing?", "Someone called saying they were from Kestrel and asked me to move my savings to a safe account.", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("app won't open", "Since this morning the app just shows the logo and goes back to the home screen. iPhone 12.", "technical_bug", "P3", "app-troubleshooting", "en"),
    ("statement download", "The PDF statement for August won't download, it just spins.", "technical_bug", "P3", "app-troubleshooting", "en"),
    ("kids", "Can I open an account for my 15 year old?", "general_inquiry", "P4", "accounts-and-features", "en"),
    ("Moving countries", "I'm relocating to Canada next year, can I keep using my account there?", "general_inquiry", "P4", "accounts-and-features", "en"),
    ("Mi tarjeta no funciona", "Mi tarjeta no funciona en las tiendas desde ayer, tengo saldo suficiente.", "card_issue", "P3", "card-payments-declined", "es"),
    ("Compte bloqué", "Je n'arrive plus à me connecter, mon compte est bloqué après plusieurs essais.", "account_access", "P2", "account-access-2fa", "fr"),
    ("fee kyu kata", "Mere account se ek fee kata gaya hai jo mujhe samajh nahi aaya.", "billing_fees", "P4", "fees-and-plans", "hi"),
]


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "data" / "golden" / "holdout_v1.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for i, (subject, body, cat, prio, doc, lang) in enumerate(H, 1):
            fh.write(json.dumps({"id": f"H{i:03d}", "subject": subject, "body": body, "language": lang,
                                 "label": {"category": cat, "team": TEAM[cat], "priority": prio, "expected_doc": doc}},
                                ensure_ascii=False) + "\n")
    print(f"wrote {len(H)} holdout v1 tickets to {out}")


if __name__ == "__main__":
    main()
