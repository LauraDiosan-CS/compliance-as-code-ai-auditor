"""Audit trail of every credit decision (shipped to CloudWatch log group /creditlens/audit)."""

import hashlib
import json
import logging

audit_logger = logging.getLogger("creditlens.audit")


def audit_decision(app_in, result, decision, caller):
    payload = app_in.model_dump()
    audit_logger.info("credit decision %s", decision, extra={
        "application_id": app_in.application_id,
        "input_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        "pd": None if result is None else result.pd,
        "reason_codes": None if result is None else result.reason_codes,
        "model_version": None if result is None else result.model_version,
        "caller": caller.client_id,
    })


def audit_appeal_outcome(application_id, ticket, outcome, note, caller):
    audit_logger.info(
        "appeal resolved %s",
        outcome,
        extra={"application_id": application_id, "ticket": ticket, "note": note, "underwriter": caller.client_id},
    )
