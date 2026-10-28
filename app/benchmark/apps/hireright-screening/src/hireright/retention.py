"""Nightly retention job (CronJob `hireright-retention`, see infra/k8s/deployment.yaml)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import yaml

from .store import candidates, s3


def run(config_path: str = "config/retention.yaml") -> dict[str, int]:
    cfg = yaml.safe_load(open(config_path))
    now = datetime.now(timezone.utc)
    removed = {}
    raw_cutoff = now - timedelta(days=cfg["raw_cv"]["retention_days"])
    removed["raw_cv"] = candidates.delete_raw_documents(older_than=raw_cutoff)
    profile_cutoff = now - timedelta(days=cfg["candidate_profile"]["retention_days"])
    removed["profiles"] = candidates.anonymise_profiles(older_than=profile_cutoff)
    # Journal segments are object-locked; expiry is handled by the bucket lifecycle rule whose
    # value is taken from decision_journal.retention_days at deploy time.
    return removed
