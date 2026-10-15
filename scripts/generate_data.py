"""Generate the synthetic Kestrel support export used by the demo.

Everything here is fictional. Emails use example.com / example.org, phone numbers come
from ranges reserved for fiction (UK 07700 900xxx, US 555-01xx), and card numbers are
public processor test numbers. The output is deliberately messy, the way a real export is:
two source systems with different schemas, mixed date formats, HTML entities, signatures,
quoted replies, duplicates and several languages.

Run: python scripts/generate_data.py   (deterministic, seed below)
"""

from __future__ import annotations

import csv
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

SEED = 20261016
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

FIRST = ["maria", "arjun", "lena", "tom", "aisha", "kenji", "sofia", "rahul", "chloe", "diego",
         "fatima", "liam", "priya", "noah", "camila", "omar", "emma", "ravi", "julia", "marco"]
LAST = ["garcia", "nair", "fischer", "baker", "khan", "sato", "rossi", "iyer", "martin", "lopez",
        "ali", "walsh", "menon", "clark", "silva", "haddad", "moreau", "das", "costa", "bianchi"]
DOMAINS = ["example.com", "example.org", "mail.example.net"]
MERCHANTS = ["CityMart", "Bluebird Air", "StreamFlix", "Corner Cafe", "TechHaus", "Urban Eats",
             "GreenGrocer", "Nimbus Hotels", "QuickRide", "BookNook"]
COUNTRIES = ["Portugal", "Japan", "Mexico", "Thailand", "Germany", "Kenya", "Canada"]
DEVICES = ["iPhone 13", "Pixel 7", "Galaxy S22", "iPhone 15 Pro", "OnePlus 11"]
TEST_CARDS = ["4111 1111 1111 1111", "4242424242424242", "5555-5555-5555-4444",
              "4000 0566 5566 5556", "3782 822463 10005"]

