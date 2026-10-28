"""RiskClassifier: EU AI Act risk tier of the audited application.

Tiers: prohibited (Art. 5), high (Art. 6 + Annex III), limited (Art. 50 transparency), minimal.
A deterministic keyword pre-classifier works offline and is fed to the LLM as a hint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..llm.backend import LLMBackend
from ..models import Evidence, EvidenceIndex, EvidenceKind, RiskAssessment, RiskLevel
from .common import clamp01, coerce_risk, make_aliases, render_evidence, resolve_ids, str_list


@dataclass(frozen=True)
class Trigger:
    level: RiskLevel
    label: str
    pattern: str
    code_ok: bool = False  # whether matches in code (not only docs) count


TRIGGERS: list[Trigger] = [
    # ---- Art. 5 prohibited practices
    Trigger(RiskLevel.PROHIBITED, "Art. 5(1)(c): social scoring",
            r"social[\s_-]?scor(e|ing)|social credit|citizen scor(e|ing)|trustworthiness scor(e|ing)"),
    Trigger(RiskLevel.PROHIBITED, "Art. 5(1)(a): subliminal / manipulative techniques",
            r"subliminal|manipulat\w* (users|behaviou?r|vulnerab)|dark pattern"),
    Trigger(RiskLevel.PROHIBITED, "Art. 5(1)(f): emotion recognition at the workplace or in education",
            r"emotion (recognition|detection)\W+(\w+\W+){0,8}(employee|workplace|worker|student|classroom|school)|"
            r"(employee|workplace|worker|student|classroom)\W+(\w+\W+){0,8}emotion (recognition|detection)"),
    Trigger(RiskLevel.PROHIBITED, "Art. 5(1)(e): untargeted scraping of facial images",
            r"scrap\w+ (of )?(facial|face) images|face (database|images) (from|scraped).{0,20}(internet|cctv)"),
    Trigger(RiskLevel.PROHIBITED, "Art. 5(1)(d): predictive policing based on profiling",
            r"predict\w* (crime|criminal|offen[cs]e|recidivism)|crime prediction|predictive policing"),
    Trigger(RiskLevel.PROHIBITED, "Art. 5(1)(h): real-time remote biometric identification in public spaces",
            r"real[\s-]?time (remote )?(biometric|facial|face) (identification|recognition)\W+(\w+\W+){0,8}public"),
    # ---- Annex III high-risk areas
    Trigger(RiskLevel.HIGH, "Annex III 1: biometric identification / categorisation",
            r"biometric|facial recognition|face recognition|face (matching|verification)|fingerprint|voiceprint"),
    Trigger(RiskLevel.HIGH, "Annex III 2: critical infrastructure",
            r"critical infrastructure|power grid|electricity (grid|supply)|water supply|gas supply|traffic (control|management)|scada"),
    Trigger(RiskLevel.HIGH, "Annex III 3: education and vocational training",
            r"(exam|examination|test)[\s_-]?(scor|grad|proctor)\w*|student (admission|assessment|grading)|admissions? (decision|screening)|proctoring|grade (essays|students)"),
    Trigger(RiskLevel.HIGH, "Annex III 4: employment / recruitment",
            r"recruit\w*|hiring|job (applicant|candidate)s?|candidate (screening|ranking|scoring)|r[ée]sum[ée] (screening|parsing|ranking)|\bcv (screening|parsing|ranking)|applicant tracking|promotion decision|employee (evaluation|monitoring)"),
    Trigger(RiskLevel.HIGH, "Annex III 5(b): creditworthiness / credit scoring",
            r"credit[\s_-]?(scor\w*|worthiness)|loan (approval|default|eligibility|application)|creditworth\w*"),
    Trigger(RiskLevel.HIGH, "Annex III 5(c): life and health insurance pricing",
            r"(life|health) insurance (pricing|premium|risk)|insurance underwriting"),
    Trigger(RiskLevel.HIGH, "Annex III 5(a): eligibility for public benefits / essential services",
            r"(public|social|welfare) benefits? (eligibility|allocation)|emergency (call|dispatch) (triage|priorit)"),
    Trigger(RiskLevel.HIGH, "Annex III 6: law enforcement",
            r"law enforcement|police|polygraph|evidence reliability|criminal investigation"),
    Trigger(RiskLevel.HIGH, "Annex III 7: migration, asylum and border control",
            r"asylum|visa application|border control|migration (risk|assessment)"),
    Trigger(RiskLevel.HIGH, "Annex III 8: administration of justice / elections",
            r"judicial (decision|authority)|court ruling|sentencing|influence (the )?(election|voting)"),
    # ---- Art. 50 transparency (limited)
    Trigger(RiskLevel.LIMITED, "Art. 50(1): chatbot / conversational AI interacting with people",
            r"chat[\s_-]?bot|conversational (agent|assistant|ai)|virtual assistant|customer support (bot|assistant)|chat (completion|assistant)",
            code_ok=True),
    Trigger(RiskLevel.LIMITED, "Art. 50(2): generative AI producing synthetic content",
            r"generative ai|text generation|image generation|llm\b|large language model|gpt-?\d|stable[\s_-]?diffusion|"
            r"openai\.|anthropic\.|chat\.completions|messages\.create|text-to-image",
            code_ok=True),
    Trigger(RiskLevel.LIMITED, "Art. 50(4): deep fakes",
            r"deep[\s_-]?fake|face[\s_-]?swap|voice clon\w*|synthetic (video|voice|media)"),
    Trigger(RiskLevel.LIMITED, "Art. 50(3): emotion recognition / biometric categorisation (disclosure)",
            r"emotion (recognition|detection)|sentiment from (face|voice)"),
]

_ORDER = [RiskLevel.PROHIBITED, RiskLevel.HIGH, RiskLevel.LIMITED, RiskLevel.MINIMAL]
DOC_KINDS = {EvidenceKind.DOC, EvidenceKind.MODEL_CARD}


def heuristic_classify(index: EvidenceIndex | list[Evidence]) -> RiskAssessment:
    """Deterministic keyword classification over docs/model cards (and some code signals)."""
    items = index.items if isinstance(index, EvidenceIndex) else list(index)
    hits: dict[str, list[str]] = {}
    level_of: dict[str, RiskLevel] = {}
    for trig in TRIGGERS:
        rx = re.compile(trig.pattern, re.IGNORECASE)
        for ev in items:
            if ev.kind not in DOC_KINDS and not trig.code_ok:
                continue
            if rx.search(ev.snippet) or (ev.kind in DOC_KINDS and rx.search(ev.path.replace("_", " "))):
                ids = hits.setdefault(trig.label, [])
                if ev.id not in ids and len(ids) < 3:
                    ids.append(ev.id)
                level_of[trig.label] = trig.level
    if not hits:
        has_docs = any(ev.kind in DOC_KINDS for ev in items)
        return RiskAssessment(
            level=RiskLevel.MINIMAL if has_docs else RiskLevel.UNKNOWN,
            rationale=("No prohibited-practice, Annex III or Art. 50 indicators found in documentation."
                       if has_docs else "No documentation found; risk level cannot be determined heuristically."),
            confidence=0.5 if has_docs else 0.2,
        )
    level = next(lv for lv in _ORDER if lv in level_of.values())
    triggers = [lab for lab, lv in level_of.items() if lv == level]
    others = [lab for lab, lv in level_of.items() if lv != level]
    ev_ids: list[str] = []
    for lab in triggers:
        for i in hits[lab]:
            if i not in ev_ids:
                ev_ids.append(i)
    n = sum(len(hits[lab]) for lab in triggers)
    conf = {RiskLevel.PROHIBITED: 0.55, RiskLevel.HIGH: 0.6, RiskLevel.LIMITED: 0.6}.get(level, 0.5)
    conf = min(0.85, conf + 0.05 * (n - 1))
    rationale = f"Keyword pre-classifier: {level.value} because of " + "; ".join(triggers) + "."
    if others:
        rationale += " Other indicators: " + "; ".join(others) + "."
    return RiskAssessment(level=level, rationale=rationale, triggers=triggers + others,
                          evidence_ids=ev_ids[:8], confidence=round(conf, 2))


RISK_SYSTEM = """You are RiskClassifier, an expert on the EU AI Act (Regulation (EU) 2024/1689).
Classify the AI system described by the repository excerpts into exactly one risk tier:
- "prohibited": an Art. 5 practice (manipulative/subliminal techniques, exploiting vulnerabilities, social scoring,
  predictive policing based solely on profiling, untargeted facial-image scraping, emotion recognition at work or in
  education, biometric categorisation inferring sensitive traits, real-time remote biometric identification in public
  spaces for law enforcement).
