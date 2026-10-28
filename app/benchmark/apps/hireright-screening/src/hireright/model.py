"""Candidate ranker: LightGBM LambdaRank model over CV/requisition features, with explanations."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import shap

from .features import build_features

log = logging.getLogger(__name__)

MODEL_VERSION = "ranker-2.4.1"
# Fields removed before feature extraction: identity and protected characteristics are never
# visible to the model (data minimisation, see DATASHEET.md section 3).
REDACTED_FIELDS = ("name", "email", "phone", "photo", "date_of_birth", "gender", "nationality", "address")


@dataclass
class Ranking:
    score: float | None
    reasons: list[tuple[str, float]]
    model_version: str
    needs_manual_review: bool = False


class Ranker:
    def __init__(self, path: str) -> None:
        self.booster = lgb.Booster(model_file=path)
        self.explainer = shap.TreeExplainer(self.booster)

    @staticmethod
    def redact(cv: dict) -> dict:
        return {k: v for k, v in cv.items() if k not in REDACTED_FIELDS}

    def rank(self, cv: dict, requisition: dict) -> Ranking:
        try:
            x = build_features(self.redact(cv), requisition)
            score = float(self.booster.predict(np.array([x]))[0])
            contrib = self.explainer.shap_values(np.array([x]))[0]
            names = self.booster.feature_name()
            top = sorted(zip(names, contrib), key=lambda t: abs(t[1]), reverse=True)[:5]
            return Ranking(score=score, reasons=[(n, float(c)) for n, c in top], model_version=MODEL_VERSION)
        except Exception:  # noqa: BLE001
            # Fallback: never guess. The application goes to the recruiter queue unranked.
            log.exception("ranker failed; application queued unranked")
            return Ranking(score=None, reasons=[], model_version=MODEL_VERSION, needs_manual_review=True)
