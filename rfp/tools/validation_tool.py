"""Validation Tool: turn raw LLM text into a trusted, normalised scorecard.

Pipeline
  1. parse_llm_json      raw text -> dict  (strips code fences / chatter; raises JSONParseError)
  2. normalize_scorecard dict     -> ValidatedScorecard + warnings
       - one result per ACTIVE criterion, in criterion order
       - unknown / duplicate criterion ids dropped
       - missing criteria filled with score 0 (status DEFAULTED_MISSING)
       - non-numeric scores -> 0 (status DEFAULTED_INVALID)
       - out-of-range scores clipped to [0, max_score] (status CLIPPED)
       - max_score always taken from the database, never from the LLM
       - evidence quotes checked against the source document (evidence_verified)
  3. The final object is validated by Pydantic so downstream code can trust it.

Every change is recorded as a human-readable warning, so nothing is silently fixed.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

NO_EVIDENCE = "No evidence found in document"


class JSONParseError(Exception):
    pass


# ------------------------------------------------------------------ strict output models
CriterionStatus = Literal["OK", "CLIPPED", "DEFAULTED_MISSING", "DEFAULTED_INVALID"]


class CriterionResult(BaseModel):
    criterion_id: int
    criterion_name: str
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    justification: str
    evidence: str
    evidence_verified: bool
    status: CriterionStatus

    @model_validator(mode="after")
    def _score_in_range(self):
        if self.score > self.max_score:
            raise ValueError("score exceeds max_score")
        return self


class ValidatedScorecard(BaseModel):
    supplier_name: str
    criteria: list[CriterionResult]
    risks: list[str]
    overall_summary: str
    warnings: list[str]

    @field_validator("criteria")
    @classmethod
    def _unique_ids(cls, v):
        ids = [c.criterion_id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate criterion ids")
        return v


# ------------------------------------------------------------------ step 1: parse
def parse_llm_json(raw: str) -> dict:
    """Extract the first JSON object from an LLM reply."""
    if raw is None or not str(raw).strip():
        raise JSONParseError("empty response")
    text = str(raw).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise JSONParseError("no JSON object found in response")
        try:
            obj = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise JSONParseError(f"invalid JSON: {exc.msg} at char {exc.pos}") from exc
    if not isinstance(obj, dict):
        raise JSONParseError(f"expected a JSON object, got {type(obj).__name__}")
    return obj


# ------------------------------------------------------------------ helpers
def _to_number(value: Any) -> float | None:
    """Coerce 8, 8.5, "8", "8/10", "7.5 out of 10" -> float. Returns None if impossible."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return None if (math.isnan(value) or math.isinf(value)) else float(value)
    if isinstance(value, str):
        m = re.search(r"-?\d+(?:\.\d+)?", value)
        if m:
            return float(m.group())
    return None


def _to_int(value: Any) -> int | None:
    n = _to_number(value)
    return int(n) if n is not None and float(n).is_integer() else None


def _norm_text(s: str) -> str:
    s = s.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9%€$.]+", " ", s).strip()


def evidence_found_in_document(evidence: str, document_text: str) -> bool:
    """True if at least one quoted fragment (split on ' | ' or '...') appears in the document.
    Compares on a normalised form (case, punctuation, whitespace) and a leading slice, so small
    formatting differences from PDF extraction do not cause false negatives."""
    if not evidence or evidence.strip() == NO_EVIDENCE or not document_text:
        return False
    doc = _norm_text(document_text)
    for frag in re.split(r"\s*\|\s*|\.\.\.|…", evidence):
        f = _norm_text(frag.strip(" \"'"))
        if len(f) < 12:
            continue
        if f in doc or f[:40] in doc:
            return True
    return False


