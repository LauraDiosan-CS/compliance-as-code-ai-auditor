"""Walk a repository and turn it into an EvidenceIndex of line-window chunks tagged with signals."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ccauditor.evidence.files import classify, iter_repo_files, read_text
from ccauditor.models import Evidence, EvidenceIndex, EvidenceKind

CHUNK_LINES = 40
CHUNK_OVERLAP = 10
SMALL_FILE_LINES = 50  # files up to this many lines become a single chunk

# Lightweight regex detectors. A chunk may carry several signals (comma-separated in Evidence.signal).
SIGNALS: dict[str, re.Pattern[str]] = {
    "logging_call": re.compile(
        r"\b(logger|logging|log)\.(info|warn|warning|error|debug|exception|critical)\s*\(|"
        r"\baudit_?log|\bconsole\.(log|info|warn|error)\s*\(|structlog|winston|log4j|slf4j",
        re.IGNORECASE,
    ),
    "ai_disclosure": re.compile(
        r"(generated|produced|powered)\s+by\s+(an?\s+)?(ai|artificial intelligence|model|llm)|"
        r"you are (talking|chatting|interacting) (to|with) (an? )?(ai|bot|assistant)|"
        r"ai[-_ ]?disclosure|ai[-_ ]generated|disclose.*\bai\b|\bis_ai_generated\b|watermark",
        re.IGNORECASE,
    ),
    "human_override": re.compile(
        r"human[-_ ]?(in[-_ ]the[-_ ]loop|review|oversight|override|approval)|manual[-_ ]?review|"
        r"\boverride\b|\bescalat\w*|requires?_review|approve[d]?_by|reviewer",
        re.IGNORECASE,
    ),
    "retention_config": re.compile(
        r"retention|ttl\b|time[-_]to[-_]live|expire|expiry|max[-_]?age|purge|delete[-_]after|"
        r"data[-_]?lifecycle|lifecycle_rule",
        re.IGNORECASE,
    ),
    "pii_field": re.compile(
        r"\b(email|phone|ssn|social_security|passport|date_of_birth|dob|birth_?date|address|"
        r"first_?name|last_?name|full_?name|national_id|iban|credit_card|gender|ethnicity|religion|"
        r"health|biometric|ip_address)\b",
        re.IGNORECASE,
    ),
    "model_call": re.compile(
        r"\.predict(_proba)?\s*\(|\bmodel\.(generate|forward|infer)|openai|anthropic|"
        r"chat\.completions|messages\.create|transformers|pipeline\(|inference|\bllm\b|"
        r"sklearn|torch|tensorflow|xgboost|huggingface",
        re.IGNORECASE,
    ),
    "consent": re.compile(r"consent|opt[-_ ]?(in|out)|gdpr|lawful[-_ ]basis|cookie[-_ ]banner", re.IGNORECASE),
    "encryption": re.compile(
        r"encrypt|decrypt|\bkms\b|\baes\b|\btls\b|\bssl\b|https|bcrypt|argon2|hashlib|fernet|"
        r"server_side_encryption|at[-_ ]rest",
        re.IGNORECASE,
    ),
    "access_control": re.compile(
        r"\brbac\b|role[-_ ]?based|permission|authoriz|authenticat|\bauth\b|jwt|oauth|"
        r"\biam\b|access[-_ ]control|requires?_role|is_admin|login_required|Depends\(.*user",
        re.IGNORECASE,
    ),
    "rate_limit": re.compile(r"rate[-_ ]?limit|throttl|slowapi|limiter", re.IGNORECASE),
    "data_documentation": re.compile(
        r"datasheet|data[-_ ]?card|model[-_ ]?card|training data|data provenance|"
        r"data (source|collection|lineage)|dataset|intended use|limitations",
        re.IGNORECASE,
    ),
    "bias_fairness": re.compile(r"\bbias\b|fairness|disparate|demographic parity|equal opportunity", re.IGNORECASE),
    "accuracy_metrics": re.compile(
        r"\baccuracy\b|precision|recall|f1[-_ ]?score|\bauc\b|roc_auc|confusion_matrix|evaluation metric",
        re.IGNORECASE,
    ),
    "risk_management": re.compile(r"risk[-_ ]?(assessment|management|register|mitigation)", re.IGNORECASE),
    "monitoring": re.compile(r"monitor|prometheus|grafana|opentelemetry|sentry|drift|alerting", re.IGNORECASE),
    "anonymization": re.compile(r"anonymi[sz]|pseudonymi[sz]|mask(ing)?_?pii|redact|hash_pii", re.IGNORECASE),
}


def evidence_id(path: str, start: int, end: int) -> str:
    return hashlib.sha1(f"{path}:{start}-{end}".encode()).hexdigest()[:12]


def detect_signals(text: str) -> list[str]:
    return [name for name, rx in SIGNALS.items() if rx.search(text)]


def chunk_lines(n_lines: int, size: int = CHUNK_LINES, overlap: int = CHUNK_OVERLAP) -> list[tuple[int, int]]:
    """1-based inclusive (start, end) windows covering n_lines."""
    if n_lines <= 0:
        return []
    if n_lines <= max(size, SMALL_FILE_LINES):
        return [(1, n_lines)]
    step = max(1, size - overlap)
    windows: list[tuple[int, int]] = []
    start = 1
    while True:
        end = min(n_lines, start + size - 1)
        windows.append((start, end))
        if end >= n_lines:
            break
        start += step
    return windows


def chunk_file(rel_path: str, kind: EvidenceKind, text: str) -> list[Evidence]:
    lines = text.splitlines()
    out: list[Evidence] = []
    for start, end in chunk_lines(len(lines)):
        snippet = "\n".join(lines[start - 1 : end])
        if not snippet.strip():
            continue
        out.append(
            Evidence(
                id=evidence_id(rel_path, start, end),
                kind=kind,
                path=rel_path,
                start_line=start,
                end_line=end,
                snippet=snippet,
                signal=",".join(detect_signals(snippet)),
            )
        )
    return out


def collect(repo_root: str | Path, exclude: list[str] | None = None) -> EvidenceIndex:
    """Scan repo_root and build the evidence index."""
    root = Path(repo_root).resolve()
    items: list[Evidence] = []
    files = 0
    for p in iter_repo_files(root, exclude):
        rel = p.relative_to(root).as_posix()
        text = read_text(p)
        kind = classify(rel, text)
        if kind is None:
            continue
        files += 1
        items.extend(chunk_file(rel, kind, text))
    return EvidenceIndex(repo_root=str(root), files_scanned=files, items=items)


def chunks_for_file(index: EvidenceIndex, path: str) -> list[Evidence]:
    return sorted((e for e in index.items if e.path == path), key=lambda e: e.start_line)


def chunk_for_line(index: EvidenceIndex, path: str, line: int) -> Evidence | None:
    """Smallest-start chunk of `path` whose window contains `line` (best-centred if several)."""
    best: Evidence | None = None
    best_margin = -1
    for e in index.items:
        if e.path == path and e.start_line <= line <= e.end_line:
            margin = min(line - e.start_line, e.end_line - line)
            if margin > best_margin:
                best, best_margin = e, margin
    return best