# (category, subject, body). Placeholders are filled per ticket.
TEMPLATES: list[tuple[str, str, str]] = [
    ("card_issue", "Lost my card", "I think I left my Kestrel card at a restaurant last night. Can you block it and send a new one? Card ends in {last4}."),
    ("card_issue", "Card declined at {merchant}", "My card got declined at {merchant} for {amount} even though I have money in the account. What is going on?"),
    ("card_issue", "replacement card not here", "I ordered a replacement card {days} days ago and it still hasn't arrived. Nothing in the app shows tracking."),
    ("card_issue", "Card not working abroad", "I'm travelling in {country} and my card keeps getting declined at ATMs. Chip and PIN at shops works."),
    ("card_issue", "contactless", "Tap to pay stopped working on my physical card since last week. Chip and PIN still works fine."),
    ("card_issue", "Card expiring", "My card expires next month. Will a new one be sent automatically or do I need to order it?"),
    ("card_issue", "declined online", "My card number is {card} and it was declined online at {merchant}. Please check what's wrong."),
    ("payments_transfer", "Transfer still pending", "I sent {amount} to my landlord on {date} and it is still pending. Rent is due tomorrow!"),
    ("payments_transfer", "Transfer failed - money gone", "A bank transfer failed but the money left my balance. Reference {ref}. When do I get it back?"),
    ("payments_transfer", "sent money to wrong account", "I sent {amount} to the wrong account by mistake this morning. Can you reverse the transfer?"),
    ("payments_transfer", "Salary not received", "My employer says my salary was sent on {date} but I don't see the incoming payment anywhere."),
    ("payments_transfer", "International transfer taking long", "How long does an international transfer to {country} take? It's been 4 days and the recipient has nothing."),
    ("account_access", "Locked out", "I'm locked out of my account after too many password attempts. Can't access anything."),
    ("account_access", "No SMS code", "I'm not receiving the SMS verification code on {phone}. Tried 5 times."),
    ("account_access", "new phone can't login", "Got a new phone and can't log in, the app keeps asking to confirm on my old device which I sold."),
    ("account_access", "password reset email", "The password reset email never arrives. My email is {email}."),
    ("account_access", "Account restricted??", "The app says my account is restricted and I can't sign in properly. Why? Nobody told me anything."),
    ("kyc_verification", "Verification stuck in review", "I uploaded my ID {days} days ago and verification still says in review. I need to lift my limits."),
    ("kyc_verification", "passport rejected", "My passport photo was rejected twice. What am I doing wrong?"),
    ("kyc_verification", "Proof of address", "What documents do you accept as proof of address? I don't have utility bills in my name."),
    ("kyc_verification", "Selfie check fails", "The selfie verification keeps failing even in good light. It says the face doesn't match my ID document."),
    ("billing_fees", "Unknown fee", "I was charged a {fee} fee I don't recognise, it says FX markup. Please explain and refund it."),
    ("billing_fees", "Charged after cancelling Plus", "I cancelled Kestrel Plus but was still charged {amount} this month for the plan."),
    ("billing_fees", "ATM fee?", "Why was I charged an ATM fee? I thought the first withdrawals each month were free."),
    ("billing_fees", "Plan fee refund", "Can I get a refund for this month's Plus subscription? I only used it for two days."),
    ("fraud_dispute", "Transaction I didn't make", "There's a charge of {amount} from {merchant} that I didn't make. I still have my card with me."),
    ("fraud_dispute", "ACCOUNT HACKED", "Someone logged into my account and sent money out!! URGENT please help, {amount} gone."),
    ("fraud_dispute", "Dispute - item never delivered", "{merchant} never delivered my order and won't reply. I want to dispute the {amount} charge."),
    ("fraud_dispute", "Charged twice", "{merchant} charged me twice for the same purchase on {date}. I contacted them two weeks ago, no answer."),
    ("fraud_dispute", "Scam text", "Got a text pretending to be Kestrel asking for my PIN and I clicked the link. Did I get scammed?"),
    ("fraud_dispute", "wallet stolen", "My wallet was stolen on the train and now there are transactions I didn't make. Please help asap."),
    ("technical_bug", "App crashes", "The app crashes every time I open the statements tab on my {device}."),
    ("technical_bug", "CSV export broken", "Exporting transactions to CSV gives an error every time, even for one month."),
    ("technical_bug", "No notifications", "I stopped getting push notifications for payments after the last update on {device}."),
    ("technical_bug", "Balance screen blank", "The home screen shows a blank balance and a spinning wheel forever since the update."),
    ("general_inquiry", "Joint account?", "Do you offer joint accounts? My partner and I want to share expenses."),
    ("general_inquiry", "How to close account", "How do I close my account? I'm moving abroad."),
    ("general_inquiry", "Savings interest", "What interest do savings pots pay at the moment?"),
    ("general_inquiry", "Standard vs Plus", "What's the difference between Standard and Plus? Is Plus worth it if I travel twice a year?"),
    ("general_inquiry", "business use", "Can I use Kestrel for my small bakery business?"),
    ("general_inquiry", "Feedback", "Just wanted to say the new app design is great, much faster than before."),
]

