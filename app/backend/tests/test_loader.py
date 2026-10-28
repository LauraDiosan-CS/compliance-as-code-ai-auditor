from pathlib import Path

import pytest

from ccauditor.models import Category, RiskLevel
from ccauditor.policies.loader import (
    get_policy,
    get_requirements,
    list_builtin_policies,
    load_policy,
    load_requirements,
)

from conftest import POLICIES


def test_load_policy_front_matter_and_clauses():
    p = load_policy(POLICIES / "test-policy.md")
    assert p.id == "test-policy"
    assert p.name == "Test Regulation"
    assert p.version == "1"
    assert p.kind == "regulation"
    ids = [c.id for c in p.clauses]
    assert ids == [
        "test-policy/Art.12",
        "test-policy/Art.12(1)",
        "test-policy/Art.12(2)",
        "test-policy/Art.14",
        "test-policy/Art.14(1)",
        "test-policy/AnnexIII",
        "test-policy/AnnexIII(4)",
        "test-policy/AnnexIII(4)(a)",
    ]
    by_id = {c.id: c for c in p.clauses}
    assert by_id["test-policy/Art.12"].title == "Record-keeping"
    assert "automatic recording" in by_id["test-policy/Art.12"].text
    assert "Preamble" not in by_id["test-policy/Art.12"].text
    assert by_id["test-policy/Art.12(1)"].parent_id == "test-policy/Art.12"
    assert "(logs)" in by_id["test-policy/Art.12(1)"].text
    assert by_id["test-policy/AnnexIII(4)(a)"].parent_id == "test-policy/AnnexIII(4)"
    assert by_id["test-policy/AnnexIII(4)"].parent_id == "test-policy/AnnexIII"


def test_internal_policy_generic_refs():
    p = load_policy(POLICIES / "internal.md")
    assert p.kind == "internal_policy"
    assert [c.id for c in p.clauses] == ["acme-internal/POL-3", "acme-internal/POL-3(a)"]
    assert p.clauses[0].title == "Data retention"


def test_load_requirements():
    reqs = load_requirements(POLICIES / "test-policy.yaml")
    assert [r.id for r in reqs][:2] == ["TP-REC-01", "TP-HO-01"]
    r = reqs[0]
    assert r.policy_id == "test-policy"
    assert r.category == Category.RECORD_KEEPING
    assert r.applies_to == [RiskLevel.HIGH]
    assert r.checks[0].type == "pattern"
    # default applies_to is used when omitted
    assert RiskLevel.MINIMAL in reqs[1].applies_to


def test_builtin_registry(tmp_path: Path):
    pdir, rdir = tmp_path / "p", tmp_path / "r"
    pdir.mkdir()
    rdir.mkdir()
    (pdir / "test-policy.md").write_text((POLICIES / "test-policy.md").read_text())
    (rdir / "anything.yaml").write_text((POLICIES / "test-policy.yaml").read_text())
    items = list_builtin_policies(pdir, rdir)
    assert len(items) == 1 and items[0]["id"] == "test-policy"
    assert items[0]["requirements"] == 5
    assert get_policy("test-policy", pdir).id == "test-policy"
    assert len(get_requirements("test-policy", rdir)) == 5
    assert get_requirements("nope", rdir) == []
    with pytest.raises(KeyError):
        get_policy("nope", pdir)


def test_builtin_listing_does_not_crash():
    assert isinstance(list_builtin_policies(), list)
