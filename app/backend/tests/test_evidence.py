from ccauditor.evidence.collector import chunk_file, chunk_lines, collect, evidence_id
from ccauditor.evidence.files import classify, read_lines
from ccauditor.evidence.retriever import Retriever, tokenize
from ccauditor.models import EvidenceKind

import pytest


def test_classify():
    assert classify("app/main.py") == EvidenceKind.CODE
    assert classify("web/src/App.tsx") == EvidenceKind.CODE
    assert classify("config/settings.yaml", "a: 1") == EvidenceKind.CONFIG
    assert classify("k8s/deployment.yaml", "apiVersion: v1\nkind: Pod") == EvidenceKind.IAC
    assert classify("deploy/x.yaml", "apiVersion: v1\nkind: Pod") == EvidenceKind.IAC
    assert classify("infra/main.tf") == EvidenceKind.IAC
    assert classify("docker-compose.yml") == EvidenceKind.IAC
    assert classify("charts/api/values.yaml") == EvidenceKind.IAC
    assert classify("Dockerfile") == EvidenceKind.CONFIG
    assert classify(".env.example") == EvidenceKind.CONFIG
    assert classify(".env") is None
    assert classify("README.md") == EvidenceKind.DOC
    assert classify("docs/adr/0001.md") == EvidenceKind.DOC
    assert classify("MODEL_CARD.md") == EvidenceKind.MODEL_CARD
    assert classify("models/fraud.modelcard.md") == EvidenceKind.MODEL_CARD
    assert classify("datasheet_loans.md") == EvidenceKind.MODEL_CARD
    assert classify("logs/audit.jsonl") == EvidenceKind.LOG
    assert classify("server.log") == EvidenceKind.LOG
    assert classify("data/raw.jsonl") is None


def test_collect_skips_and_classifies(index):
    paths = {e.path for e in index.items}
    assert "app/main.py" in paths
    assert "MODEL_CARD.md" in paths
    assert not any(p.startswith(("node_modules", ".git")) for p in paths)
    assert "big.py" not in paths and "image.png" not in paths
    kinds = {e.path: e.kind for e in index.items}
    assert kinds["k8s/deployment.yaml"] == EvidenceKind.IAC
    assert kinds["logs/audit.jsonl"] == EvidenceKind.LOG
    assert index.files_scanned == len(paths)
    main = next(e for e in index.items if e.path == "app/main.py")
    assert "logging_call" in main.signal and "model_call" in main.signal
    assert main.id == evidence_id("app/main.py", main.start_line, main.end_line)


def test_chunking_overlap():
    assert chunk_lines(10) == [(1, 10)]
    windows = chunk_lines(100)
    assert windows[0] == (1, 40) and windows[1] == (31, 70)
    assert windows[-1][1] == 100
    text = "\n".join(f"line {i}" for i in range(1, 101))
    chunks = chunk_file("a.py", EvidenceKind.CODE, text)
    assert len({c.id for c in chunks}) == len(chunks)
    assert chunks[1].snippet.splitlines()[0] == "line 31"


def test_ids_are_stable(repo):
    a = collect(repo)
    b = collect(repo)
    assert [e.id for e in a.items] == [e.id for e in b.items]


def test_tokenize():
    toks = tokenize("auditLogger.logPrediction(user_email)")
    assert {"audit", "logger", "log", "prediction", "user", "email", "user_email"} <= set(toks)


def test_retriever(index):
    r = Retriever(index)
    hits = r.search("logging prediction decision", k=3)
    assert hits and hits[0].path == "app/main.py"
    assert hits[0].score > 0
    docs = r.search("model card training data limitations", kinds=[EvidenceKind.MODEL_CARD])
    assert docs and all(h.kind == EvidenceKind.MODEL_CARD for h in docs)
    assert r.search("") == []
    assert r.get(hits[0].id) is not None


def test_read_lines(repo):
    assert read_lines(repo, "app/main.py", 1, 1) == "import logging"
    with pytest.raises(ValueError):
        read_lines(repo, "../../etc/passwd", 1, 2)
