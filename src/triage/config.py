"""Client configuration. In a real engagement this is the file you edit with the client's
support lead in discovery; everything downstream reads from here."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CATEGORIES: dict[str, tuple[str, str]] = {
    # category: (owning team, default priority)  -- mirrors data/policies/routing-policy.md
    "fraud_dispute": ("Fraud & Risk", "P2"),
    "account_access": ("Identity & Access", "P2"),
    "card_issue": ("Cards Ops", "P3"),
    "payments_transfer": ("Payments Ops", "P3"),
    "kyc_verification": ("Compliance Ops", "P3"),
    "technical_bug": ("App Engineering", "P3"),
    "billing_fees": ("Billing Ops", "P4"),
    "general_inquiry": ("Tier-1 Support", "P4"),
}
PRIORITIES = ("P1", "P2", "P3", "P4")
TRIAGE_QUEUE_TEAM = "Tier-1 Support"  # where low-confidence tickets go for a human to route
LOW_CONFIDENCE = 0.40


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    docs_dir: Path
    raw_dir: Path
    golden_path: Path
    llm_mode: str  # auto | off | openai | anthropic

    @property
    def db_path(self) -> Path:
        return self.data_dir / "triage.db"

    @property
    def audit_path(self) -> Path:
        return self.data_dir / "audit.jsonl"


def load_settings() -> Settings:
    data_dir = Path(os.environ.get("TRIAGE_DATA_DIR", REPO_ROOT / "var"))
    return Settings(
        data_dir=data_dir,
        docs_dir=Path(os.environ.get("TRIAGE_DOCS_DIR", REPO_ROOT / "data" / "docs")),
        raw_dir=Path(os.environ.get("TRIAGE_RAW_DIR", REPO_ROOT / "data" / "raw")),
        golden_path=Path(os.environ.get("TRIAGE_GOLDEN", REPO_ROOT / "data" / "golden" / "golden.jsonl")),
        llm_mode=os.environ.get("TRIAGE_LLM", "auto").lower(),
    )
