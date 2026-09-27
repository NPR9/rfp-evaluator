"""Prompt builder. Criteria are injected dynamically from SQLite, so changing
criteria or weights in the database never requires editing prompt code.

Note: weights are deliberately NOT sent to the LLM. The model judges each
criterion on its own merits; weighting is pure Python arithmetic afterwards."""
from __future__ import annotations

import json

SYSTEM_PROMPT = """You are an impartial procurement evaluator on an RFP scoring panel.
You assess ONE supplier proposal at a time against the evaluation criteria you are given.

Strict rules:
1. Use ONLY evidence that is present in the supplier document provided. Do not use outside
   knowledge about the supplier, do not assume, and do not reward claims that are not stated.
2. Return exactly one result for EVERY criterion listed - no more, no fewer - using the given criterion_id.
3. Each score must be a number between 0 and that criterion's max_score (inclusive).
   Missing or vague information must lower the score. If the document contains no evidence
   for a criterion, score 0 and set evidence to "No evidence found in document".
4. "evidence" must be a short verbatim quote (or quotes separated by " | ") copied from the document.
5. "justification" explains in 1-3 sentences why the evidence earns that score, including gaps.
6. Output a single JSON object only. No markdown, no code fences, no commentary."""

OUTPUT_SCHEMA_EXAMPLE = {
    "supplier_name": "<supplier name>",
    "criteria": [
        {
            "criterion_id": 1,
            "score": 0,
            "max_score": 10,
            "justification": "<why this score>",
            "evidence": "<verbatim quote from document>",
        }
    ],
    "risks": ["<risk or gap found in the proposal>"],
    "overall_summary": "<2-3 sentence neutral summary>",
}


def build_user_prompt(supplier_name: str, document_text: str, criteria: list[dict]) -> str:
    criteria_block = "\n".join(
        f"- criterion_id: {c['criterion_id']} | name: {c['name']} | "
        f"inspect: {c['description']} | score range: 0 to {c['max_score']:g}"
        for c in criteria
    )
    return f"""Evaluate the supplier proposal below.

SUPPLIER NAME: {supplier_name}

EVALUATION CRITERIA ({len(criteria)} active):
{criteria_block}

REQUIRED OUTPUT - a single JSON object with exactly this structure:
{json.dumps(OUTPUT_SCHEMA_EXAMPLE, indent=2)}

The "criteria" array must contain exactly {len(criteria)} objects, one for each criterion_id:
{[c['criterion_id'] for c in criteria]}.

SUPPLIER DOCUMENT (verbatim extracted text):
<<<DOCUMENT_START>>>
{document_text}
<<<DOCUMENT_END>>>

Return the JSON object now."""


def build_repair_prompt(previous_output: str, error: str) -> str:
    """Used on retry when the previous answer was not parseable JSON."""
    return (
        "Your previous answer could not be parsed as JSON "
        f"(error: {error}).\nPrevious answer (truncated):\n{previous_output[:1500]}\n\n"
        "Return ONLY the corrected JSON object, following every rule and the required structure."
    )
