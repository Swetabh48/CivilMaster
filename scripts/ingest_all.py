"""Ingest all corpus PDFs into the DB (incremental)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from app.core.config import get_settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.services.rag import ingest_corpus  # noqa: E402


def main() -> None:
    get_settings.cache_clear()
    init_db()
    db = SessionLocal()
    try:
        result = ingest_corpus(db, force=False)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
