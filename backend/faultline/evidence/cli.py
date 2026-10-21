"""python -m faultline.evidence.cli [--db PATH] [--dry-run] [--allow-loss]: rebuild the evidence rows from the objects and print the report."""
import argparse
import json
import sys
from pathlib import Path

from ..core.config import Settings
from ..storage.db import connect
from ..storage.migrate import migrate
from .rebuild import rebuild


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true", help="do everything, check the result, then roll back")
    p.add_argument("--allow-loss", action="store_true", help="accept losing rows that have no object (only for a database written with the store off)")
    a = p.parse_args(argv)
    db = a.db or Settings.from_env().db_path
    conn = connect(db)
    migrate(conn)
    report = rebuild(conn, dry_run=a.dry_run, allow_loss=a.allow_loss)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] in ("REBUILT", "DRY_RUN_OK") else 1


if __name__ == "__main__":
    sys.exit(main())
