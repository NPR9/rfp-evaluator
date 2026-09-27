"""Agentic RFP Evaluation & Supplier Ranking - Streamlit UI.

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Agentic RFP Evaluator", page_icon="📑", layout="wide")

# Copy Streamlit Cloud secrets into env vars BEFORE importing config.
_SECRET_KEYS = ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY",
                "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
_secrets_found: list[str] = []
try:
    _flat = dict(st.secrets)
    for _v in list(_flat.values()):
        if hasattr(_v, "items"):
            _flat.update({k: v for k, v in _v.items() if k not in _flat})
    for _k in _SECRET_KEYS:
        if _k in _flat and str(_flat[_k]).strip():
            os.environ[_k] = str(_flat[_k]).strip()
            _secrets_found.append(_k)
except Exception:
    pass

from rfp import db  # noqa: E402
from rfp.agents.evaluation_agent import LLMSettings  # noqa: E402
from rfp.config import (DEFAULT_MODELS, EXPERIENCE_MAX, EXPERIENCE_MIN,  # noqa: E402
                        LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER)
from rfp.orchestrator import FAULT_MODES, run_rfp_evaluation  # noqa: E402

LLM_PROVIDER = os.getenv("LLM_PROVIDER", LLM_PROVIDER)
LLM_MODEL = os.getenv("LLM_MODEL", LLM_MODEL)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", LLM_BASE_URL)
from rfp.sample_suppliers import SAMPLE_SUPPLIERS, load_sample_suppliers  # noqa: E402
from rfp.tools.document_tool import DocumentError, extract_pdf_text  # noqa: E402

MAX_FILE_MB = 15
db.init_db()

if "result" not in st.session_state:
    st.session_state.result = None


# ====================================================================== sidebar
with st.sidebar:
    st.header("⚙️ LLM settings")
    providers = ["openai", "anthropic", "mock"]
    provider = st.selectbox(
        "Provider", providers,
        index=providers.index(LLM_PROVIDER) if LLM_PROVIDER in providers else 0,
        format_func={"openai": "OpenAI / OpenAI-compatible (Groq, OpenRouter…)",
                     "anthropic": "Anthropic Claude",
                     "mock": "Offline deterministic evaluator (no API key)"}.get,
    )
    model = st.text_input("Model", value=LLM_MODEL if provider == LLM_PROVIDER else "",
                          placeholder=DEFAULT_MODELS[provider],
                          help="Leave empty for the default shown.")
    base_url = ""
    api_key = ""
    if provider == "openai":
        base_url = st.text_input("Base URL (optional)", value=LLM_BASE_URL,
                                 placeholder="https://api.groq.com/openai/v1",
                                 help="Leave empty for api.openai.com")
    if provider != "mock":
        env_key = (os.getenv("OPENAI_API_KEY") if provider == "openai"
                   else os.getenv("ANTHROPIC_API_KEY")) or os.getenv("LLM_API_KEY", "")
        api_key = st.text_input("API key", type="password",
                                placeholder="Loaded from secrets" if env_key else "sk-…",
                                help="Stored only in this browser session.") or env_key
        if not api_key:
            st.warning("No API key found. Add one here or in Streamlit secrets.")
    else:
        st.info("The offline evaluator scores with transparent keyword signals. "
                "Use a real LLM for the actual qualitative judgement.")
    st.caption("temperature = 0 for reproducibility · secrets detected: "
               + (", ".join(_secrets_found) if _secrets_found else "none"))

    st.divider()
    st.header("🧪 Demo: validation / error cases")
    fault_mode = st.selectbox("Fault injection", list(FAULT_MODES),
                              format_func=lambda k: FAULT_MODES[k])
    st.caption("Corrupts the LLM output for the FIRST supplier so you can watch the "
               "Validation Tool and retry logic work.")

settings = LLMSettings(provider=provider, model=model.strip(), api_key=api_key,
                       base_url=base_url.strip())

st.title("📑 Agentic RFP Evaluation & Supplier Ranking")
st.caption("LLM judges proposal content · Python does all arithmetic, benchmarks, "
           "tie-breaks and ranking · SQLite stores every run")

tab_crit, tab_input, tab_board, tab_card, tab_run, tab_hist = st.tabs(
    ["1 · Criteria", "2 · Suppliers & Evaluate", "3 · Leaderboard", "4 · Scorecards",
     "5 · Run details", "History"])


# ====================================================================== 1. criteria
with tab_crit:
    st.subheader("Active evaluation criteria (loaded from SQLite)")
    all_criteria = db.get_all_criteria()
    active = [c for c in all_criteria if c["is_active"]]
    crit_errors = db.validate_criteria(all_criteria)
    if active:
        df_active = pd.DataFrame(active)[["criterion_id", "name", "description", "weight",
                                          "max_score"]]
        st.dataframe(df_active, hide_index=True, width="stretch",
                     column_config={"weight": st.column_config.NumberColumn("Weight (%)",
                                                                           format="%.0f%%"),
                                    "max_score": st.column_config.NumberColumn("Max score")})
    total = sum(c["weight"] for c in active)
    (st.success if not crit_errors else st.error)(
        f"{len(active)} active criteria · total weight {total:g}%"
        + ("" if not crit_errors else " · " + " ".join(crit_errors)))

    with st.expander("✏️ Edit criteria / weights (no prompt changes needed)"):
        edited = st.data_editor(
            pd.DataFrame(all_criteria), num_rows="dynamic", hide_index=True,
            width="stretch", key="crit_editor",
            column_config={
                "criterion_id": st.column_config.NumberColumn("ID", min_value=1, step=1,
                                                              required=True),
                "name": st.column_config.TextColumn("Name", required=True),
                "description": st.column_config.TextColumn("What the LLM inspects",
                                                           required=True),
                "weight": st.column_config.NumberColumn("Weight %", min_value=0,
                                                        max_value=100, required=True),
                "max_score": st.column_config.NumberColumn("Max score", min_value=1,
                                                           required=True),
                "is_active": st.column_config.CheckboxColumn("Active"),
            })
        c1, c2 = st.columns(2)
        if c1.button("💾 Save criteria", type="primary"):
            rows = edited.dropna(subset=["criterion_id", "name"]).to_dict("records")
            for r in rows:
                r["is_active"] = bool(r.get("is_active"))
                r["description"] = r.get("description") or ""
            ids = [int(r["criterion_id"]) for r in rows]
            try:
                if len(ids) != len(set(ids)):
                    raise ValueError("Criterion IDs must be unique.")
                db.save_criteria(rows)
                st.success("Criteria saved.")
                st.rerun()
            except ValueError as exc:
                st.error(f"Not saved: {exc}")
        if c2.button("↩️ Reset to sample criteria"):
            db.reset_criteria()
            st.rerun()


# ====================================================================== 2. input
def _guess_name(filename: str) -> str:
    for s in SAMPLE_SUPPLIERS:
        if s["filename"] == filename:
            return s["supplier_name"]
    stem = re.sub(r"\.pdf$", "", filename, flags=re.I)
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\b(rfp|proposal|response|final|v\d+)\b", "", stem, flags=re.I)
    return re.sub(r"\s+", " ", stem).strip() or filename


def _sample_meta(filename: str) -> dict:
    return next((s for s in SAMPLE_SUPPLIERS if s["filename"] == filename), {})


with tab_input:
    st.subheader("Supplier proposals")
    source = st.radio("Source", ["Upload PDFs", "Use the 4 bundled synthetic proposals"],
                      horizontal=True)

    suppliers: list[dict] = []
    if source == "Upload PDFs":
        files = st.file_uploader("Upload supplier RFP responses (PDF, multiple)", type=["pdf"],
                                 accept_multiple_files=True)
        if files:
            base = pd.DataFrame([{
                "file": f.name,
                "supplier_name": _guess_name(f.name),
                "submission_date": pd.to_datetime(_sample_meta(f.name).get("submission_date",
                                                                           date.today())),
                "experience_rating": float(_sample_meta(f.name).get("experience_rating", 3.0)),
            } for f in files])
            meta = st.data_editor(
                base, hide_index=True, width="stretch", key=f"meta_{len(files)}",
                disabled=["file"],
                column_config={
                    "supplier_name": st.column_config.TextColumn("Supplier name", required=True),
                    "submission_date": st.column_config.DateColumn("Submission date",
                                                                   format="YYYY-MM-DD",
                                                                   required=True),
                    "experience_rating": st.column_config.NumberColumn(
                        f"Experience rating ({EXPERIENCE_MIN:g}-{EXPERIENCE_MAX:g})",
                        min_value=EXPERIENCE_MIN, max_value=EXPERIENCE_MAX, step=0.5,
                        required=True),
                })
            by_name = {f.name: f for f in files}
            for _, row in meta.iterrows():
                f = by_name[row["file"]]
                suppliers.append({
                    "supplier_name": str(row["supplier_name"] or "").strip(),
                    "submission_date": (pd.to_datetime(row["submission_date"]).date().isoformat()
                                        if pd.notna(row["submission_date"]) else ""),
                    "experience_rating": row["experience_rating"],
                    "filename": f.name, "pdf_bytes": f.getvalue(),
                })
    else:
        samples = load_sample_suppliers()
        base = pd.DataFrame([{"file": s["filename"], "supplier_name": s["supplier_name"],
                              "submission_date": pd.to_datetime(s["submission_date"]),
                              "experience_rating": s["experience_rating"]} for s in samples])
        meta = st.data_editor(
            base, hide_index=True, width="stretch", key="sample_meta",
            disabled=["file"],
            column_config={
                "submission_date": st.column_config.DateColumn("Submission date",
                                                               format="YYYY-MM-DD"),
                "experience_rating": st.column_config.NumberColumn(
                    "Experience rating (0-5)", min_value=0.0, max_value=5.0, step=0.5),
            })
        st.caption("Tip: set two suppliers to the same values to see the tie-break rules in "
                   "action. Download the PDFs below to inspect them.")
        for s, (_, row) in zip(samples, meta.iterrows()):
            suppliers.append({
                "supplier_name": str(row["supplier_name"] or "").strip(),
                "submission_date": (pd.to_datetime(row["submission_date"]).date().isoformat()
                                    if pd.notna(row["submission_date"]) else ""),
                "experience_rating": row["experience_rating"],
                "filename": s["filename"], "pdf_bytes": s["pdf_bytes"],
            })
        cols = st.columns(len(samples))
        for col, s in zip(cols, samples):
            col.download_button(f"⬇️ {s['supplier_name']}", s["pdf_bytes"],
                                file_name=s["filename"], mime="application/pdf")

    # ------------------------------------------------ input validation
    errors: list[str] = []
    if suppliers:
        names = [s["supplier_name"].lower() for s in suppliers]
        for s in suppliers:
            label = s["filename"]
            if not s["supplier_name"]:
                errors.append(f"{label}: supplier name is required.")
            elif names.count(s["supplier_name"].lower()) > 1:
                errors.append(f"{label}: supplier name '{s['supplier_name']}' is duplicated.")
            if not s["submission_date"]:
                errors.append(f"{label}: submission date is required.")
            elif s["submission_date"] > date.today().isoformat():
                errors.append(f"{label}: submission date {s['submission_date']} is in the future.")
            er = s["experience_rating"]
            if er is None or pd.isna(er) or not (EXPERIENCE_MIN <= float(er) <= EXPERIENCE_MAX):
                errors.append(f"{label}: experience rating must be between "
                              f"{EXPERIENCE_MIN:g} and {EXPERIENCE_MAX:g}.")
            if len(s["pdf_bytes"]) > MAX_FILE_MB * 1024 * 1024:
                errors.append(f"{label}: file larger than {MAX_FILE_MB} MB.")
            else:
                try:
                    doc = extract_pdf_text(s["pdf_bytes"], label)
                    s["_pages"] = doc.page_count
                except DocumentError as exc:
                    errors.append(str(exc))
        errors = list(dict.fromkeys(errors))
        if len(suppliers) < 2:
            errors.append("Upload at least two supplier proposals so peers can be compared.")
        if crit_errors:
            errors.append("Fix the evaluation criteria first: " + " ".join(crit_errors))
        if provider != "mock" and not api_key:
            errors.append("Add an API key in the sidebar (or choose the offline evaluator).")

    if errors:
        st.error("**Please fix before evaluating:**\n\n" + "\n".join(f"- {e}" for e in errors))
    elif suppliers:
        st.success(f"{len(suppliers)} suppliers ready · "
                   + ", ".join(f"{s['supplier_name']} ({s.get('_pages', '?')} p.)"
                               for s in suppliers))

    if fault_mode != "none":
        st.warning(f"Fault injection active: {FAULT_MODES[fault_mode]}")

    if st.button("🚀 Evaluate suppliers", type="primary",
                 disabled=bool(errors) or not suppliers):
        payload = [{k: v for k, v in s.items() if not k.startswith("_")} for s in suppliers]
        with st.status("Running agentic evaluation…", expanded=True) as status:
            def on_event(e):
                status.write(f"`{e['step']}` — {e['message']}")
            try:
                result = run_rfp_evaluation(payload, settings, fault_mode, on_event=on_event)
                st.session_state.result = result
                status.update(label=f"Completed · {result['rfp_run_id']}", state="complete")
                st.success("Done. Open the **Leaderboard** tab.")
            except Exception as exc:
                status.update(label="Run failed", state="error")
                st.session_state.run_error = str(exc)
        if st.session_state.get("run_error"):
            st.error(st.session_state.pop("run_error"))


# ====================================================================== helpers
result = st.session_state.result


def _need_result():
    st.info("No run loaded yet. Evaluate suppliers in tab 2, or open a past run in History.")


# ====================================================================== 3. leaderboard
with tab_board:
    if not result:
        _need_result()
    else:
        st.subheader(f"Leaderboard · {result['rfp_run_id']}")
        lb = pd.DataFrame([{
            "Rank": r["final_rank"], "Supplier": r["supplier_name"],
            "Absolute score": r["absolute_score"], "PPI": r["ppi"],
            "Submission date": r["submission_date"],
            "Experience rating": r["experience_rating"],
            "Warnings": len(r["validation_warnings"]),
            "Why this position": r["rank_reason"],
        } for r in result["leaderboard"]])
        st.dataframe(lb, hide_index=True, width="stretch", column_config={
            "Absolute score": st.column_config.NumberColumn(format="%.2f",
                                                            help="Σ score/max × weight (0-100)"),
            "PPI": st.column_config.ProgressColumn("PPI", min_value=0, max_value=100,
                                                   format="%.2f",
                                                   help="Weighted avg of relative-performance %"),
        })
        top = result["leaderboard"][0]
        m1, m2, m3 = st.columns(3)
        m1.metric("Recommended supplier", top["supplier_name"])
        m2.metric("PPI", f"{top['ppi']:.2f}")
        m3.metric("Absolute score", f"{top['absolute_score']:.2f}")

        st.markdown("#### Criterion comparison (score / benchmark)")
        crit_names = [c["name"] for c in result["criteria"]]
        matrix = {r["supplier_name"]: {c["criterion_name"]: c["score"] for c in r["criteria"]}
                  for r in result["leaderboard"]}
        matrix["⭐ Benchmark"] = {b["criterion_name"]: b["benchmark_score"]
                                 for b in result["benchmarks"]}
        mdf = pd.DataFrame(matrix).T[crit_names]
        suppliers_only = pd.IndexSlice[[n for n in mdf.index if n != "⭐ Benchmark"], :]
        st.dataframe(mdf.style.highlight_max(axis=0, color="#2e7d3240", subset=suppliers_only)
                     .format("{:.1f}"),
                     width="stretch")
        if result["llm"]["provider"] == "mock":
            st.caption("⚠️ Scores produced by the offline deterministic evaluator, not an LLM.")


# ====================================================================== 4. scorecards
with tab_card:
    if not result:
        _need_result()
    else:
        names = [r["supplier_name"] for r in result["leaderboard"]]
        pick = st.selectbox("Supplier", names,
                            format_func=lambda n: f"#{names.index(n) + 1} · {n}")
        r = next(x for x in result["leaderboard"] if x["supplier_name"] == pick)
        a, b, c, d = st.columns(4)
        a.metric("Rank", r["final_rank"])
        b.metric("PPI", f"{r['ppi']:.2f}")
        c.metric("Absolute score", f"{r['absolute_score']:.2f}")
        d.metric("Validation warnings", len(r["validation_warnings"]))
        st.write(r["overall_summary"])

        sc = pd.DataFrame([{
            "Criterion": x["criterion_name"], "Weight %": x["weight"],
            "Score": x["score"], "Max": x["max_score"], "Benchmark": x["benchmark_score"],
            "Gap": x["gap"], "Relative %": x["relative_pct"],
            "Weighted pts": x["weighted_points"], "Leader": "⭐" if x["is_benchmark_leader"] else "",
            "Status": x["status"], "Evidence found in PDF": "✅" if x["evidence_verified"] else "⚠️",
        } for x in r["criteria"]])
        st.dataframe(sc, hide_index=True, width="stretch", column_config={
            "Relative %": st.column_config.NumberColumn(format="%.1f%%"),
            "Weighted pts": st.column_config.NumberColumn(format="%.2f"),
            "Gap": st.column_config.NumberColumn(format="%+.1f"),
        })
        st.caption(f"Absolute = Σ weighted pts = {r['absolute_score']:.2f} · "
                   f"PPI = Σ(relative % × weight) / Σ weight = {r['ppi']:.2f}")

        st.markdown("#### Evidence & justification")
        for x in r["criteria"]:
            with st.expander(f"{x['criterion_name']} — {x['score']:g}/{x['max_score']:g}"
                             f"  ({x['status']})"):
                st.markdown(f"**Justification:** {x['justification']}")
                st.markdown("**Evidence (quoted from the PDF):**")
                st.info(x["evidence"])
        if r["risks"]:
            st.markdown("#### Risks identified")
            for risk in r["risks"]:
                st.markdown(f"- {risk}")
        if r["validation_warnings"]:
            st.markdown("#### Validation warnings")
            for w in r["validation_warnings"]:
                st.warning(w)


# ====================================================================== 5. run details
with tab_run:
    if not result:
        _need_result()
    else:
        st.subheader("Run details")
        st.markdown(f"**RFP_RUN_ID:** `{result['rfp_run_id']}`")
        c2, c3, c4 = st.columns(3)
        c2.metric("Status", result["status"])
        c3.metric("LLM provider", f"{result['llm']['provider']}")
        c4.metric("Suppliers ranked", len(result["leaderboard"]))
        st.caption(f"Model: `{result['llm']['model']}` · temperature {result['llm']['temperature']}"
                   f" · created {result['created_at']} · completed {result['completed_at']}"
                   f" · fault injection: {result.get('fault_injection', 'none')}")

        st.download_button("⬇️ Download complete result (JSON)",
                           json.dumps(result, indent=2, ensure_ascii=False),
                           file_name=f"{result['rfp_run_id']}.json", mime="application/json",
                           type="primary")

        st.markdown("#### Tie-break explanation")
        st.markdown("Order applied: " + " → ".join(result["tie_break_rules"]))
        for t in result["tie_breaks"]:
            icon = "🟢" if t["decided_by"] == "PPI" else "🟠"
            st.markdown(f"{icon} **{t['decided_by']}** — {t['explanation']}")
        if all(t["decided_by"] == "PPI" for t in result["tie_breaks"]):
            st.caption("No ties in this run: every position was decided by PPI.")

        st.markdown("#### Formulas used")
        st.table(pd.DataFrame(result["formulas"].items(), columns=["Metric", "Formula"]))

        st.markdown(f"#### Warnings ({len(result['warnings'])})")
        if result["warnings"]:
            for w in result["warnings"]:
                st.warning(w)
        else:
            st.success("No validation warnings.")
        if result.get("skipped_suppliers"):
            st.error("Skipped: " + "; ".join(f"{s['supplier_name']} ({s['reason']})"
                                             for s in result["skipped_suppliers"]))

        with st.expander("🤖 Agent trace (orchestrator steps)"):
            st.dataframe(pd.DataFrame(result.get("agent_trace", [])), hide_index=True,
                         width="stretch")
        with st.expander("🧾 Raw LLM outputs (before validation)"):
            for r in result["leaderboard"]:
                st.markdown(f"**{r['supplier_name']}** — attempts: {r.get('llm_attempts')}")
                st.code(r.get("raw_llm_output", "")[:6000], language="json")
        with st.expander("🗄️ Stored rows in SQLite (supplier_results)"):
            st.dataframe(pd.DataFrame(db.get_supplier_rows(result["rfp_run_id"])),
                         hide_index=True, width="stretch")


# ====================================================================== history
with tab_hist:
    st.subheader("Past runs (SQLite · rfp_runs)")
    runs = db.list_runs()
    if not runs:
        st.info("No runs stored yet.")
    else:
        st.dataframe(pd.DataFrame(runs), hide_index=True, width="stretch")
        done = [r["rfp_run_id"] for r in runs if r["status"] == "COMPLETED"]
        if done:
            sel = st.selectbox("Open a completed run", done)
            if st.button("Load run"):
                st.session_state.result = db.get_run(sel)
                st.rerun()
    st.caption("Note: on Streamlit Community Cloud the SQLite file resets when the app restarts.")
