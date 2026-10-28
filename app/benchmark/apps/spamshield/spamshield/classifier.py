from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import joblib

MODEL_VERSION = "nb-2026.10"
URL = re.compile(r"https?://\S+")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


@dataclass
class Verdict:
    action: str  # deliver | tag | quarantine
    spam_probability: float
    model_version: str = MODEL_VERSION


def normalise(subject: str, body: str) -> str:
    """Reduce the message to what the model needs; addresses become placeholders."""
    text = f"{subject}\n{body[:20000]}"
    text = URL.sub(" URLTOKEN ", text)
    return EMAIL.sub(" EMAILTOKEN ", text).lower()


def message_ref(message_id: str) -> str:
    return hashlib.sha256(message_id.encode()).hexdigest()[:24]


class SpamClassifier:
    def __init__(self, path: str, tag_at: float, quarantine_at: float) -> None:
        self.pipeline = joblib.load(path)
        self.tag_at, self.quarantine_at = tag_at, quarantine_at

    def classify(self, subject: str, body: str) -> Verdict:
        p = float(self.pipeline.predict_proba([normalise(subject, body)])[0][1])
        if p >= self.quarantine_at:
            return Verdict("quarantine", p)
        if p >= self.tag_at:
            return Verdict("tag", p)
        return Verdict("deliver", p)
