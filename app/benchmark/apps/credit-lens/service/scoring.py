from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np

MODEL_VERSION = "pd-lgbm-3.1.0"
FEATURES = [
    "amount_eur", "term_months", "net_monthly_income_eur", "monthly_obligations_eur", "dti",
    "employment_status", "months_at_employer", "bureau_score", "open_credit_lines", "delinquencies_24m",
]
REASON_TEXT = {
    "dti": "R01 Debt-to-income ratio too high",
    "bureau_score": "R02 Credit bureau score",
    "delinquencies_24m": "R03 Recent payment delinquencies",
    "months_at_employer": "R04 Length of current employment",
    "open_credit_lines": "R05 Number of open credit lines",
    "net_monthly_income_eur": "R06 Income level",
}


class ScoringError(RuntimeError):
    pass


@dataclass
class ScoreResult:
    pd: float
    reason_codes: list[str]
    model_version: str = MODEL_VERSION


class Scorer:
    def __init__(self, path: str = "models/pd-lgbm-3.1.0.txt") -> None:
        self.booster = lgb.Booster(model_file=path)

    def _row(self, a) -> np.ndarray:
        d = a.model_dump()
        d["dti"] = d["monthly_obligations_eur"] / max(d["net_monthly_income_eur"], 1.0)
        d["employment_status"] = ["employed", "self_employed", "retired", "student", "unemployed"].index(d["employment_status"])
        return np.array([[d[f] for f in FEATURES]], dtype=float)

    def score(self, a) -> ScoreResult:
        try:
            x = self._row(a)
            pd_ = float(self.booster.predict(x)[0])
            contrib = self.booster.predict(x, pred_contrib=True)[0][:-1]  # TreeSHAP contributions
        except Exception as exc:  # noqa: BLE001
            raise ScoringError(str(exc)) from exc
        ranked = sorted(zip(FEATURES, contrib), key=lambda t: t[1], reverse=True)
        codes = [REASON_TEXT[f] for f, c in ranked if c > 0 and f in REASON_TEXT][:4]
        return ScoreResult(pd=pd_, reason_codes=codes)


scorer = Scorer()
