"""Ranking Tool: deterministic Python only. No LLM calls in this module.

Formulas (w = criterion weight in %, s = validated score, m = max score)
  weighted points (per criterion)  = s / m * w
  Absolute weighted score          = sum of weighted points                    (0-100)
  Criterion benchmark  B_c         = highest validated score for criterion c across suppliers
  Criterion gap                    = s - B_c     (0 for the leader, otherwise negative)
  Relative performance %           = s / B_c * 100
                                     if B_c == 0 (no supplier scored above 0): 0.0
  Peer Performance Index (PPI)     = sum(relative% * w) / sum(w)              (0-100)

Mandatory tie-break order (stable sort, then ranks 1..N):
  1) higher PPI  2) earlier submission date  3) higher experience rating
  4) supplier name ascending (case-insensitive)
PPI is rounded to PPI_DECIMALS before sorting so float noise cannot flip an order.
"""
from __future__ import annotations

from datetime import date

from rfp.config import PPI_DECIMALS

TIE_BREAK_RULES = [
    "1) Higher PPI",
    "2) Earlier submission date",
    "3) Higher historical experience rating",
    "4) Supplier name ascending (A-Z)",
]


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _scorecard_dict(sc) -> dict:
    return sc.model_dump() if hasattr(sc, "model_dump") else sc


def compute_benchmarks(suppliers: list[dict], criteria: list[dict]) -> dict[int, dict]:
    """Best validated score per criterion and who holds it (ties listed alphabetically)."""
    bench: dict[int, dict] = {}
    for c in criteria:
        cid = int(c["criterion_id"])
        scores = {
            s["supplier_name"]: next(r["score"] for r in _scorecard_dict(s["scorecard"])["criteria"]
                                     if r["criterion_id"] == cid)
            for s in suppliers
        }
        best = max(scores.values()) if scores else 0.0
        leaders = sorted([n for n, v in scores.items() if v == best], key=str.casefold)
        bench[cid] = {"criterion_id": cid, "criterion_name": c["name"], "benchmark_score": best,
                      "max_score": float(c["max_score"]), "weight": float(c["weight"]),
                      "leaders": leaders if best > 0 else []}
    return bench


def sort_key(row: dict):
    """The single source of truth for ordering."""
    return (
        -round(row["ppi"], PPI_DECIMALS),
        _as_date(row["submission_date"]),
        -float(row["experience_rating"]),
        str(row["supplier_name"]).casefold(),
    )


def _explain_pair(a: dict, b: dict) -> tuple[str, str]:
    """Why supplier a is ranked directly above supplier b -> (rule, sentence)."""
    pa, pb = round(a["ppi"], PPI_DECIMALS), round(b["ppi"], PPI_DECIMALS)
    if pa != pb:
        return "PPI", (f"{a['supplier_name']} is above {b['supplier_name']} on PPI "
                       f"({pa:.2f} vs {pb:.2f}).")
    da, db = _as_date(a["submission_date"]), _as_date(b["submission_date"])
    if da != db:
        return "SUBMISSION_DATE", (f"PPI tied at {pa:.2f}; {a['supplier_name']} submitted earlier "
                                   f"({da.isoformat()} vs {db.isoformat()}).")
    ea, eb = float(a["experience_rating"]), float(b["experience_rating"])
    if ea != eb:
        return "EXPERIENCE", (f"PPI and submission date tied; {a['supplier_name']} has the higher "
                              f"experience rating ({ea:g} vs {eb:g}).")
    return "NAME", (f"PPI, submission date and experience rating all tied; ordered by supplier "
                    f"name ({a['supplier_name']} before {b['supplier_name']}).")


def rank_suppliers(suppliers: list[dict], criteria: list[dict]) -> dict:
    """
    suppliers: [{supplier_name, submission_date, experience_rating, scorecard, ...extra}]
    criteria : active criteria snapshot (criterion_id, name, weight, max_score, ...)
    returns  : {"benchmarks": [...], "leaderboard": [...], "tie_breaks": [...], "warnings": [...]}
    """
    warnings: list[str] = []
    if not suppliers:
        return {"benchmarks": [], "leaderboard": [], "tie_breaks": [], "warnings": ["No suppliers."]}

    total_weight = sum(float(c["weight"]) for c in criteria)
    if total_weight <= 0:
        raise ValueError("Active criteria weights sum to 0; cannot rank.")

    bench = compute_benchmarks(suppliers, criteria)
    for b in bench.values():
        if b["benchmark_score"] == 0:
            warnings.append(f"No supplier scored above 0 on '{b['criterion_name']}'; relative "
                            f"performance set to 0% for everyone on this criterion.")

    rows: list[dict] = []
    for s in suppliers:
        sc = _scorecard_dict(s["scorecard"])
        by_id = {r["criterion_id"]: r for r in sc["criteria"]}
        details, absolute, ppi_num = [], 0.0, 0.0
        for c in criteria:
            cid, w, m = int(c["criterion_id"]), float(c["weight"]), float(c["max_score"])
            r = by_id[cid]
            score = float(r["score"])
            b = bench[cid]["benchmark_score"]
            weighted_points = score / m * w
            rel = (score / b * 100.0) if b > 0 else 0.0
            absolute += weighted_points
            ppi_num += rel * w
            details.append({
                "criterion_id": cid, "criterion_name": c["name"], "weight": w, "max_score": m,
                "score": score, "weighted_points": round(weighted_points, 4),
                "benchmark_score": b, "gap": round(score - b, 4),
                "relative_pct": round(rel, 4), "is_benchmark_leader": b > 0 and score == b,
                "status": r["status"], "evidence_verified": r["evidence_verified"],
                "justification": r["justification"], "evidence": r["evidence"],
            })
        row = {k: v for k, v in s.items() if k != "scorecard"}
        row.update({
            "supplier_name": s["supplier_name"],
            "submission_date": _as_date(s["submission_date"]).isoformat(),
            "experience_rating": float(s["experience_rating"]),
            "absolute_score": round(absolute, 4),
            "ppi": round(ppi_num / total_weight, PPI_DECIMALS),
            "criteria": details,
            "risks": sc["risks"],
            "overall_summary": sc["overall_summary"],
            "validation_warnings": sc["warnings"],
        })
        rows.append(row)

    rows.sort(key=sort_key)  # stable, fully deterministic
    tie_breaks = []
    for i, row in enumerate(rows):
        row["final_rank"] = i + 1
        if i == 0:
            row["rank_reason"] = "Highest PPI after applying the tie-break order."
        else:
            rule, sentence = _explain_pair(rows[i - 1], row)
            row["rank_reason"] = sentence
            tie_breaks.append({"higher": rows[i - 1]["supplier_name"],
                               "lower": row["supplier_name"],
                               "decided_by": rule, "explanation": sentence})

    return {"benchmarks": list(bench.values()), "leaderboard": rows,
            "tie_breaks": tie_breaks, "warnings": warnings}
