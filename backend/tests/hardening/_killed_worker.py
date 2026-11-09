from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from blueframe.config import Settings
from blueframe.db.engine import create_engine_and_session
from blueframe.jobs.repository import JobRepository


def main() -> int:
    marker = Path(sys.argv[1])
    settings = Settings(data_dir=Path(os.environ["BLUEFRAME_DATA_DIR"]))
    engine, session_factory = create_engine_and_session(settings)
    try:
        job = JobRepository(session_factory).claim_next("killed-worker", lease_seconds=30)
        marker.write_text("claimed" if job is not None else "empty", encoding="utf-8")
        time.sleep(120)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
