"""Offline deterministic evaluator ("mock LLM").

Purpose: run the whole pipeline without an API key (tests, CI, a reproducible demo,
Streamlit Cloud without secrets). It mimics the LLM contract exactly - same JSON
schema, verbatim evidence quotes - but judges with transparent keyword signals.
It is NOT a substitute for a real LLM judgement and is labelled as such in the UI.
"""
from __future__ import annotations

import re

LEXICON = {
    "technical": {
        "match": ["technical", "architecture", "integration", "scalab"],
        "pos": ["event-driven", "kafka", "api gateway", "pre-built", "connector", "identity resolution",
                "load-tested", "auto-scales", "latency", "terraform", "ci/cd", "sap integration suite",
                "s/4hana", "service cloud", "streaming", "near-real-time", "bigquery", "deterministic",
                "fuzzy-match", "million profiles"],
        "neg": ["will be defined during", "will be assessed", "later phase", "csv", "if required",
                "not included", "as appropriate", "is scalable and cloud based"],
    },
    "implementation": {
        "match": ["implementation", "timeline", "milestone", "delivery", "plan"],
        "pos": ["milestone", "acceptance criterion", "raci", "risk register", "mitigated",
                "governance", "steering committee", "named", "rollback", "fte", "sprint",
                "go/no-go", "deputies", "stage-gated", "profiling sprint", "sign-off", "signed"],
        "neg": ["will be prepared after", "sized after discovery", "if needed", "standard raid",
                "will be agreed", "accelerated methodology"],
    },
    "commercial": {
        "match": ["commercial", "pric", "cost", "value"],
        "pos": ["fixed price", "fixed-price", "total cost of ownership", "assumptions", "capped at cpi",
                "milestone-based", "held for 3 years", "travel is included", "per day",
                "per consultant day"],
        "neg": ["estimate", "not yet included", "will be confirmed", "depends on", "quoted separately",
                "list price", "out of scope", "time-and-materials", "indicative"],
    },
    "security": {
        "match": ["security", "compliance", "privacy", "gdpr"],
        "pos": ["27001", "soc 2 type ii", "aes-256", "tls", "mfa", "dpia", "data processing agreement",
                "audit log", "penetration", "pseudonymisation", "erasure", "customer-managed keys",
                "siem", "least-privilege", "consent"],
        "neg": ["best practices", "working towards", "will be confirmed", "will be documented",
                "vendor is responsible", "awareness training", "type i "],
    },
    "support": {
        "match": ["support", "experience", "reference"],
        "pos": ["24x7", "dedicated", "technical account manager", "service credits", "references",
                "hypercare", "follow-the-sun", "customer success manager", "since 2010", "since 2019",
                "multi-country", "contactable", "p1 response", "sla"],
        "neg": ["upon request", "provided on request", "business hours", "one business day", "founded in 2024",
                "email-based", "priority 1 incidents only"],
    },
}


def _sentences(text: str) -> list[str]:
    flat = re.sub(r"\[Page \d+\]", " ", text)
    flat = re.sub(r"\s+", " ", flat)
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z0-9(])", flat) if len(s.strip()) > 20]


def _profile_for(criterion: dict) -> dict:
    hay = f"{criterion['name']} {criterion.get('description', '')}".lower()
    best, best_hits = None, 0
    for key, prof in LEXICON.items():
        hits = sum(1 for m in prof["match"] if m in hay)
        if hits > best_hits:
            best, best_hits = key, hits
    if best:
        return LEXICON[best] | {"key": best}
    words = [w for w in re.findall(r"[a-z]{5,}", hay)]
    return {"key": "generic", "pos": words, "neg": []}


def _tco_eur(text: str) -> float | None:
    m = re.search(r"total cost of ownership, 3 years\s*([\d,]+)", text.lower())
    return float(m.group(1).replace(",", "")) if m else None


def mock_evaluate(supplier_name: str, text: str, criteria: list[dict]) -> dict:
    low = text.lower()
    sentences = _sentences(text)
    results, risks = [], []
    for c in criteria:
        prof = _profile_for(c)
        pos = [k for k in prof["pos"] if k in low]
        neg = [k for k in prof["neg"] if k in low]
        raw = 4.0 + 0.45 * min(len(pos), 10) - 0.8 * min(len(neg), 4)
        if prof["key"] == "commercial":
            tco = _tco_eur(text)
            if tco is not None:
                raw += 2.0 if tco < 700_000 else 1.0 if tco < 1_000_000 else -0.5 if tco > 1_300_000 else 0
        max_score = float(c["max_score"])
        score = max(1.0, min(10.0, raw)) / 10.0 * max_score
        score = round(score * 2) / 2  # nearest 0.5

        quotes = []
        for kw in (pos + neg):
            s = next((s for s in sentences if kw in s.lower()), None)
            if s and s not in quotes:
                quotes.append(s)
            if len(quotes) == 2:
                break
        evidence = " | ".join(q[:300] for q in quotes) or "No evidence found in document"
        if not quotes:
            score = 0.0
        justification = (f"Deterministic keyword evaluator: {len(pos)} supporting signal(s)"
                         f"{' (' + ', '.join(pos[:5]) + ')' if pos else ''} and {len(neg)} gap "
                         f"signal(s){' (' + ', '.join(neg[:4]) + ')' if neg else ''}.")
        risks += [f"{c['name']}: proposal states '{n}'" for n in neg[:2]]
        results.append({"criterion_id": c["criterion_id"], "score": score, "max_score": max_score,
                        "justification": justification, "evidence": evidence})
    return {
        "supplier_name": supplier_name,
        "criteria": results,
        "risks": risks,
        "overall_summary": (f"{supplier_name} evaluated offline by the deterministic keyword "
                            f"evaluator across {len(criteria)} criteria. Use a real LLM provider "
                            f"for a qualitative judgement."),
    }
