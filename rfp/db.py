"""SQLite persistence layer.

Tables (minimum fields from the brief + a few audit columns):
    evaluation_criteria(criterion_id, name, description, weight, max_score, is_active)
    rfp_runs(rfp_run_id, created_at, status, ...audit)
    supplier_results(rfp_run_id, supplier_name, submission_date, experience_rating,
                     absolute_score, ppi, final_rank, result_json)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from rfp.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id  INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL UNIQUE,
    description   TEXT    NOT NULL,
    weight        REAL    NOT NULL CHECK (weight >= 0 AND weight <= 100),
    max_score     REAL    NOT NULL DEFAULT 10 CHECK (max_score > 0),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id         TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('CREATED','RUNNING','COMPLETED','FAILED')),
    completed_at       TEXT,
    llm_provider       TEXT,
    llm_model          TEXT,
    supplier_count     INTEGER,
    criteria_snapshot  TEXT,   -- JSON: criteria + weights used for this run
    warnings_json      TEXT,   -- JSON list of run-level warnings
    run_json           TEXT    -- JSON: complete exported result
);

CREATE TABLE IF NOT EXISTS supplier_results (
    rfp_run_id         TEXT    NOT NULL REFERENCES rfp_runs(rfp_run_id) ON DELETE CASCADE,
    supplier_name      TEXT    NOT NULL,
    submission_date    TEXT    NOT NULL,
    experience_rating  REAL    NOT NULL,
    absolute_score     REAL,
    ppi                REAL,
    final_rank         INTEGER,
    result_json        TEXT,
    PRIMARY KEY (rfp_run_id, supplier_name)
);
"""

SEED_CRITERIA = [
    # (id, name, description (= what the LLM should inspect), weight %, max_score, active)
    (1, "Technical Capability",
     "Architecture, integrations, scalability, technical fit", 30, 10, 1),
    (2, "Implementation Plan",
     "Timeline, milestones, staffing, risk plan", 20, 10, 1),
    (3, "Commercial Value",
     "Pricing clarity, total cost, assumptions", 20, 10, 1),
    (4, "Security & Compliance",
     "Controls, certifications, privacy, auditability", 20, 10, 1),
    (5, "Support & Experience",
     "Support model, similar projects, references", 10, 10, 1),
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None, seed: bool = True) -> None:
    """Create tables and (if the criteria table is empty) insert sample criteria."""
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)
        if seed:
            count = conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0]
            if count == 0:
                conn.executemany(
                    "INSERT INTO evaluation_criteria "
                    "(criterion_id, name, description, weight, max_score, is_active) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    SEED_CRITERIA,
                )


def reset_criteria(db_path: Path | str | None = None) -> None:
    """Restore the five sample criteria (used by the UI 'Reset' button)."""
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM evaluation_criteria")
        conn.executemany(
            "INSERT INTO evaluation_criteria VALUES (?, ?, ?, ?, ?, ?)", SEED_CRITERIA
        )


# ---------------------------------------------------------------- criteria
def get_all_criteria(db_path: Path | str | None = None) -> list[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM evaluation_criteria ORDER BY criterion_id"
        ).fetchall()
    return [dict(r) | {"is_active": bool(r["is_active"])} for r in rows]


def get_active_criteria(db_path: Path | str | None = None) -> list[dict]:
    return [c for c in get_all_criteria(db_path) if c["is_active"]]


def validate_criteria(criteria: list[dict]) -> list[str]:
    """Return a list of errors; empty list means the active criteria are usable."""
    errors: list[str] = []
    active = [c for c in criteria if c.get("is_active")]
    if not active:
        errors.append("At least one criterion must be active.")
        return errors
    total = round(sum(float(c["weight"]) for c in active), 6)
    if abs(total - 100.0) > 0.01:
        errors.append(f"Active criteria weights must total 100% (currently {total:g}%).")
    names = [str(c["name"]).strip().lower() for c in criteria]
    if len(names) != len(set(names)):
        errors.append("Criterion names must be unique.")
    for c in active:
        if not str(c.get("name", "")).strip():
            errors.append("Every active criterion needs a name.")
        if float(c["max_score"]) <= 0:
            errors.append(f"'{c['name']}': max_score must be > 0.")
        if float(c["weight"]) < 0:
            errors.append(f"'{c['name']}': weight cannot be negative.")
    return errors