- "high": Art. 6 / Annex III use (biometrics; critical infrastructure; education & vocational training; employment,
  recruitment & worker management; access to essential private/public services incl. credit scoring and life/health
  insurance; law enforcement; migration/asylum/border control; administration of justice & democratic processes),
  or a safety component of an Annex I product.
- "limited": not high-risk but subject to Art. 50 transparency duties (chatbots interacting with people, generative AI
  producing synthetic content, deep fakes, emotion recognition/biometric categorisation disclosure).
- "minimal": none of the above.
Use "unknown" only if the excerpts give no indication of the system's purpose.
Judge the INTENDED PURPOSE of the system, not incidental words. Cite only the excerpt ids provided.
Answer with a single JSON object only."""

RISK_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": ["prohibited", "high", "limited", "minimal", "unknown"]},
        "rationale": {"type": "string"},
        "triggers": {"type": "array", "items": {"type": "string"}},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["level", "rationale", "triggers", "evidence_ids", "confidence"],
}

RISK_QUERIES = [
    "intended purpose use case users overview",
    "model card intended use limitations",
    "predict score classify decision applicant candidate",
    "chatbot generate llm openai anthropic completion",
    "biometric face recognition camera",
]


class RiskClassifier:
    def __init__(self, backend: LLMBackend | None = None, model: str | None = None, max_chars: int = 10_000):
        self.backend = backend
        self.model = model
        self.max_chars = max_chars

    def select_evidence(self, index: EvidenceIndex, retriever=None, hint: RiskAssessment | None = None) -> list[Evidence]:
        by_id = {e.id: e for e in index.items}
        chosen: list[Evidence] = []
        seen: set[str] = set()

        def add(ev: Evidence) -> None:
            if ev.id not in seen:
                seen.add(ev.id)
                chosen.append(ev)

        if hint:
            for i in hint.evidence_ids:
                if i in by_id:
                    add(by_id[i])
        # README / model cards first chunks (the system's self-description)
        docs = sorted((e for e in index.items if e.kind in DOC_KINDS),
                      key=lambda e: (0 if "readme" in e.path.lower() else 1 if e.kind == EvidenceKind.MODEL_CARD else 2,
                                     e.path, e.start_line))
        for ev in docs[:6]:
            add(ev)
        if retriever is not None:
            for q in RISK_QUERIES:
                try:
                    for ev in retriever.search(q, k=3):
                        add(ev)
                except Exception:  # noqa: BLE001
                    pass
        out, total = [], 0
        for ev in chosen:
            ln = min(len(ev.snippet), 1500)
            if total + ln > self.max_chars and out:
                break
            total += ln
            out.append(ev)
        return out

    def run(self, index: EvidenceIndex, retriever=None, use_llm: bool = True) -> RiskAssessment:
        hint = heuristic_classify(index)
        if not use_llm or self.backend is None:
            return hint
        evidence = self.select_evidence(index, retriever, hint)
        aliases = make_aliases(evidence)
        prompt = (
            "## Repository excerpts\n" + render_evidence(evidence, aliases) + "\n\n"
            f"## Keyword pre-classifier hint (may be wrong)\nlevel={hint.level.value}; {hint.rationale}\n\n"
            "## Task\nReturn JSON {\"level\": \"prohibited|high|limited|minimal|unknown\", \"rationale\": \"...\", "
            "\"triggers\": [\"e.g. Annex III 4(a): recruitment\"], \"evidence_ids\": [\"E1\"], \"confidence\": 0..1}"
        )
        try:
            raw = self.backend.complete_json(RISK_SYSTEM, prompt, RISK_SCHEMA, model=self.model)
        except Exception as e:  # noqa: BLE001
            hint.rationale += f" (LLM risk classification failed: {e}; using heuristic.)"
            return hint
        valid = {e.id for e in evidence}
        ids = [i for i in resolve_ids(raw.get("evidence_ids"), aliases) if i in valid]
        return RiskAssessment(
            level=coerce_risk(raw.get("level")),
            rationale=str(raw.get("rationale") or "").strip(),
            triggers=str_list(raw.get("triggers")),
            evidence_ids=ids,
            confidence=clamp01(raw.get("confidence"), 0.5),
        )
