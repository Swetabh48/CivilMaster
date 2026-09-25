"""One-shot local bootstrap: init DB + ingest seed corpus."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal, init_db  # noqa: E402
from app.services.rag import ingest_corpus  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        result = ingest_corpus(db)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
