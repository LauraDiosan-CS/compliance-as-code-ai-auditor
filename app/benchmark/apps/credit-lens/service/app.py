from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, conint, constr

from .audit import audit_decision, audit_appeal_outcome
from .auth import Principal, require_scope, verify_token
from .queues import appeals_queue, underwriting_queue
from .scoring import ScoringError, scorer
from .settings import settings

app = FastAPI(title="CreditLens", version="3.1.0")


class LoanApplication(BaseModel):
    application_id: constr(pattern=r"^LA-\d{8}$")
    applicant_ref: constr(min_length=16, max_length=64)  # pseudonymous id from origination
    amount_eur: conint(ge=1_000, le=75_000)
    term_months: conint(ge=6, le=120)
    net_monthly_income_eur: float = Field(ge=0, le=100_000)
    monthly_obligations_eur: float = Field(ge=0, le=100_000)
    employment_status: Literal["employed", "self_employed", "retired", "student", "unemployed"]
    months_at_employer: conint(ge=0, le=600)
    bureau_score: conint(ge=0, le=1000)
    open_credit_lines: conint(ge=0, le=100)
    delinquencies_24m: conint(ge=0, le=50)


class Appeal(BaseModel):
    application_id: constr(pattern=r"^LA-\d{8}$")
    applicant_statement: constr(min_length=1, max_length=5000)


@app.post("/v1/score")
def score(app_in: LoanApplication, caller: Principal = Depends(verify_token)):
    if settings.kill_switch or app_in.amount_eur > settings.manual_review_threshold_eur:
        underwriting_queue.put(app_in.application_id, reason="threshold" if not settings.kill_switch else "kill_switch")
        audit_decision(app_in, None, "referred", caller)
        return {"decision": "referred_to_underwriter"}
    try:
        result = scorer.score(app_in)
    except ScoringError:
        # fail-safe: never decline because the model is unavailable
        underwriting_queue.put(app_in.application_id, reason="model_error")
        audit_decision(app_in, None, "referred", caller)
        return {"decision": "referred_to_underwriter"}
    decision = "approve" if result.pd <= settings.pd_cutoff else "decline"
    audit_decision(app_in, result, decision, caller)
    return {"decision": decision, "pd": round(result.pd, 4), "reason_codes": result.reason_codes,
            "model_version": result.model_version}


@app.post("/v1/appeals")
def appeal(body: Appeal, caller: Principal = Depends(verify_token)):
    """Applicant contests a decision: an underwriter re-assesses the full file and can reverse it."""
    ticket = appeals_queue.put(body.application_id, statement=body.applicant_statement)
    return {"ticket": ticket, "sla_days": 5}


class AppealResolution(BaseModel):
    outcome: Literal["upheld", "reversed_to_approve", "reversed_to_counteroffer"]
    underwriter_note: constr(min_length=10, max_length=5000)


@app.post("/v1/appeals/{ticket}/resolution")
def resolve_appeal(ticket: str, body: AppealResolution,
                   caller: Principal = Depends(require_scope("creditlens:underwriter"))):
    """Underwriter's final decision on a contested application; replaces the automated outcome."""
    application_id = appeals_queue.close(ticket, outcome=body.outcome)
    audit_appeal_outcome(application_id, ticket, body.outcome, body.underwriter_note, caller)
    return {"application_id": application_id, "outcome": body.outcome}


@app.post("/v1/admin/thresholds")
def update_cutoff(pd_cutoff: float, caller: Principal = Depends(require_scope("creditlens:admin"))):
    if not 0.01 <= pd_cutoff <= 0.5:
        raise HTTPException(422, "cutoff out of range")
    settings.pd_cutoff = pd_cutoff
    return {"pd_cutoff": pd_cutoff}
