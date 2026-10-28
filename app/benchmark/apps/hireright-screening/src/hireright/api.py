"""HireRight Screening API.

The ranker only orders the recruiter queue. Advancing or rejecting a candidate is always an explicit
recruiter action (POST /applications/{id}/decision). Emotion recognition, video or voice analysis are
deliberately not supported by this product (AI Act Art. 5(1)(f)); only the parsed CV text is used.
"""

from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from .auth import Principal, get_current_recruiter, require_role
from .journal import DecisionJournal, JournalEntry, S3WormSink
from .model import Ranker
from .settings import settings
from .store import applications, candidates, s3

app = FastAPI(title="HireRight Screening", version="2.4.1")
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])
app.state.limiter = limiter

ranker = Ranker(settings.model_path)
journal = DecisionJournal(S3WormSink(s3, settings.journal_bucket))


class ParsedCV(BaseModel):
    skills: list[str] = Field(max_length=200)
    experience_years: float = Field(ge=0, le=60)
    education_level: Literal["none", "secondary", "bachelor", "master", "phd"]
    languages: list[str] = Field(default_factory=list, max_length=20)
    summary: str = Field(default="", max_length=8000)


class ScoreRequest(BaseModel):
    requisition_id: str = Field(pattern=r"^REQ-\d{6}$")
    cv: ParsedCV


class RecruiterDecision(BaseModel):
    outcome: Literal["advance", "reject", "hold"]
    reason: str = Field(min_length=10, max_length=2000)


class Override(BaseModel):
    new_rank_bucket: Literal["top", "middle", "bottom"]
    justification: str = Field(min_length=10, max_length=2000)


@app.post("/applications/{application_id}/score")
def score(application_id: str, body: ScoreRequest, user: Principal = Depends(get_current_recruiter)):
    if not settings.automated_ranking_enabled:
        applications.mark_unranked(application_id)
        return {"status": "queued_for_manual_review", "reason": "automated ranking suspended"}
    r = ranker.rank(body.cv.model_dump(), {"id": body.requisition_id})
    journal.record(JournalEntry(
        event="ranked", application_id=application_id, requisition_id=body.requisition_id,
        model_version=r.model_version, input_digest=DecisionJournal.digest(body.model_dump()),
        result={"score": r.score, "reasons": r.reasons, "manual": r.needs_manual_review}, actor=user.id,
    ))
    applications.save_ranking(application_id, r)
    return {"score": r.score, "reasons": r.reasons, "model_version": r.model_version,
            "needs_manual_review": r.needs_manual_review}


@app.post("/applications/{application_id}/decision")
def decide(application_id: str, body: RecruiterDecision, user: Principal = Depends(get_current_recruiter)):
    """The only way a candidate's status changes. Requires a human recruiter."""
    journal.record(JournalEntry(event="reviewer_decision", application_id=application_id,
                                result=body.model_dump(), actor=user.id))
    applications.set_status(application_id, body.outcome, decided_by=user.id)
    return {"ok": True}


@app.post("/applications/{application_id}/override")
def override_ranking(application_id: str, body: Override, user: Principal = Depends(get_current_recruiter)):
    """Recruiters may disregard the AI ranking and move the application to another bucket."""
    journal.record(JournalEntry(event="override", application_id=application_id,
                                result=body.model_dump(), actor=user.id))
    applications.set_bucket(application_id, body.new_rank_bucket)
    return {"ok": True}


@app.post("/admin/ranking/suspend")
def suspend_automated_ranking(user: Principal = Depends(require_role("screening-admin"))):
    """Stops all automated ranking immediately; new applications go to the manual queue."""
    settings.automated_ranking_enabled = False
    journal.record(JournalEntry(event="suspended", application_id="*", actor=user.id))
    return {"automated_ranking_enabled": False}


@app.post("/admin/ranking/resume")
def resume_automated_ranking(user: Principal = Depends(require_role("screening-admin"))):
    settings.automated_ranking_enabled = True
    journal.record(JournalEntry(event="resumed", application_id="*", actor=user.id))
    return {"automated_ranking_enabled": True}


@app.delete("/candidates/{candidate_id}")
def erase_candidate_data(candidate_id: str, user: Principal = Depends(require_role("privacy-officer"))):
    """GDPR Art. 17 request: delete CV, parsed profile and rankings. Journal keeps only digests."""
    if not candidates.exists(candidate_id):
        raise HTTPException(404)
    candidates.delete_everywhere(candidate_id)
    return {"erased": candidate_id}