FOREIGN: list[tuple[str, str, str, str]] = [
    ("es", "card_issue", "Tarjeta perdida", "Perdí mi tarjeta ayer en el metro. ¿Pueden bloquearla y enviarme una nueva por favor?"),
    ("es", "payments_transfer", "Transferencia pendiente", "Hice una transferencia de {amount} hace tres días y sigue pendiente. Necesito ayuda urgente."),
    ("es", "fraud_dispute", "Cargo no reconocido", "Hay un cargo de {amount} de {merchant} que yo no hice. Por favor ayúdenme, es fraude."),
    ("es", "account_access", "No puedo entrar", "No puedo entrar a mi cuenta, dice que mi contraseña es incorrecta y la cuenta está bloqueada."),
    ("pt", "kyc_verification", "Verificação de identidade", "Enviei meu documento há uma semana e a verificação ainda está em análise. Quanto tempo demora?"),
    ("pt", "billing_fees", "Taxa cobrada", "Fui cobrado uma taxa de saque no caixa eletrônico que não entendo. Podem explicar?"),
    ("pt", "card_issue", "Cartão recusado", "Meu cartão foi recusado no supermercado mas tenho saldo. O que aconteceu?"),
    ("fr", "payments_transfer", "Virement non reçu", "Mon salaire a été envoyé le {date} mais je ne vois pas le virement sur mon compte."),
    ("fr", "technical_bug", "L'application plante", "L'application plante à chaque fois que j'ouvre mes relevés sur mon {device}."),
    ("fr", "fraud_dispute", "Paiement frauduleux", "Je vois un paiement de {amount} que je n'ai pas fait. Ma carte est toujours avec moi. C'est urgent."),
    ("hi", "account_access", "login nahi ho raha", "Mera account login nahi ho raha, OTP nahi aa raha hai. Kya karu? Bahut jaldi chahiye."),
    ("hi", "payments_transfer", "paise nahi aaye", "Maine {amount} transfer kiya tha lekin paise abhi tak nahi aaye. Transfer pending dikha raha hai."),
    ("hi", "card_issue", "card kho gaya", "Mera card kho gaya hai, please block kar dijiye aur naya card bhej dijiye."),
]

SIGNATURES = ["", "", "", "\n\nSent from my iPhone", "\n\nThanks,\n{name}\n{phone}", "\n\n--\n{name} | {email}",
              "\n\nRegards"]
QUOTED = "\n\nOn Mon, Kestrel Support <support@kestrel.example> wrote:\n> Thanks for contacting Kestrel. A member of our team will reply soon.\n> Ticket received."

# Historical first-response time (minutes) in the legacy queue, by category. Synthetic,
# shaped like a typical backlog: everything waits in one FIFO queue, so urgent tickets
# barely move faster than routine ones.
FRT_MEDIAN = {"fraud_dispute": 290, "account_access": 340, "card_issue": 380, "payments_transfer": 410,
              "kyc_verification": 520, "billing_fees": 600, "technical_bug": 640, "general_inquiry": 700}


def luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def fill(rng: random.Random, text: str, person: dict[str, str]) -> str:
    base = datetime(2026, 9, 1) + timedelta(days=rng.randint(0, 40))
    values = {
        "last4": str(rng.randint(1000, 9999)),
        "merchant": rng.choice(MERCHANTS),
        "amount": rng.choice(["$", "USD ", "€", "EUR "]) + f"{rng.randint(12, 2400)}.{rng.randint(0, 99):02d}",
        "days": str(rng.randint(5, 21)),
        "country": rng.choice(COUNTRIES),
        "card": rng.choice(TEST_CARDS),
        "date": base.strftime(rng.choice(["%d %b", "%B %d", "%d/%m"])),
        "ref": f"TRF-{rng.randint(10000, 99999)}{rng.choice('ABCDEFGH')}",
        "phone": person["phone"],
        "email": person["email"],
        "fee": rng.choice(["$4.20", "€2.99", "USD 1.85", "$12.00"]),
        "device": rng.choice(DEVICES),
        "name": person["name"],
    }
    return text.format(**values)


def make_person(rng: random.Random) -> dict[str, str]:
    first, last = rng.choice(FIRST), rng.choice(LAST)
    sep = rng.choice([".", "_", ""])
    email = f"{first}{sep}{last}{rng.randint(1, 99)}@{rng.choice(DOMAINS)}"
    if rng.random() < 0.5:
        phone = f"+44 7700 900{rng.randint(100, 999)}"
    else:
        phone = rng.choice(["+1 (202) 555-01", "202-555-01", "+1 202 555 01"]) + f"{rng.randint(10, 99)}"
    return {"name": f"{first.title()} {last.title()}", "email": email if rng.random() > 0.15 else email.upper(), "phone": phone}


