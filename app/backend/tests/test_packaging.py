"""Deployment files stay in sync with the package (Vercel requirements.txt, entrypoint)."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vercel_requirements_match_pyproject():
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    lines = [ln.strip() for ln in (ROOT / "requirements.txt").read_text().splitlines()]
    assert sorted(ln for ln in lines if ln and not ln.startswith("#")) == sorted(deps)


def test_vercel_entrypoint_exports_app():
    import importlib.util

    spec = importlib.util.spec_from_file_location("vercel_index", ROOT / "index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.app.title == "Compliance-as-Code AI Auditor"
