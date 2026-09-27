"""Create the SQLite database and seed the sample evaluation criteria.

    python scripts/init_db.py            # create if missing (keeps existing criteria)
    python scripts/init_db.py --reset    # restore the 5 sample criteria
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rfp import db  # noqa: E402
from rfp.config import DB_PATH  # noqa: E402

if __name__ == "__main__":
    db.init_db()
    if "--reset" in sys.argv:
        db.reset_criteria()
    print(f"Database ready: {DB_PATH}")
    for c in db.get_all_criteria():
        print(f"  [{c['criterion_id']}] {c['name']:<24} weight={c['weight']:>5g}%  "
              f"max={c['max_score']:g}  active={c['is_active']}")
