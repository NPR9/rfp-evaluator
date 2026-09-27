"""Run a full evaluation from the command line (no Streamlit) and export JSON.

    python scripts/run_cli.py                         # offline mock evaluator
    python scripts/run_cli.py --provider openai        # needs OPENAI_API_KEY
    python scripts/run_cli.py --provider anthropic     # needs ANTHROPIC_API_KEY
    python scripts/run_cli.py --fault malformed_values --out sample_output/validation_case.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rfp import db  # noqa: E402
from rfp.agents.evaluation_agent import LLMSettings  # noqa: E402
from rfp.orchestrator import FAULT_MODES, run_rfp_evaluation  # noqa: E402
from rfp.sample_suppliers import load_sample_suppliers  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "mock"),
                    choices=["mock", "openai", "anthropic"])
    ap.add_argument("--model", default=os.getenv("LLM_MODEL", ""))
    ap.add_argument("--base-url", default=os.getenv("LLM_BASE_URL", ""))
    ap.add_argument("--fault", default="none", choices=list(FAULT_MODES))
    ap.add_argument("--out", default="sample_output/sample_rfp_run.json")
    args = ap.parse_args()

    db.init_db()
    settings = LLMSettings(provider=args.provider, model=args.model, base_url=args.base_url)
    result = run_rfp_evaluation(load_sample_suppliers(), settings, fault_mode=args.fault,
                                on_event=lambda e: print(f"[{e['step']:>16}] {e['message']}"))

    print(f"\nRFP_RUN_ID: {result['rfp_run_id']}")
    print(f"{'Rank':<5}{'Supplier':<18}{'Absolute':>9}{'PPI':>9}  Submitted   Exp")
    for r in result["leaderboard"]:
        print(f"{r['final_rank']:<5}{r['supplier_name']:<18}{r['absolute_score']:>9.2f}"
              f"{r['ppi']:>9.2f}  {r['submission_date']}  {r['experience_rating']:g}")
    print("\nTie-break explanations:")
    for t in result["tie_breaks"]:
        print(" -", t["explanation"])
    if result["warnings"]:
        print(f"\n{len(result['warnings'])} warning(s):")
        for w in result["warnings"]:
            print(" -", w)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nJSON written to {out}")


if __name__ == "__main__":
    main()
