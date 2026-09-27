"""Validation Tool: parsing and normalisation of LLM output."""
import json

import pytest

from rfp.tools.validation_tool import (JSONParseError, failed_scorecard, normalize_scorecard,
                                       parse_llm_json)

CRITERIA = [
    {"criterion_id": 1, "name": "Technical Capability", "max_score": 10},
    {"criterion_id": 2, "name": "Commercial Value", "max_score": 10},
    {"criterion_id": 3, "name": "Security & Compliance", "max_score": 5},
]
DOC = "We hold ISO/IEC 27001:2022 certification. Total cost of ownership is EUR 982,000."


def item(cid, score, **kw):
    return {"criterion_id": cid, "score": score, "max_score": 10, "justification": "ok",
            "evidence": "We hold ISO/IEC 27001:2022 certification", **kw}


def test_parse_strips_code_fences_and_chatter():
    raw = 'Here you go:\n```json\n{"criteria": []}\n```'
    assert parse_llm_json(raw) == {"criteria": []}


@pytest.mark.parametrize("raw", ["", "no json here", '{"a": 1,', "[1, 2]"])
def test_parse_rejects_bad_json(raw):
    with pytest.raises(JSONParseError):
        parse_llm_json(raw)


def test_valid_output_passes_unchanged():
    sc = normalize_scorecard({"supplier_name": "X", "criteria": [item(1, 8), item(2, 6),
                                                                 item(3, 4, max_score=5)],
                              "risks": ["r"], "overall_summary": "s"}, CRITERIA, "X", DOC)
    assert [c.score for c in sc.criteria] == [8, 6, 4]
    assert all(c.status == "OK" for c in sc.criteria)
    assert sc.warnings == []


def test_out_of_range_is_clipped():
    sc = normalize_scorecard({"criteria": [item(1, 14), item(2, -3), item(3, 7)],
                              "overall_summary": "s"}, CRITERIA, "X", DOC)
    assert [c.score for c in sc.criteria] == [10, 0, 5]   # criterion 3 max is 5 (from DB)
    assert [c.status for c in sc.criteria] == ["CLIPPED"] * 3


def test_non_numeric_and_string_numbers():
    sc = normalize_scorecard({"criteria": [item(1, "eight"), item(2, "7/10"), item(3, None)],
                              "overall_summary": "s"}, CRITERIA, "X", DOC)
    assert [c.score for c in sc.criteria] == [0, 7, 0]
    assert [c.status for c in sc.criteria] == ["DEFAULTED_INVALID", "OK", "DEFAULTED_INVALID"]


def test_missing_unknown_duplicate():
    sc = normalize_scorecard({"criteria": [item(1, 6), item(1, 9), item(99, 10)],
                              "overall_summary": "s"}, CRITERIA, "X", DOC)
    assert [c.criterion_id for c in sc.criteria] == [1, 2, 3]
    assert sc.criteria[0].score == 6                       # first duplicate kept
    assert sc.criteria[1].status == "DEFAULTED_MISSING"
    joined = " ".join(sc.warnings)
    assert "unknown criterion_id 99" in joined and "Duplicate" in joined


def test_match_by_name_when_id_missing():
    sc = normalize_scorecard({"criteria": [{"name": "commercial value", "score": 5}],
                              "overall_summary": "s"}, CRITERIA, "X", DOC)
    assert sc.criteria[1].score == 5


def test_no_criteria_list():
    sc = normalize_scorecard({"foo": "bar"}, CRITERIA, "X", DOC)
    assert all(c.score == 0 and c.status == "DEFAULTED_MISSING" for c in sc.criteria)


def test_evidence_verification():
    sc = normalize_scorecard({"criteria": [
        item(1, 5), item(2, 5, evidence="We offer a 50% discount forever and ever"),
    ], "overall_summary": "s"}, CRITERIA, "X", DOC)
    assert sc.criteria[0].evidence_verified is True
    assert sc.criteria[1].evidence_verified is False
    assert any("could not be located" in w for w in sc.warnings)


def test_supplier_name_mismatch_uses_entered_name():
    sc = normalize_scorecard({"supplier_name": "Wrong Co", "criteria": [],
                              "overall_summary": "s"}, CRITERIA, "Right Co", DOC)
    assert sc.supplier_name == "Right Co"


def test_failed_scorecard_all_zero():
    sc = failed_scorecard(CRITERIA, "X", "bad json")
    assert all(c.score == 0 for c in sc.criteria)
    json.dumps(sc.model_dump())  # serialisable
