"""Shared data contracts for the Compliance-as-Code AI Auditor.

Every pipeline stage (ingestion -> decomposition -> evidence -> evaluation -> report)
exchanges these models. Keep them stable: the CLI, API, web UI and benchmark all depend on them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    PROHIBITED = "prohibited"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"
    UNKNOWN = "unknown"


class Category(str, Enum):
    RISK_CLASSIFICATION = "risk_classification"
    TRANSPARENCY = "transparency"
    RECORD_KEEPING = "record_keeping"
    HUMAN_OVERSIGHT = "human_oversight"
    DATA_GOVERNANCE = "data_governance"
    TECHNICAL_DOCUMENTATION = "technical_documentation"
    ACCURACY_ROBUSTNESS = "accuracy_robustness"
    SECURITY = "security"
    DATA_RETENTION = "data_retention"
    OTHER = "other"


class Status(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NEEDS_REVIEW = "needs_review"  # borderline -> human-in-the-loop
    NOT_APPLICABLE = "not_applicable"


class EvidenceKind(str, Enum):
    CODE = "code"
    CONFIG = "config"
    IAC = "iac"  # terraform, kubernetes, docker-compose
    DOC = "doc"  # README, ADR, architecture docs
    MODEL_CARD = "model_card"  # model cards, data sheets
    LOG = "log"


# ---------------------------------------------------------------- policy side


class Clause(BaseModel):
    """A citable unit of the source policy (article / paragraph / bullet)."""

    id: str  # e.g. "EU-AI-ACT/Art.12(1)"
    policy_id: str
    title: str = ""
    text: str
    parent_id: str | None = None


class Policy(BaseModel):
    id: str  # e.g. "eu-ai-act"
    name: str
    version: str = "1"
    source: str = ""  # url or file path
    kind: Literal["regulation", "internal_policy", "control_framework"] = "regulation"
    clauses: list[Clause] = Field(default_factory=list)


class RuleCheck(BaseModel):
    """One deterministic check. Interpreted by ccauditor.rules.engine.

    type:
      - "pattern": regex `pattern` must (expect="present") / must not (expect="absent")
        match in files selected by `globs` and/or evidence `kinds`.
      - "file_exists": at least one file matching `globs` exists.
      - "yaml_path": a key path (dot notation in `path`) exists / equals `equals` in YAML/JSON files from `globs`.
      - "rego": evaluate `rego` policy with OPA if installed (skipped -> needs_review otherwise).
    """

    type: Literal["pattern", "file_exists", "yaml_path", "rego"]
    description: str = ""
    globs: list[str] = Field(default_factory=list)
    kinds: list[EvidenceKind] = Field(default_factory=list)
    pattern: str | None = None
    path: str | None = None
    equals: Any = None
    rego: str | None = None
    expect: Literal["present", "absent"] = "present"


class Requirement(BaseModel):
    """A verifiable requirement derived from one or more clauses."""

    id: str  # e.g. "AIA-REC-01"
    policy_id: str
    clause_ids: list[str]
    category: Category
    title: str
    statement: str  # normative, testable statement
    applies_to: list[RiskLevel] = Field(
        default_factory=lambda: [RiskLevel.HIGH, RiskLevel.LIMITED, RiskLevel.MINIMAL]
    )
    checks: list[RuleCheck] = Field(default_factory=list)  # deterministic part
    llm_guidance: str = ""  # what the LLM judge should look for (ambiguous parts)
    evidence_queries: list[str] = Field(default_factory=list)  # retrieval keywords
    severity: Literal["critical", "high", "medium", "low"] = "medium"


# ---------------------------------------------------------------- evidence side


class Evidence(BaseModel):
    id: str  # stable hash of path+lines
    kind: EvidenceKind
    path: str  # relative to target repo root
    start_line: int
    end_line: int
    snippet: str
    signal: str = ""  # which collector/signal produced it, e.g. "logging_call"
    score: float = 0.0


class EvidenceIndex(BaseModel):
    repo_root: str
    files_scanned: int
    items: list[Evidence]


# ---------------------------------------------------------------- verdicts & report


class Verdict(BaseModel):
    requirement_id: str
    status: Status
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)  # must reference real Evidence.id
    gaps: list[str] = Field(default_factory=list)
    remediation: str = ""
    method: Literal["deterministic", "llm", "hybrid", "human"] = "deterministic"
    verified: bool = False  # citations checked by the Verifier agent


class RiskAssessment(BaseModel):
    level: RiskLevel
    rationale: str
    triggers: list[str] = Field(default_factory=list)  # e.g. "Annex III 4(a): recruitment"
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class CategoryScore(BaseModel):
    category: Category
    total: int
    compliant: int
    partial: int
    non_compliant: int
    needs_review: int
    score: float  # 0..100


class AuditReport(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target: str  # repo path / name
    policies: list[str]
    mode: Literal["deterministic", "llm", "hybrid"]
    risk: RiskAssessment | None = None
    requirements: list[Requirement]
    verdicts: list[Verdict]
    evidence: list[Evidence]  # only items cited by verdicts
    scorecard: list[CategoryScore] = Field(default_factory=list)
    overall_score: float = 0.0
    stats: dict[str, Any] = Field(default_factory=dict)  # timings, llm calls, tokens, cost
