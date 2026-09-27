"""Central configuration. Values can be overridden with environment variables
or (on Streamlit Community Cloud) with st.secrets, which app.py copies into env."""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("RFP_DB_PATH", ROOT_DIR / "rfp_evaluation.db"))
SAMPLE_PDF_DIR = ROOT_DIR / "sample_data" / "pdfs"
ERROR_CASE_DIR = ROOT_DIR / "sample_data" / "error_cases"

# Max characters of proposal text sent to the LLM (keeps prompt inside context limits).
MAX_DOC_CHARS = int(os.getenv("RFP_MAX_DOC_CHARS", "40000"))
# Minimum characters for a PDF to count as readable (scanned / empty PDFs fail this).
MIN_DOC_CHARS = int(os.getenv("RFP_MIN_DOC_CHARS", "200"))

# Experience rating scale entered by the user.
EXPERIENCE_MIN = 0.0
EXPERIENCE_MAX = 5.0

# PPI is rounded to this many decimals BEFORE sorting so floating-point noise
# (e.g. 87.50000000001 vs 87.5) can never change the ranking.
PPI_DECIMALS = 4

# Number of extra LLM attempts when the response is not parseable JSON.
LLM_JSON_RETRIES = int(os.getenv("RFP_LLM_JSON_RETRIES", "1"))

# Default LLM settings. provider: "openai" | "anthropic" | "mock"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "")          # empty -> provider default
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")    # e.g. https://api.groq.com/openai/v1

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "mock": "deterministic-keyword-v1",
}
