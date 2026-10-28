import json

REPORT = json.load(open("artifacts/oot_report.json"))


def test_auc_gate():
    assert REPORT["roc_auc"] >= 0.78


def test_gini_gate():
    assert REPORT["gini"] >= 0.56


def test_psi_stable():
    assert REPORT["psi_score"] < 0.1
