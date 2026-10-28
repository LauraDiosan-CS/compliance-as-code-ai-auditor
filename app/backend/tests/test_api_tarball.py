"""api.py fallback for hosts without git (Vercel): audit a GitHub repo from its codeload tarball."""

import io
import tarfile
from contextlib import contextmanager

import httpx
from fastapi.testclient import TestClient

from ccauditor import api
from ccauditor.policies.loader import load_requirements

from conftest import FIXTURES, POLICIES

client = TestClient(api.app)


def _tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(FIXTURES / "sample_repo", arcname="sample-repo-abc123")
        evil = tarfile.TarInfo("../escape.txt")
        data = b"should never be written"
        evil.size = len(data)
        tar.addfile(evil, io.BytesIO(data))
        link = tarfile.TarInfo("sample-repo-abc123/passwd")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        tar.addfile(link)
    return buf.getvalue()


class _Resp:
    def __init__(self, status: int, body: bytes):
        self.status_code, self._body = status, body

    def iter_bytes(self):
        yield from (self._body[i:i + 4096] for i in range(0, len(self._body), 4096))


def test_github_tarball_url():
    assert api._github_tarball_url("https://github.com/pallets/itsdangerous") == \
        "https://codeload.github.com/pallets/itsdangerous/tar.gz/HEAD"
    assert api._github_tarball_url("https://github.com/a/b.git/").endswith("/a/b/tar.gz/HEAD")
    assert api._github_tarball_url("https://gitlab.com/a/b") is None


def test_audit_without_git_uses_tarball(monkeypatch, tmp_path):
    body = _tarball()
    requested: list[str] = []

    @contextmanager
    def fake_stream(method, url, **kw):
        requested.append(url)
        yield _Resp(200, body)

    monkeypatch.setattr(api.shutil, "which", lambda name: None)
    monkeypatch.setattr(httpx, "stream", fake_stream)
    reqs = load_requirements(POLICIES / "test-policy.yaml")
    res = client.post("/audit", json={
        "repo_url": "https://github.com/acme/sample-repo", "policies": ["test-policy"], "mode": "deterministic",
        "requirements": [r.model_dump(mode="json") for r in reqs],
    })
    assert res.status_code == 200, res.text
    assert requested == ["https://codeload.github.com/acme/sample-repo/tar.gz/HEAD"]
    report = res.json()
    assert report["target"] == "https://github.com/acme/sample-repo"
    assert len(report["verdicts"]) == 5
    paths = {e["path"] for e in report["evidence"]}
    assert "app/main.py" in paths and not any("passwd" in p or "escape" in p for p in paths)


def test_tarball_fallback_errors(monkeypatch):
    @contextmanager
    def not_found(method, url, **kw):
        yield _Resp(404, b"")

    monkeypatch.setattr(api.shutil, "which", lambda name: None)
    monkeypatch.setattr(httpx, "stream", not_found)
    res = client.post("/audit", json={"repo_url": "https://github.com/acme/missing", "mode": "deterministic"})
    assert res.status_code == 400 and "HTTP 404" in res.json()["detail"]
    res = client.post("/audit", json={"repo_url": "https://gitlab.com/acme/repo", "mode": "deterministic"})
    assert res.status_code == 400 and "github.com" in res.json()["detail"]


def test_serverless_forces_deterministic(monkeypatch):
    monkeypatch.setattr(api, "ALLOW_LLM", False)
    assert api.effective_mode("hybrid") == "deterministic"
    assert api.effective_mode(None) == "deterministic"
    monkeypatch.setattr(api, "ALLOW_LLM", True)
    assert api.effective_mode("llm") == "llm"


def test_serverless_env_detection(monkeypatch):
    import importlib

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("CCAUDITOR_ALLOW_LLM", raising=False)
    mod = importlib.reload(api)
    try:
        assert mod.SERVERLESS and mod.DEFAULT_MODE == "deterministic" and not mod.ALLOW_LLM
        assert TestClient(mod.app).get("/health").json()["llm_enabled"] is False
    finally:
        monkeypatch.delenv("VERCEL")
        importlib.reload(api)
