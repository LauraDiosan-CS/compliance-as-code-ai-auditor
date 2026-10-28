from fastapi.testclient import TestClient

from ccauditor.api import app
from ccauditor.policies.loader import load_requirements

from conftest import POLICIES
from helpers import make_report

client = TestClient(app)


def test_health_and_policies():
    assert client.get("/health").json()["status"] == "ok"
    assert isinstance(client.get("/policies").json(), list)
    assert client.get("/policies/does-not-exist").status_code == 404


def test_audit_local_path(repo):
    reqs = load_requirements(POLICIES / "test-policy.yaml")
    body = {"repo_path": str(repo), "policies": ["test-policy"], "mode": "deterministic",
            "requirements": [r.model_dump(mode="json") for r in reqs]}
    res = client.post("/audit", json=body)
    assert res.status_code == 200, res.text
    assert len(res.json()["verdicts"]) == 5


def test_audit_validation():
    assert client.post("/audit", json={"policies": ["x"]}).status_code == 400
    assert client.post("/audit", json={"repo_url": "file:///etc"}).status_code == 400


def test_compare_render_diff(repo, requirements):
    rep = make_report(repo, requirements)
    payload = rep.model_dump(mode="json")
    res = client.post("/reports/compare", json={"baseline": payload, "current": payload})
    assert res.status_code == 200 and res.json()["regressions"] == []
    res = client.post("/reports/render?format=sarif", json=payload)
    assert res.status_code == 200 and res.json()["version"] == "2.1.0"
    res = client.post("/reports/review", json={"report": payload, "reviews": [
        {"requirement_id": "TP-TR-01", "status": "compliant", "reviewer": "bob"}]})
    assert res.status_code == 200
    diff = client.post("/policies/diff", json={
        "old": (POLICIES / "test-policy.md").read_text(),
        "new": (POLICIES / "test-policy-v2.md").read_text(),
        "requirements": [r.model_dump(mode="json") for r in requirements],
    })
    assert diff.status_code == 200
    assert len(diff.json()["modified"]) == 1
