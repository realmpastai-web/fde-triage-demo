"""Section-level BM25 retrieval over the client's markdown help docs.

No embeddings, no vector DB: the corpus is ~45 sections, BM25 is deterministic, explainable
("these words matched") and has zero infra. Non-English queries are expanded with a small
glossary so a Spanish ticket can still hit the English docs. Swap in embeddings when the
corpus or the query language mix outgrows this; the `Retriever` interface stays the same.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "is",
    "it",
    "my",
    "i",
    "you",
    "your",
    "we",
    "our",
    "be",
    "can",
    "with",
    "this",
    "that",
    "are",
    "was",
    "at",
    "by",
    "if",
    "as",
    "not",
    "do",
    "have",
    "me",
    "what",
    "how",
    "why",
    "from",
    "but",
    "so",
    "up",
    "out",
    "any",
    "no",
    "yes",
    "will",
    "all",
    "its",
    "please",
    "has",
    "had",
    "been",
    "they",
    "them",
    "there",
    "after",
    "than",
    "then",
    "into",
    "us",
    "am",
    "kestrel",
    "still",
    "just",
    "get",
    "got",
    "im",
    "i'm",
    "it's",
    "don't",
    "can't",
    "s",
}

GLOSSARY: dict[str, str] = {
    # es
    "tarjeta": "card",
    "perdí": "lost",
    "robaron": "stolen",
    "bloquear": "freeze",
    "bloquearla": "freeze",
    "transferencia": "transfer",
    "pendiente": "pending",
    "cargo": "payment",
    "fraude": "unauthorised",
    "cuenta": "account",
    "contraseña": "password",
    "bloqueada": "locked",
    "código": "code",
    "verificación": "verification",
    "entrar": "sign",
    "funciona": "declined",
    "tiendas": "merchant",
    # pt
    "cartão": "card",
    "recusado": "declined",
    "taxa": "fee",
    "saque": "atm",
    "caixa": "atm",
    "verificação": "verification",
    "documento": "document",
    "análise": "review",
    "pagamento": "payment",
    # fr
    "virement": "transfer",
    "salaire": "salary",
    "attente": "pending",
    "relevés": "statements",
    "application": "app",
    "plante": "crashes",
    "paiement": "payment",
    "carte": "card",
    "bloqué": "locked",
    "connecter": "sign",
    "compte": "account",
    "essais": "attempts",
    # hi (romanised)
    "kho": "lost",
    "naya": "replacement",
    "paise": "money",
    "otp": "code",
    "documents": "document",
    "kata": "fee",
    "login": "sign",
    # English customer words -> the words the help centre uses
    "block": "freeze",
    "blocked": "freeze",
    "misplaced": "lost",
    "hacked": "unauthorised",
    "scammed": "scam",
}


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[^\W_]+(?:'[^\W_]+)?", text.lower())
    out: list[str] = []
    for w in words:
        if w in GLOSSARY:
            out.append(_stem(GLOSSARY[w]))
        if w not in STOP and not w.isdigit():
            out.append(_stem(w))
    return out


@dataclass
class Section:
    doc_id: str
    title: str
    heading: str
    url: str
    categories: list[str]
    text: str
    tokens: list[str] = field(default_factory=list)


@dataclass
class Hit:
    section: Section
    score: float


def parse_doc(path: Path) -> list[Section]:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    if raw.startswith("---"):
        _, fm, raw = raw.split("---", 2)
        for line in fm.strip().splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    doc_id = meta.get("id", path.stem)
    title = meta.get("title", doc_id)
    cats = [c.strip() for c in meta.get("categories", "").split(",") if c.strip()]
    sections: list[Section] = []
    for block in re.split(r"^## ", raw, flags=re.MULTILINE)[1:]:
        heading, _, body = block.partition("\n")
        body = body.strip()
        s = Section(doc_id, title, heading.strip(), meta.get("url", ""), cats, body)
        # Title and heading words count twice: they say what the section is about.
        s.tokens = tokenize(f"{title} {title} {heading} {heading} {body}")
        sections.append(s)
    return sections


class Retriever:
    def __init__(self, sections: list[Section], k1: float = 1.4, b: float = 0.75) -> None:
        self.sections = sections
        self.k1, self.b = k1, b
        self.avgdl = sum(len(s.tokens) for s in sections) / max(1, len(sections))
        df: Counter[str] = Counter()
        for s in sections:
            df.update(set(s.tokens))
        n = len(sections)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self.tf = [Counter(s.tokens) for s in sections]

    @classmethod
    def from_dir(cls, docs_dir: Path) -> Retriever:
        sections: list[Section] = []
        for p in sorted(docs_dir.glob("*.md")):
            sections.extend(parse_doc(p))
        return cls(sections)

    def search(self, query: str, k: int = 3, category: str | None = None, category_boost: float = 2.0) -> list[Hit]:
        q = set(tokenize(query))  # repeated words in a ticket ("card ... card ... card") shouldn't dominate
        hits: list[Hit] = []
        for s, tf in zip(self.sections, self.tf, strict=True):
            score = 0.0
            dl = len(s.tokens)
            for t in q:
                f = tf.get(t, 0)
                if f:
                    score += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if score and category and category in s.categories:
                score *= category_boost
            if score > 0:
                hits.append(Hit(s, round(score, 3)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def category_votes(self, query: str, k: int = 5) -> dict[str, float]:
        """Score each category by the retrieval mass of its docs. Used as a classifier prior."""
        votes: dict[str, float] = {}
        for h in self.search(query, k=k):
            for c in h.section.categories:
                votes[c] = votes.get(c, 0.0) + h.score / len(h.section.categories)
        return votes
