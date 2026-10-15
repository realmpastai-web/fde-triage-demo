from __future__ import annotations

from pathlib import Path

import pytest

from triage.config import REPO_ROOT, Settings
from triage.pipeline import Pipeline, Service


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        docs_dir=REPO_ROOT / "data" / "docs",
        raw_dir=REPO_ROOT / "data" / "raw",
        golden_path=REPO_ROOT / "data" / "golden" / "golden.jsonl",
        llm_mode="off",
    )


@pytest.fixture
def pipeline(settings: Settings) -> Pipeline:
    return Pipeline.build(settings)


@pytest.fixture
def service(settings: Settings) -> Service:
    return Service.create(settings)
