"""End-to-end orchestrator, SQLite persistence, document errors and provider wiring."""
import json
from types import SimpleNamespace

import pytest

from rfp import db
from rfp.agents import evaluation_agent
from rfp.agents.evaluation_agent import LLMSettings
from rfp.config import ERROR_CASE_DIR
from rfp.orchestrator import run_rfp_evaluation
from rfp.sample_suppliers import load_sample_suppliers
from rfp.tools.document_tool import DocumentError, extract_pdf_text


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    return path


MOCK = LLMSettings(provider="mock")


def test_full_run_is_persisted_and_deterministic():
    r1 = run_rfp_evaluation(load_sample_suppliers(), MOCK)
    r2 = run_rfp_evaluation(load_sample_suppliers(), MOCK)
    order = lambda r: [(x["supplier_name"], x["ppi"], x["final_rank"]) for x in r["leaderboard"]]
    assert order(r1) == order(r2)
    assert [x["final_rank"] for x in r1["leaderboard"]] == [1, 2, 3, 4]

    rows = db.get_supplier_rows(r1["rfp_run_id"])
    assert len(rows) == 4 and rows[0]["final_rank"] == 1
    stored = db.get_run(r1["rfp_run_id"])
    assert stored["rfp_run_id"] == r1["rfp_run_id"]
    assert {x["status"] for x in db.list_runs()} == {"COMPLETED"}
    # every leaderboard score traces back to criterion, weight, evidence
    for s in stored["leaderboard"]:
        for c in s["criteria"]:
            assert {"weight", "score", "benchmark_score", "evidence", "justification"} <= c.keys()


@pytest.mark.parametrize("mode,expect_attempts", [("malformed_values", 1),
                                                  ("invalid_json_once", 2),
                                                  ("invalid_json_always", 2)])
def test_fault_modes(mode, expect_attempts):
    res = run_rfp_evaluation(load_sample_suppliers(), MOCK, fault_mode=mode)
    apex = next(r for r in res["leaderboard"] if r["supplier_name"] == "Apex Systems")
    assert apex["llm_attempts"] == expect_attempts
    if mode != "invalid_json_once":
        assert apex["validation_warnings"]
    if mode == "invalid_json_always":
        assert apex["absolute_score"] == 0 and apex["final_rank"] == 4


def test_unreadable_pdf_is_skipped_not_crashing():
    sups = load_sample_suppliers()[:2]
    sups.append({"supplier_name": "Scan Co", "submission_date": "2026-09-01",
                 "experience_rating": 3, "filename": "scan.pdf",
                 "pdf_bytes": (ERROR_CASE_DIR / "Scanned_No_Text_Proposal.pdf").read_bytes()})
    res = run_rfp_evaluation(sups, MOCK)
    assert len(res["leaderboard"]) == 2
    assert res["skipped_suppliers"][0]["supplier_name"] == "Scan Co"


def test_invalid_criteria_fail_the_run():
    with db.get_conn() as conn:
        conn.execute("UPDATE evaluation_criteria SET weight = 50 WHERE criterion_id = 1")
    with pytest.raises(RuntimeError, match="must total 100%"):
        run_rfp_evaluation(load_sample_suppliers(), MOCK)
    assert db.list_runs()[0]["status"] == "FAILED"


def test_criteria_changes_flow_into_run():
    crit = db.get_all_criteria()
    crit[4]["is_active"] = False                   # drop Support (10%)
    crit[0]["weight"] = 40                         # Tech 30 -> 40
    db.save_criteria(crit)
    res = run_rfp_evaluation(load_sample_suppliers(), MOCK)
    assert [c["criterion_id"] for c in res["criteria"]] == [1, 2, 3, 4]
    assert all(len(r["criteria"]) == 4 for r in res["leaderboard"])


@pytest.mark.parametrize("name,exc_text", [("Scanned_No_Text_Proposal.pdf", "No usable text"),
                                           ("Corrupt_Not_A_PDF.pdf", "not a valid PDF")])
def test_document_errors(name, exc_text):
    with pytest.raises(DocumentError, match=exc_text):
        extract_pdf_text((ERROR_CASE_DIR / name).read_bytes(), name)


def test_openai_provider_wiring(monkeypatch):
    """No network: fake OpenAI client returns a valid scorecard; checks prompt + JSON mode."""
    captured = {}

    class FakeCompletions:
        def create(self, **kw):
            captured.update(kw)
            crit = [{"criterion_id": i, "score": 7, "max_score": 10, "justification": "j",
                     "evidence": "No evidence found in document"} for i in range(1, 6)]
            content = json.dumps({"supplier_name": "x", "criteria": crit, "risks": [],
                                  "overall_summary": "s"})
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=content))])

    class FakeOpenAI:
        def __init__(self, **kw):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    res = run_rfp_evaluation(load_sample_suppliers()[:2],
                             LLMSettings(provider="openai", api_key="test"))
    assert captured["temperature"] == 0 and captured["response_format"]["type"] == "json_object"
    user_msg = captured["messages"][1]["content"]
    assert "Technical Capability" in user_msg and "DOCUMENT_START" in user_msg
    # equal scores -> tie on PPI -> earlier submission (BrightPath 09-08 < Apex 09-10)
    assert res["leaderboard"][0]["supplier_name"] == "BrightPath Tech"
    assert res["tie_breaks"][0]["decided_by"] == "SUBMISSION_DATE"
