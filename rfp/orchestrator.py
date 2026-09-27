"""Orchestrator Agent (LangGraph StateGraph).

Graph
                     +---------------------------- retry (bad JSON) ---+
                     v                                                 |
  load_criteria -> extract_document -> evaluate_supplier -> validate_output
        |                ^      |                                      |
     (invalid)           |   (unreadable PDF: skip)                   v
        v                +------------------------------------ next_supplier?
       END                                                             |  (all done)
                                                                       v
                                                    score_benchmark_rank -> persist_results -> END

Roles
  Orchestrator Agent  - this graph: decides which tool runs next (conditional edges)
  Document Tool       - rfp.tools.document_tool.extract_pdf_text
  Evaluation Agent    - rfp.agents.evaluation_agent.run_evaluation   (the ONLY LLM call)
  Validation Tool     - rfp.tools.validation_tool
  Ranking Tool        - rfp.tools.ranking_tool                        (pure Python)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from rfp import db
from rfp.agents.evaluation_agent import EvaluationRequest, LLMError, LLMSettings, run_evaluation
from rfp.config import LLM_JSON_RETRIES
from rfp.tools.document_tool import DocumentError, extract_pdf_text
from rfp.tools.ranking_tool import TIE_BREAK_RULES, rank_suppliers
from rfp.tools.validation_tool import (JSONParseError, failed_scorecard, normalize_scorecard,
                                       parse_llm_json)

FAULT_MODES = {
    "none": "No fault injection (normal run)",
    "malformed_values": "Corrupt 1st supplier's LLM JSON: out-of-range, non-numeric, "
                        "missing & unknown criteria, code fences",
    "invalid_json_once": "1st supplier's first LLM reply is broken JSON -> agent retries",
    "invalid_json_always": "1st supplier's LLM reply is always broken -> defaulted to 0",
}

FORMULAS = {
    "weighted_points": "score / max_score * weight",
    "absolute_weighted_score": "sum over criteria of (score / max_score * weight)  [0-100]",
    "criterion_benchmark": "highest validated score for the criterion across all suppliers",
    "criterion_gap": "score - benchmark_score  (0 for the leader, otherwise negative)",
    "relative_performance_pct": "score / benchmark_score * 100; 0 when benchmark_score = 0",
    "peer_performance_index": "sum(relative_pct * weight) / sum(weight)  [0-100]",
}


class RunState(TypedDict, total=False):
    rfp_run_id: str
    created_at: str
    settings: LLMSettings
    fault_mode: str
    suppliers_input: list[dict]
    criteria: list[dict]
    idx: int
    attempt: int
    doc_text: str
    doc_meta: dict
    raw_output: str
    parse_error: str
    history: list[dict]
    evaluated: list[dict]
    skipped: list[dict]
    trace: list[dict]
    fatal_error: str
    result: dict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"RFP-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6].upper()}"


def _log(state: RunState, step: str, message: str, **extra) -> list[dict]:
    return [*state.get("trace", []), {"ts": _now(), "step": step, "message": message, **extra}]


# ------------------------------------------------------------------ fault injection (demo)
def _inject_fault(raw: str, mode: str, attempt: int) -> str:
    if mode == "invalid_json_always" or (mode == "invalid_json_once" and attempt == 1):
        return 'Sure! Here is my evaluation:\n{"supplier_name": "X", "criteria": [{"criterion_id": 1, "score": 8,'
    if mode == "malformed_values":
        data = json.loads(raw)
        crit = data.get("criteria", [])
        if len(crit) >= 1:
            crit[0]["score"] = 14                       # out of range  -> clipped
        if len(crit) >= 2:
            crit[1]["score"] = "eight"                  # non-numeric   -> 0
        if len(crit) >= 3:
            crit.pop()                                  # missing       -> defaulted 0
        crit.append({"criterion_id": 99, "score": 10, "justification": "?", "evidence": "?"})
        if crit:
            crit.append(dict(crit[0]))                  # duplicate     -> ignored
        data["criteria"] = crit
        return "```json\n" + json.dumps(data) + "\n```"  # code fences   -> stripped
    return raw


# ------------------------------------------------------------------ nodes
def load_criteria(state: RunState) -> dict:
    criteria = db.get_active_criteria()   # reloaded at evaluation time (brief step 4)
    errors = db.validate_criteria(criteria)
    if errors:
        return {"fatal_error": " ".join(errors),
                "trace": _log(state, "load_criteria", "Criteria invalid: " + " ".join(errors))}
    db.update_run_status(state["rfp_run_id"], "RUNNING")
    return {"criteria": criteria, "idx": 0, "attempt": 0, "history": [], "evaluated": [],
            "skipped": [],
            "trace": _log(state, "load_criteria",
                          f"Loaded {len(criteria)} active criteria (weights total 100%).")}


def extract_document(state: RunState) -> dict:
    sup = state["suppliers_input"][state["idx"]]
    try:
        doc = extract_pdf_text(sup["pdf_bytes"], sup.get("filename", "document.pdf"))
    except DocumentError as exc:
        return {"doc_text": "", "doc_meta": {"error": str(exc)},
                "skipped": [*state["skipped"], {"supplier_name": sup["supplier_name"],
                                                "reason": str(exc)}],
                "trace": _log(state, "document_tool", f"{sup['supplier_name']}: SKIPPED - {exc}")}
    meta = {"filename": sup.get("filename"), "pages": doc.page_count, "chars": doc.char_count,
            "extractor": doc.extractor, "truncated": doc.truncated}
    return {"doc_text": doc.text, "doc_meta": meta, "attempt": 0, "history": [],
            "trace": _log(state, "document_tool",
                          f"{sup['supplier_name']}: extracted {doc.char_count:,} chars from "
                          f"{doc.page_count} pages via {doc.extractor}"
                          + (" (truncated)" if doc.truncated else ""))}


def evaluate_supplier(state: RunState) -> dict:
    sup = state["suppliers_input"][state["idx"]]
    attempt = state.get("attempt", 0) + 1
    req = EvaluationRequest(sup["supplier_name"], state["doc_text"], state["criteria"],
                            history=state.get("history", []))
    try:
        raw = run_evaluation(req, state["settings"])
    except LLMError as exc:
        return {"fatal_error": str(exc), "attempt": attempt,
                "trace": _log(state, "evaluation_agent", f"{sup['supplier_name']}: {exc}")}
    if state["idx"] == 0 and state.get("fault_mode", "none") != "none":
        raw = _inject_fault(raw, state["fault_mode"], attempt)
    return {"raw_output": raw, "attempt": attempt,
            "trace": _log(state, "evaluation_agent",
                          f"{sup['supplier_name']}: LLM response received "
                          f"(attempt {attempt}, {len(raw):,} chars)")}


def validate_output(state: RunState) -> dict:
    sup = state["suppliers_input"][state["idx"]]
    try:
        parsed = parse_llm_json(state["raw_output"])
    except JSONParseError as exc:
        if state["attempt"] <= LLM_JSON_RETRIES:
            return {"parse_error": str(exc),
                    "history": [*state.get("history", []),
                                {"output": state["raw_output"], "error": str(exc)}],
                    "trace": _log(state, "validation_tool",
                                  f"{sup['supplier_name']}: invalid JSON ({exc}) - "
                                  f"asking the model to repair")}
        scorecard = failed_scorecard(state["criteria"], sup["supplier_name"], str(exc))
        return {**_append_evaluated(state, sup, scorecard, state["raw_output"]),
                "parse_error": "",
                "trace": _log(state, "validation_tool",
                              f"{sup['supplier_name']}: invalid JSON after retries - "
                              f"all criteria defaulted to 0")}

    scorecard = normalize_scorecard(parsed, state["criteria"], sup["supplier_name"],
                                    state["doc_text"])
    n = len(scorecard.warnings)
    return {**_append_evaluated(state, sup, scorecard, state["raw_output"]), "parse_error": "",
            "trace": _log(state, "validation_tool",
                          f"{sup['supplier_name']}: schema valid, "
                          f"{n} normalisation warning{'s' if n != 1 else ''}")}


def _append_evaluated(state: RunState, sup: dict, scorecard, raw: str) -> dict:
    entry = {
        "supplier_name": sup["supplier_name"],
        "submission_date": sup["submission_date"],
        "experience_rating": float(sup["experience_rating"]),
        "source_file": sup.get("filename"),
        "document": state.get("doc_meta", {}),
        "llm_attempts": state["attempt"],
        "raw_llm_output": raw,
        "scorecard": scorecard,
    }
    return {"evaluated": [*state["evaluated"], entry]}


def next_supplier(state: RunState) -> dict:
    return {"idx": state["idx"] + 1, "attempt": 0, "history": [], "doc_text": "",
            "raw_output": ""}


def score_benchmark_rank(state: RunState) -> dict:
    ranked = rank_suppliers(state["evaluated"], state["criteria"])
    top = ranked["leaderboard"][0] if ranked["leaderboard"] else None
    msg = (f"Scored {len(ranked['leaderboard'])} suppliers; benchmarks computed; "
           f"rank 1 = {top['supplier_name']} (PPI {top['ppi']:.2f})" if top else "Nothing to rank")
    run_warnings = list(ranked["warnings"])
    for s in state["skipped"]:
        run_warnings.append(f"{s['supplier_name']} excluded: {s['reason']}")
    for row in ranked["leaderboard"]:
        run_warnings += [f"{row['supplier_name']}: {w}" for w in row["validation_warnings"]]

    settings: LLMSettings = state["settings"]
    result = {
        "rfp_run_id": state["rfp_run_id"],
        "created_at": state["created_at"],
        "completed_at": _now(),
        "status": "COMPLETED",
        "llm": {"provider": settings.provider, "model": settings.resolved_model(),
                "temperature": settings.temperature},
        "fault_injection": state.get("fault_mode", "none"),
        "criteria": [{k: c[k] for k in ("criterion_id", "name", "description", "weight",
                                        "max_score")} for c in state["criteria"]],
        "formulas": FORMULAS,
        "tie_break_rules": TIE_BREAK_RULES,
        "benchmarks": ranked["benchmarks"],
        "leaderboard": ranked["leaderboard"],
        "tie_breaks": ranked["tie_breaks"],
        "skipped_suppliers": state["skipped"],
        "warnings": run_warnings,
    }
    return {"result": result, "trace": _log(state, "ranking_tool", msg)}


def persist_results(state: RunState) -> dict:
    trace = _log(state, "persist", f"Saved run {state['rfp_run_id']} to SQLite "
                                   f"({len(state['result']['leaderboard'])} supplier rows)")
    result = {**state["result"], "agent_trace": trace}
    db.persist_run_results(state["rfp_run_id"], result)
    return {"result": result, "trace": trace}


# ------------------------------------------------------------------ routers
def route_after_criteria(state: RunState) -> str:
    return "abort" if state.get("fatal_error") else "extract_document"


def route_after_extract(state: RunState) -> str:
    return "next_supplier" if not state.get("doc_text") else "evaluate_supplier"


def route_after_evaluate(state: RunState) -> str:
    return "abort" if state.get("fatal_error") else "validate_output"


def route_after_validate(state: RunState) -> str:
    return "evaluate_supplier" if state.get("parse_error") else "next_supplier"


def route_after_next(state: RunState) -> str:
    if state["idx"] < len(state["suppliers_input"]):
        return "extract_document"
    return "score_benchmark_rank" if state["evaluated"] else "abort"


def build_graph():
    g = StateGraph(RunState)
    g.add_node("load_criteria", load_criteria)
    g.add_node("extract_document", extract_document)
    g.add_node("evaluate_supplier", evaluate_supplier)
    g.add_node("validate_output", validate_output)
    g.add_node("next_supplier", next_supplier)
    g.add_node("score_benchmark_rank", score_benchmark_rank)
    g.add_node("persist_results", persist_results)

    g.add_edge(START, "load_criteria")
    g.add_conditional_edges("load_criteria", route_after_criteria,
                            {"abort": END, "extract_document": "extract_document"})
    g.add_conditional_edges("extract_document", route_after_extract,
                            {"next_supplier": "next_supplier",
                             "evaluate_supplier": "evaluate_supplier"})
    g.add_conditional_edges("evaluate_supplier", route_after_evaluate,
                            {"abort": END, "validate_output": "validate_output"})
    g.add_conditional_edges("validate_output", route_after_validate,
                            {"evaluate_supplier": "evaluate_supplier",
                             "next_supplier": "next_supplier"})
    g.add_conditional_edges("next_supplier", route_after_next,
                            {"extract_document": "extract_document",
                             "score_benchmark_rank": "score_benchmark_rank", "abort": END})
    g.add_edge("score_benchmark_rank", "persist_results")
    g.add_edge("persist_results", END)
    return g.compile()


GRAPH = build_graph()


# ------------------------------------------------------------------ entry point
def run_rfp_evaluation(suppliers: list[dict], settings: LLMSettings, fault_mode: str = "none",
                       on_event: Optional[Callable[[dict], Any]] = None) -> dict:
    """Create a batch, run the graph, and return the complete run result.

    suppliers: [{supplier_name, submission_date (YYYY-MM-DD), experience_rating,
                 filename, pdf_bytes}]
    Raises RuntimeError (with run id) if the run fails; the run is marked FAILED in SQLite.
    """
    run_id = new_run_id()
    db.create_run(run_id, settings.provider, settings.resolved_model(), len(suppliers))
    state: RunState = {"rfp_run_id": run_id, "created_at": _now(), "settings": settings,
                       "fault_mode": fault_mode, "suppliers_input": suppliers, "trace": [
                           {"ts": _now(), "step": "batch",
                            "message": f"Created batch {run_id} with {len(suppliers)} suppliers"}]}
    if on_event:
        on_event(state["trace"][0])

    final: dict = dict(state)
    try:
        for update in GRAPH.stream(state, config={"recursion_limit": 500}, stream_mode="updates"):
            for _node, delta in update.items():
                if not delta:
                    continue
                final.update(delta)
                if on_event and delta.get("trace"):
                    on_event(delta["trace"][-1])
    except Exception as exc:
        db.update_run_status(run_id, "FAILED", [f"Unhandled error: {exc}"])
        raise RuntimeError(f"Run {run_id} failed: {exc}") from exc

    if final.get("fatal_error") or not final.get("result"):
        reason = final.get("fatal_error") or "No supplier documents could be evaluated."
        skipped = [f"{s['supplier_name']}: {s['reason']}" for s in final.get("skipped", [])]
        db.update_run_status(run_id, "FAILED", [reason, *skipped])
        raise RuntimeError(f"Run {run_id} failed: {reason}"
                           + (" | " + " | ".join(skipped) if skipped else ""))
    return final["result"]