def messy_date(rng: random.Random, dt: datetime) -> str:
    fmt = rng.choice(["iso", "iso_z", "us", "eu", "plain"])
    ymd = "%04d-%02d-%02d" % (dt.year, dt.month, dt.day)
    hms = "%02d:%02d:%02d" % (dt.hour, dt.minute, dt.second)
    if fmt == "iso":
        return f"{ymd}T{hms}+00:00"
    if fmt == "iso_z":
        return f"{ymd}T{hms}Z"
    if fmt == "us":
        return dt.strftime("%m-%d-%Y %I:%M %p")
    if fmt == "eu":
        return dt.strftime("%d/%m/%Y %H:%M")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def messify(rng: random.Random, body: str, person: dict[str, str]) -> str:
    if rng.random() < 0.15:
        body = "<p>" + body.replace("&", "&amp;").replace("'", "&#39;") + "</p>"
    if rng.random() < 0.2:
        body = "  " + body.replace(". ", ".\n\n", 1) + "   "
    body += fill(rng, rng.choice(SIGNATURES), person)
    if rng.random() < 0.12:
        body += QUOTED
    return body


def frt(rng: random.Random, category: str) -> int:
    return max(4, int(rng.lognormvariate(0, 0.55) * FRT_MEDIAN[category]))


def main() -> None:
    rng = random.Random(SEED)
    RAW.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)
    rows: list[dict[str, str]] = []
    convos: list[dict[str, object]] = []
    people = [make_person(rng) for _ in range(90)]

    n_csv, n_chat = 124, 26
    for i in range(n_csv + n_chat):
        person = rng.choice(people)
        dt = start + timedelta(minutes=rng.randint(0, 60 * 24 * 42))
        if rng.random() < 0.13:
            lang, category, subject, body = rng.choice(FOREIGN)
        else:
            lang = "en"
            category, subject, body = rng.choice(TEMPLATES)
        subject_f = fill(rng, subject, person)
        body_f = fill(rng, body, person)
        if lang == "en" and rng.random() < 0.08:
            subject_f, body_f = subject_f.upper(), body_f.upper() + " !!!"
        if i < n_csv:
            rows.append({
                "Ticket ID": f"ZD-{48000 + i}",
                "Created": messy_date(rng, dt),
                "Customer Email": person["email"],
                "Channel": rng.choice(["email", "Email", "EMAIL", "web_form", "Web Form", "app", "In-App"]),
                "Subject": subject_f if rng.random() > 0.07 else "",
                "Description": messify(rng, body_f, person),
                "First Response (min)": str(frt(rng, category)),
            })
        else:
            msgs = [{"from": "bot", "text": "Hi! I'm Kes, the Kestrel assistant. How can I help?"},
                    {"from": "customer", "text": subject_f},
                    {"from": "bot", "text": "Could you tell me a bit more?"},
                    {"from": "customer", "text": body_f}]
            convos.append({
                "conversation_id": f"chat_{rng.randint(10**7, 10**8 - 1)}",
                "started_at": int(dt.timestamp()),
                "user": {"email": person["email"], "phone": person["phone"]},
                "first_response_seconds": frt(rng, category) * 60,
                "messages": msgs,
            })

    # Duplicates: the same customer writing twice through the same form, sometimes with
    # small edits. Real exports are full of these.
    for src in rng.sample(rows[:110], 9):
        dup = dict(src)
        dup["Ticket ID"] = f"ZD-{48000 + len(rows) + 50}"
        dup["Description"] = src["Description"].replace("  ", " ") + (" Please reply." if rng.random() < 0.5 else "")
        dup["Channel"] = src["Channel"].lower()
        rows.append(dup)
    rng.shuffle(rows)

    with (RAW / "zendesk_export.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with (RAW / "chat_export.json").open("w", encoding="utf-8") as fh:
        json.dump({"exported_at": "2026-10-14T09:00:00Z", "conversations": convos}, fh, ensure_ascii=False, indent=1)
    print(f"wrote {len(rows)} csv rows and {len(convos)} chat conversations to {RAW}")


if __name__ == "__main__":
    main()
