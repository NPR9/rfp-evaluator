"""Metadata for the four bundled synthetic supplier PDFs (used by the
'Load sample suppliers' button and the CLI). Experience ratings are on a 0-5 scale
and represent the procurement team's historical rating of each supplier."""
from __future__ import annotations

from rfp.config import SAMPLE_PDF_DIR

SAMPLE_SUPPLIERS = [
    {"supplier_name": "Apex Systems", "filename": "Apex_Systems_Proposal.pdf",
     "submission_date": "2026-09-10", "experience_rating": 4.0},
    {"supplier_name": "BrightPath Tech", "filename": "BrightPath_Tech_Proposal.pdf",
     "submission_date": "2026-09-08", "experience_rating": 2.0},
    {"supplier_name": "NexaWorks", "filename": "NexaWorks_Proposal.pdf",
     "submission_date": "2026-09-09", "experience_rating": 4.0},
    {"supplier_name": "Orbit Digital", "filename": "Orbit_Digital_Proposal.pdf",
     "submission_date": "2026-09-11", "experience_rating": 4.5},
]


def load_sample_suppliers() -> list[dict]:
    return [s | {"pdf_bytes": (SAMPLE_PDF_DIR / s["filename"]).read_bytes()}
            for s in SAMPLE_SUPPLIERS]
