"""Cheap, deterministic language and urgency detection. Good enough to route and to flag
tickets for translation review; not a general-purpose language identifier."""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

STOPWORDS: dict[str, set[str]] = {
    "en": {
        "the",
        "and",
        "my",
        "is",
        "it",
        "to",
        "i",
        "a",
        "of",
        "for",
        "in",
        "on",
        "you",
        "not",
        "can",
        "what",
        "have",
        "was",
        "this",
        "me",
        "with",
        "but",
        "please",
        "why",
        "how",
        "do",
        "still",
    },
    "es": {
        "el",
        "la",
        "de",
        "que",
        "y",
        "mi",
        "es",
        "no",
        "un",
        "una",
        "por",
        "favor",
        "para",
        "con",
        "hace",
        "sigue",
        "pueden",
        "cuenta",
        "tarjeta",
        "yo",
        "hay",
        "puedo",
        "llega",
        "cómo",
        "esta",
    },
    "pt": {
        "o",
        "a",
        "de",
        "que",
        "e",
        "meu",
        "minha",
        "não",
        "um",
        "uma",
        "foi",
        "está",
        "tenho",
        "há",
        "eu",
        "ainda",
        "fiz",
        "comigo",
        "cartão",
        "podem",
        "seu",
        "também",
    },
    "fr": {
        "le",
        "la",
        "les",
        "de",
        "et",
        "mon",
        "ma",
        "mes",
        "est",
        "je",
        "pas",
        "un",
        "une",
        "que",
        "sur",
        "à",
        "été",
        "fois",
        "avec",
        "toujours",
        "depuis",
        "c",
        "n",
        "ai",
        "j",
    },
    "hi": {
        "hai",
        "nahi",
        "mera",
        "meri",
        "kya",
        "kar",
        "ho",
        "raha",
        "rahi",
        "maine",
        "tha",
        "lekin",
        "abhi",
        "tak",
        "paise",
        "kyu",
        "kyun",
        "kijiye",
        "dijiye",
        "aur",
        "bahut",
        "jaldi",
        "gaya",
        "pehle",
        "din",
        "kiye",
        "karu",
    },
}

URGENT_TERMS = [
    "urgent",
    "urgently",
    "asap",
    "immediately",
    "emergency",
    "right now",
    "tonight",
    "today",
    "rent",
    "salary",
    "payroll",
    "late fee",
    "threatening",
    "help",
    "stolen",
    "hacked",
    "fraud",
    "didn't do this",
    "did not do this",
    "gave them a code",
    "urgente",
    "ayuda",
    "ayúdenme",
    "jaldi",
    "c'est urgent",
]


def detect_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return "en"
    scores = {lang: sum(1 for w in words if w in sw) for lang, sw in STOPWORDS.items()}
    # Accented characters are strong hints for es/pt/fr.
    if re.search(r"[ñ¿¡]", text):
        scores["es"] += 2
    if re.search(r"[ãõç]", text):
        scores["pt"] += 2
    if re.search(r"[èêàùœ]", text):
        scores["fr"] += 2
    best = max(scores, key=lambda k: scores[k])
    # English is the tie-break default: most tickets are English and "the"/"a" overlap.
    if scores[best] <= scores["en"] or scores[best] < 2:
        return "en"
    return best


@dataclass
class Urgency:
    level: str  # low | medium | high
    signals: list[str]


def detect_urgency(text: str) -> Urgency:
    low = text.lower()
    signals = [t for t in URGENT_TERMS if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", low)]
    if re.search(r"!{2,}", text):
        signals.append("exclamations")
    letters = [c for c in text if c.isalpha()]
    if len(letters) > 20 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        signals.append("all_caps")
    elif re.search(r"\b[A-Z]{4,}\b", text) and not re.search(r"\b(?:ATM|USD|EUR|IBAN|CSV|SMS|PDF|OTP|KYC)\b", text):
        signals.append("shouting")
    level = "high" if len(signals) >= 2 else "medium" if signals else "low"
    return Urgency(level, signals)
