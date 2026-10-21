"""Runs one live analysis in a process of its own, so that a test can stop it for real (a kill, or the FAULTLINE_FAULT exit).

    python -m tests.integration.child_analyse <database> <sandbox port> <image> <store folder> <analysis project id>
"""
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    db, port, image, store_root, apid = argv
    from faultline.analysis.live import run_live_analysis
    from faultline.sandbox.client import SandboxClient
    from faultline.storage.db import connect
    from faultline.storage.store import Store
    from tests.conftest import TOKEN
    conn = connect(db)
    run_live_analysis(conn, SandboxClient(port=int(port), token=TOKEN, timeout=900), image, Store(Path(store_root)), apid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