def save_criteria(criteria: list[dict], db_path: Path | str | None = None) -> None:
    """Replace the criteria table with the edited list (validated first)."""
    errors = validate_criteria(criteria)
    if errors:
        raise ValueError(" ".join(errors))
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM evaluation_criteria")
        for c in criteria:
            conn.execute(
                "INSERT INTO evaluation_criteria "
                "(criterion_id, name, description, weight, max_score, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (int(c["criterion_id"]), str(c["name"]).strip(), str(c["description"]).strip(),
                 float(c["weight"]), float(c["max_score"]), 1 if c["is_active"] else 0),
            )


# ---------------------------------------------------------------- runs
def create_run(rfp_run_id: str, provider: str, model: str, supplier_count: int,
               db_path: Path | str | None = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO rfp_runs (rfp_run_id, created_at, status, llm_provider, llm_model, "
            "supplier_count) VALUES (?, ?, 'CREATED', ?, ?, ?)",
            (rfp_run_id, _utcnow(), provider, model, supplier_count),
        )


def update_run_status(rfp_run_id: str, status: str, warnings: list[str] | None = None,
                      db_path: Path | str | None = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE rfp_runs SET status = ?, warnings_json = COALESCE(?, warnings_json), "
            "completed_at = CASE WHEN ? IN ('COMPLETED','FAILED') THEN ? ELSE completed_at END "
            "WHERE rfp_run_id = ?",
            (status, json.dumps(warnings) if warnings is not None else None,
             status, _utcnow(), rfp_run_id),
        )


def persist_run_results(rfp_run_id: str, run_result: dict,
                        db_path: Path | str | None = None) -> None:
    """Write every supplier row + the full run JSON in ONE transaction."""
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM supplier_results WHERE rfp_run_id = ?", (rfp_run_id,))
        for s in run_result["leaderboard"]:
            conn.execute(
                "INSERT INTO supplier_results (rfp_run_id, supplier_name, submission_date, "
                "experience_rating, absolute_score, ppi, final_rank, result_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rfp_run_id, s["supplier_name"], s["submission_date"], s["experience_rating"],
                 s["absolute_score"], s["ppi"], s["final_rank"],
                 json.dumps(s, ensure_ascii=False)),
            )
        conn.execute(
            "UPDATE rfp_runs SET status = 'COMPLETED', completed_at = ?, criteria_snapshot = ?, "
            "warnings_json = ?, run_json = ? WHERE rfp_run_id = ?",
            (_utcnow(), json.dumps(run_result["criteria"]),
             json.dumps(run_result["warnings"]),
             json.dumps(run_result, ensure_ascii=False), rfp_run_id),
        )


def list_runs(limit: int = 50, db_path: Path | str | None = None) -> list[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT rfp_run_id, created_at, status, completed_at, llm_provider, llm_model, "
            "supplier_count FROM rfp_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_run(rfp_run_id: str, db_path: Path | str | None = None) -> dict | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT run_json FROM rfp_runs WHERE rfp_run_id = ?", (rfp_run_id,)
        ).fetchone()
    if row is None or row["run_json"] is None:
        return None
    return json.loads(row["run_json"])


def get_supplier_rows(rfp_run_id: str, db_path: Path | str | None = None) -> list[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT rfp_run_id, supplier_name, submission_date, experience_rating, "
            "absolute_score, ppi, final_rank FROM supplier_results "
            "WHERE rfp_run_id = ? ORDER BY final_rank", (rfp_run_id,)
        ).fetchall()
    return [dict(r) for r in rows]
