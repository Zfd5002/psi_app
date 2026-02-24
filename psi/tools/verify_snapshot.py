from __future__ import annotations

"""CLI wrapper: verify a persisted PSI DI DecisionSnapshot deterministically (read-only).

Implementation lives in `psi.services.di.verify` so web + CLI share the exact same logic.
"""

import argparse
from typing import Any

from psi.core.db import get_db
from psi.core.utils import stable_json_dumps
from psi.services.di.verify import verify_snapshot


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m psi.tools.verify_snapshot",
        description="Verify a persisted PSI DI DecisionSnapshot deterministically (read-only).",
    )
    ap.add_argument("--snapshot-id", required=True, type=int, help="DecisionSnapshot id")
    ap.add_argument("--db", default="", help="Optional path to sqlite db (default uses PSI_DB_PATH or psi/psi.sqlite)")
    ap.add_argument("--debug", action="store_true", help="Include deterministic structural debug deltas when drift is detected")
    args = ap.parse_args()

    with get_db(args.db.strip() or None, ensure=True) as db:
        report = verify_snapshot(db=db, snapshot_id=int(args.snapshot_id), debug=bool(args.debug))
        print(stable_json_dumps(report))


if __name__ == "__main__":
    main()
