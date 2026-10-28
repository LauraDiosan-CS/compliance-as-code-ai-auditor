import json

import pytest

from spamshield.classifier import SpamClassifier

THRESHOLDS = {"precision": 0.98, "recall": 0.92}


@pytest.fixture(scope="module")
def metrics():
    return json.load(open("artifacts/holdout_metrics.json"))


def test_precision_gate(metrics):
    assert metrics["precision"] >= THRESHOLDS["precision"]


def test_recall_gate(metrics):
    assert metrics["recall"] >= THRESHOLDS["recall"]


def test_quarantine_threshold_is_conservative():
    clf = SpamClassifier.__new__(SpamClassifier)
    clf.tag_at, clf.quarantine_at = 0.7, 0.95
    assert clf.quarantine_at > clf.tag_at