# ------------------------------------------------------------------ step 2: normalise
def normalize_scorecard(parsed: dict, criteria: list[dict], supplier_name: str,
                        document_text: str = "") -> ValidatedScorecard:
    warnings: list[str] = []
    by_id = {int(c["criterion_id"]): c for c in criteria}
    by_name = {str(c["name"]).strip().lower(): int(c["criterion_id"]) for c in criteria}

    llm_name = parsed.get("supplier_name")
    if llm_name and str(llm_name).strip().lower() != supplier_name.strip().lower():
        warnings.append(f"LLM returned supplier_name '{llm_name}'; using entered name "
                        f"'{supplier_name}'.")

    items = parsed.get("criteria")
    if not isinstance(items, list):
        warnings.append("LLM output has no 'criteria' list; every criterion defaulted to 0.")
        items = []

    collected: dict[int, CriterionResult] = {}
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            warnings.append(f"criteria[{idx}] is not an object; ignored.")
            continue
        cid = _to_int(item.get("criterion_id"))
        if cid is None:  # fall back to matching by name
            nm = str(item.get("name") or item.get("criterion_name") or "").strip().lower()
            cid = by_name.get(nm)
        if cid is None or cid not in by_id:
            warnings.append(f"criteria[{idx}] has unknown criterion_id "
                            f"{item.get('criterion_id')!r}; ignored.")
            continue
        if cid in collected:
            warnings.append(f"Duplicate result for criterion {cid}; kept the first one.")
            continue

        crit = by_id[cid]
        cname, max_score = crit["name"], float(crit["max_score"])
        status: CriterionStatus = "OK"

        llm_max = _to_number(item.get("max_score"))
        if llm_max is not None and abs(llm_max - max_score) > 1e-9:
            warnings.append(f"[{cname}] LLM used max_score {llm_max:g}; database value "
                            f"{max_score:g} applied.")

        score = _to_number(item.get("score"))
        if score is None:
            warnings.append(f"[{cname}] score {item.get('score')!r} is not numeric; set to 0.")
            score, status = 0.0, "DEFAULTED_INVALID"
        elif score < 0 or score > max_score:
            clipped = min(max(score, 0.0), max_score)
            warnings.append(f"[{cname}] score {score:g} outside 0-{max_score:g}; "
                            f"clipped to {clipped:g}.")
            score, status = clipped, "CLIPPED"

        justification = str(item.get("justification") or "").strip()
        if not justification:
            justification = "No justification provided by the model."
            warnings.append(f"[{cname}] missing justification.")
        evidence = str(item.get("evidence") or "").strip() or NO_EVIDENCE
        verified = evidence_found_in_document(evidence, document_text)
        if evidence != NO_EVIDENCE and document_text and not verified:
            warnings.append(f"[{cname}] evidence quote could not be located verbatim in the "
                            f"PDF text - review manually.")

        collected[cid] = CriterionResult(
            criterion_id=cid, criterion_name=cname, score=round(score, 2), max_score=max_score,
            justification=justification, evidence=evidence, evidence_verified=verified,
            status=status,
        )

    results: list[CriterionResult] = []
    for cid, crit in by_id.items():  # criteria order from the database
        if cid in collected:
            results.append(collected[cid])
        else:
            warnings.append(f"[{crit['name']}] missing from LLM output; defaulted to 0.")
            results.append(CriterionResult(
                criterion_id=cid, criterion_name=crit["name"], score=0.0,
                max_score=float(crit["max_score"]),
                justification="Criterion not returned by the model; defaulted to 0.",
                evidence=NO_EVIDENCE, evidence_verified=False, status="DEFAULTED_MISSING",
            ))

    risks = parsed.get("risks")
    if isinstance(risks, str):
        risks = [risks]
    if not isinstance(risks, list):
        risks = []
    risks = [str(r).strip() for r in risks if str(r).strip()]

    summary = str(parsed.get("overall_summary") or "").strip()
    if not summary:
        summary = "No summary provided by the model."
        warnings.append("Missing overall_summary.")

    return ValidatedScorecard(supplier_name=supplier_name, criteria=results, risks=risks,
                              overall_summary=summary, warnings=warnings)


def failed_scorecard(criteria: list[dict], supplier_name: str, reason: str) -> ValidatedScorecard:
    """Scorecard used when the LLM never produced parseable JSON: every criterion = 0.
    The supplier stays in the run (visible, ranked last-ish) instead of silently disappearing."""
    sc = normalize_scorecard({"criteria": []}, criteria, supplier_name, "")
    sc.warnings = [f"LLM output unusable after retries ({reason}); all criteria scored 0."]
    sc.overall_summary = "Evaluation failed - LLM did not return valid JSON."
    for c in sc.criteria:
        c.status = "DEFAULTED_INVALID"
        c.justification = "LLM output could not be parsed; defaulted to 0."
    return sc
