"""Hand-labelled golden set (40 tickets). Written separately from the template generator,
with its own phrasing, typos and a few genuinely ambiguous tickets.
Labels follow data/policies/routing-policy.md. Run to (re)write data/golden/golden.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

TEAM = {"fraud_dispute": "Fraud & Risk", "account_access": "Identity & Access", "card_issue": "Cards Ops",
        "payments_transfer": "Payments Ops", "kyc_verification": "Compliance Ops", "technical_bug": "App Engineering",
        "billing_fees": "Billing Ops", "general_inquiry": "Tier-1 Support"}

# (subject, body, category, priority, expected_doc, language)
G = [
    ("cant find my card", "can't find my kestrel card anywhere since the weekend. pls block it, I'll need a replacement", "card_issue", "P2", "card-lost-stolen", "en"),
    ("Declined at petrol station", "Card was declined at the petrol station twice today, balance is fine. Embarrassing.", "card_issue", "P3", "card-payments-declined", "en"),
    ("ATM abroad", "In Lisbon for work, two ATMs refused my card. Need cash for a taxi, what's wrong?", "card_issue", "P3", "card-payments-declined", "en"),
    ("New card", "When does the new card come? My current one expires end of November.", "card_issue", "P4", "card-payments-declined", "en"),
    ("Card stuck in the post", "Replacement card ordered 12 days ago, still nothing. I can only use Apple Pay.", "card_issue", "P3", "card-lost-stolen", "en"),
    ("online payment declined", "Trying to pay for flights, my card 4242 4242 4242 4242 keeps getting declined. Please fix", "card_issue", "P3", "card-payments-declined", "en"),
    ("Rent transfer pending", "Paid my rent 3 days ago and it STILL shows pending. Landlord is threatening a late fee. Urgent!!", "payments_transfer", "P2", "transfers-and-payments", "en"),
    ("where is my salary", "Payroll says salary went out on the 25th, nothing has arrived. Can you check?", "payments_transfer", "P2", "transfers-and-payments", "en"),
    ("wrong IBAN", "I typed the wrong account number and sent 300 EUR to someone else. Can it be recalled?", "payments_transfer", "P2", "transfers-and-payments", "en"),
    ("Transfer to Kenya", "Sent money to my mother in Nairobi yesterday, how long until she receives it?", "payments_transfer", "P3", "transfers-and-payments", "en"),
    ("Transfer returned?", "My transfer shows failed but the 120 USD is not back in my balance.", "payments_transfer", "P3", "transfers-and-payments", "en"),
    ("locked", "Locked out after typing my password wrong a few times. Need to pay a bill today.", "account_access", "P2", "account-access-2fa", "en"),
    ("no verification code", "Verification code never comes to my phone +44 7700 900411, I've been trying for an hour.", "account_access", "P2", "account-access-2fa", "en"),
    ("Changed phones", "I switched to a new phone and the app wants me to approve on the old one, which is broken.", "account_access", "P2", "account-access-2fa", "en"),
    ("reset link", "Reset password link expired before I could use it, and now I get no email at nora.k@example.com", "account_access", "P2", "account-access-2fa", "en"),
    ("ID check taking forever", "Uploaded passport last Tuesday, still 'under review'. My limits are tiny until this is done.", "kyc_verification", "P3", "identity-verification", "en"),
    ("Driving licence not accepted", "The app keeps rejecting my driving licence photo, says glare. Third attempt now.", "kyc_verification", "P3", "identity-verification", "en"),
    ("address proof", "Is a bank statement from another bank OK as proof of address?", "kyc_verification", "P4", "identity-verification", "en"),
    ("weekend FX", "Why did I pay extra on a currency payment on Saturday? Nobody mentioned a markup.", "billing_fees", "P4", "fees-and-plans", "en"),
    ("Plus charge after cancel", "I cancelled Plus on the 2nd and got charged 9.99 again. Please refund it.", "billing_fees", "P4", "fees-and-plans", "en"),
    ("ATM withdrawal fee", "Charged 1 USD for an ATM withdrawal. I've only taken cash 4 times this month?", "billing_fees", "P4", "fees-and-plans", "en"),
    ("payment I didn't make", "There's a 89.99 payment to StreamFlix I never made. My card is in my wallet.", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("HELP someone in my account", "Someone changed my email and moved 1,500 out of my account tonight. I didn't do this!!", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("Never received order", "Bought headphones from TechHaus 3 weeks ago, never arrived, seller ignores me. Want my money back.", "fraud_dispute", "P3", "disputes-and-fraud", "en"),
    ("suspicious message", "Got an SMS saying my Kestrel account is frozen and to call a number. I gave them a code. Is this you?", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("double charge", "Corner Cafe took the payment twice for one coffee order last week.", "fraud_dispute", "P3", "disputes-and-fraud", "en"),
    ("App closes", "App closes immediately when I tap Statements. Pixel 7, latest version.", "technical_bug", "P3", "app-troubleshooting", "en"),
    ("export", "Exporting a year of transactions fails with 'something went wrong'.", "technical_bug", "P3", "app-troubleshooting", "en"),
    ("notifications gone", "Since updating I don't get payment notifications at all.", "technical_bug", "P3", "app-troubleshooting", "en"),
    ("joint account", "Can my wife and I open a shared account with you?", "general_inquiry", "P4", "accounts-and-features", "en"),
    ("interest on pots", "What rate do savings pots earn right now?", "general_inquiry", "P4", "accounts-and-features", "en"),
    ("closing", "I'd like to close my Kestrel account, what do I need to do?", "general_inquiry", "P4", "accounts-and-features", "en"),
    ("is plus worth it", "Thinking about upgrading to Plus, what do I actually get?", "general_inquiry", "P4", "fees-and-plans", "en"),
    ("Tarjeta robada", "Me robaron la tarjeta esta mañana. ¿Cómo la bloqueo y pido otra?", "card_issue", "P2", "card-lost-stolen", "es"),
    ("No me llega el código", "No me llega el código de verificación y no puedo entrar a la cuenta.", "account_access", "P2", "account-access-2fa", "es"),
    ("Pagamento que não fiz", "Apareceu um pagamento de 200 euros que eu não fiz. Meu cartão está comigo.", "fraud_dispute", "P1", "disputes-and-fraud", "pt"),
    ("Virement en attente", "Mon virement de 400 euros est en attente depuis trois jours.", "payments_transfer", "P3", "transfers-and-payments", "fr"),
    ("verification", "Verification pending kyu hai? Maine documents 4 din pehle upload kiye the.", "kyc_verification", "P3", "identity-verification", "hi"),
    ("frozen card + charges", "Froze my card because I lost it but I can see two charges from before I froze it that aren't mine.", "fraud_dispute", "P1", "disputes-and-fraud", "en"),
    ("money missing", "My balance is 200 lower than it should be and I can't work out why.", "fraud_dispute", "P2", "disputes-and-fraud", "en"),
]


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "data" / "golden" / "golden.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for i, (subject, body, cat, prio, doc, lang) in enumerate(G, 1):
            fh.write(json.dumps({"id": f"G{i:03d}", "subject": subject, "body": body, "language": lang,
                                 "label": {"category": cat, "team": TEAM[cat], "priority": prio, "expected_doc": doc}},
                                ensure_ascii=False) + "\n")
    print(f"wrote {len(G)} golden tickets to {out}")


if __name__ == "__main__":
    main()
