-- SQLite schema + seed (same as rfp/db.py; either can be used)
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

-- Sample criteria (weights total 100%)
INSERT OR IGNORE INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active) VALUES (1, 'Technical Capability', 'Architecture, integrations, scalability, technical fit', 30, 10, 1);
INSERT OR IGNORE INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active) VALUES (2, 'Implementation Plan', 'Timeline, milestones, staffing, risk plan', 20, 10, 1);
INSERT OR IGNORE INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active) VALUES (3, 'Commercial Value', 'Pricing clarity, total cost, assumptions', 20, 10, 1);
INSERT OR IGNORE INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active) VALUES (4, 'Security & Compliance', 'Controls, certifications, privacy, auditability', 20, 10, 1);
INSERT OR IGNORE INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active) VALUES (5, 'Support & Experience', 'Support model, similar projects, references', 10, 10, 1);
