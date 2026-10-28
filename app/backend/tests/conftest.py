from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ccauditor.evidence.collector import collect
from ccauditor.models import EvidenceIndex, Requirement
from ccauditor.policies.loader import load_requirements

FIXTURES = Path(__file__).parent / "fixtures"
POLICIES = FIXTURES / "policies"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A copy of the sample repo plus directories/files the collector must skip."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURES / "sample_repo", dest)
    (dest / "node_modules" / "lib").mkdir(parents=True)
    (dest / "node_modules" / "lib" / "index.js").write_text('console.log("vendored")\n')
    (dest / ".git").mkdir()
    (dest / ".git" / "config").write_text("[core]\n")
    (dest / "big.py").write_text("x = 1\n" * 200_000)  # > 1MB
    (dest / "image.png").write_bytes(b"\x89PNG\r\n\x00\x00binary")
    return dest


@pytest.fixture()
def index(repo: Path) -> EvidenceIndex:
    return collect(repo)


@pytest.fixture()
def requirements() -> list[Requirement]:
    return load_requirements(POLICIES / "test-policy.yaml")


# ------------------------------------------------------------------ live LLM tests (agent B)
# Tests marked @pytest.mark.live call the real Claude Code CLI (developer subscription).
# Skipped by default; run with `pytest -m live --run-live` or `CCAUDITOR_LIVE=1 pytest -m live`.


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="run tests that call the real Claude Code CLI")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls the real Claude Code CLI (skipped unless --run-live)")


def pytest_collection_modifyitems(config, items):
    import os

    if config.getoption("--run-live") or os.environ.get("CCAUDITOR_LIVE") == "1":
        return
    skip = pytest.mark.skip(reason="live LLM test: use --run-live or CCAUDITOR_LIVE=1")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
