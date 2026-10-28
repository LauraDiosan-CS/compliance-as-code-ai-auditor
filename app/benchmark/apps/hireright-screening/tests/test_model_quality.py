"""CI quality gate: the release candidate must meet predefined metrics on the frozen hold-out."""

import json
from pathlib import Path

import pytest

REPORT = Path("artifacts/eval/holdout_report.json")
MIN_AUC = 0.85
MIN_NDCG10 = 0.68


@pytest.fixture(scope="module")
def report():
    return json.loads(REPORT.read_text())


def test_auc_threshold(report):
    assert report["roc_auc"] >= MIN_AUC, f"ROC-AUC {report['roc_auc']:.3f} below gate"


def test_ndcg_threshold(report):
    assert report["ndcg@10"] >= MIN_NDCG10


def test_unranked_rate_is_low(report):
    assert report["unranked_rate"] < 0.06
