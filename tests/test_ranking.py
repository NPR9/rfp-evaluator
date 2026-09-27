"""Ranking Tool: formulas, benchmarks, tie-breaks, determinism."""
import random

import pytest

from rfp.tools.ranking_tool import rank_suppliers

CRITERIA = [
    {"criterion_id": 1, "name": "Tech", "weight": 60, "max_score": 10},
    {"criterion_id": 2, "name": "Price", "weight": 40, "max_score": 10},
]


def sup(name, scores, date="2026-09-10", exp=3.0):
    return {"supplier_name": name, "submission_date": date, "experience_rating": exp,
            "scorecard": {"criteria": [
                {"criterion_id": cid, "score": s, "status": "OK", "evidence_verified": True,
                 "justification": "j", "evidence": "e"} for cid, s in scores.items()],
                "risks": [], "overall_summary": "", "warnings": []}}


def by_name(res):
    return {r["supplier_name"]: r for r in res["leaderboard"]}


def test_formulas_hand_calculated():
    res = rank_suppliers([sup("A", {1: 8, 2: 5}), sup("B", {1: 4, 2: 10})], CRITERIA)
    a, b = by_name(res)["A"], by_name(res)["B"]
    # Absolute: A = 8/10*60 + 5/10*40 = 48 + 20 = 68 ; B = 24 + 40 = 64
    assert a["absolute_score"] == pytest.approx(68)
    assert b["absolute_score"] == pytest.approx(64)
    # Benchmarks: Tech 8 (A), Price 10 (B)
    bm = {x["criterion_id"]: x for x in res["benchmarks"]}
    assert bm[1]["benchmark_score"] == 8 and bm[1]["leaders"] == ["A"]
    assert bm[2]["benchmark_score"] == 10 and bm[2]["leaders"] == ["B"]
    # Gaps and relative %
    a_price = next(c for c in a["criteria"] if c["criterion_id"] == 2)
    assert a_price["gap"] == -5 and a_price["relative_pct"] == pytest.approx(50)
    # PPI: A = (100*60 + 50*40)/100 = 80 ; B = (50*60 + 100*40)/100 = 70
    assert a["ppi"] == pytest.approx(80) and b["ppi"] == pytest.approx(70)
    assert [a["final_rank"], b["final_rank"]] == [1, 2]
    assert res["tie_breaks"][0]["decided_by"] == "PPI"


def test_leader_gap_is_zero():
    res = rank_suppliers([sup("A", {1: 9, 2: 9}), sup("B", {1: 1, 2: 1})], CRITERIA)
    for c in by_name(res)["A"]["criteria"]:
        assert c["gap"] == 0 and c["is_benchmark_leader"] and c["relative_pct"] == 100


def test_zero_benchmark_is_safe():
    res = rank_suppliers([sup("A", {1: 5, 2: 0}), sup("B", {1: 4, 2: 0})], CRITERIA)
    for r in res["leaderboard"]:
        price = next(c for c in r["criteria"] if c["criterion_id"] == 2)
        assert price["relative_pct"] == 0.0
    assert any("No supplier scored above 0" in w for w in res["warnings"])


def test_tie_break_submission_date():
    res = rank_suppliers([sup("Late", {1: 7, 2: 7}, date="2026-09-12"),
                          sup("Early", {1: 7, 2: 7}, date="2026-09-01")], CRITERIA)
    assert [r["supplier_name"] for r in res["leaderboard"]] == ["Early", "Late"]
    assert res["tie_breaks"][0]["decided_by"] == "SUBMISSION_DATE"


def test_tie_break_experience():
    res = rank_suppliers([sup("Low", {1: 7, 2: 7}, exp=2), sup("High", {1: 7, 2: 7}, exp=4.5)],
                         CRITERIA)
    assert [r["supplier_name"] for r in res["leaderboard"]] == ["High", "Low"]
    assert res["tie_breaks"][0]["decided_by"] == "EXPERIENCE"


def test_tie_break_name():
    res = rank_suppliers([sup("zeta", {1: 7, 2: 7}), sup("Alpha", {1: 7, 2: 7})], CRITERIA)
    assert [r["supplier_name"] for r in res["leaderboard"]] == ["Alpha", "zeta"]
    assert res["tie_breaks"][0]["decided_by"] == "NAME"


def test_ranks_sequential_and_order_independent():
    pool = [sup("A", {1: 7, 2: 7}, "2026-09-05", 3), sup("B", {1: 7, 2: 7}, "2026-09-05", 4),
            sup("C", {1: 9, 2: 2}), sup("D", {1: 7, 2: 7}, "2026-09-01", 1),
            sup("E", {1: 1, 2: 1})]
    expected = None
    for seed in range(20):
        shuffled = pool[:]
        random.Random(seed).shuffle(shuffled)
        res = rank_suppliers(shuffled, CRITERIA)
        order = [(r["supplier_name"], r["final_rank"]) for r in res["leaderboard"]]
        expected = expected or order
        assert order == expected
    assert [r for _, r in expected] == [1, 2, 3, 4, 5]


def test_float_noise_does_not_break_ties():
    crit = [{"criterion_id": i, "name": f"C{i}", "weight": w, "max_score": 10}
            for i, w in enumerate([33.3, 33.3, 33.4], 1)]
    # Same scores in different criterion order -> mathematically equal PPI.
    a = sup("A", {1: 7, 2: 9, 3: 8}, date="2026-09-02")
    b = sup("B", {1: 7, 2: 9, 3: 8}, date="2026-09-01")
    res = rank_suppliers([a, b], crit)
    assert res["leaderboard"][0]["supplier_name"] == "B"  # decided by date, not float noise
