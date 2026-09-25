#!/usr/bin/env python3
"""OCR unindexed / empty-text PDFs and re-ingest them into the corpus.

Usage:
  python scripts/ocr_reingest.py
  python scripts/ocr_reingest.py --limit 20 --max-pages 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.corpus import CorpusChunk  # noqa: E402
from app.services.ocr import extract_pdf_path, write_sidecar  # noqa: E402
from app.services.rag import ingest_corpus  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR empty corpus PDFs and re-ingest")
    parser.add_argument("--limit", type=int, default=None, help="Max PDFs to OCR this run")
    parser.add_argument("--max-pages", type=int, default=12)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data" / "corpus")
    parser.add_argument("--force-ocr", action="store_true", help="Ignore existing sidecars")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        indexed = {row[0] for row in db.query(CorpusChunk.source_path).distinct().all() if row[0]}
        pdfs = sorted(args.corpus.resolve().rglob("*.pdf"))
        targets = [p for p in pdfs if str(p) not in indexed]
        if args.limit:
            targets = targets[: args.limit]

        print(f"Unindexed PDFs: {len(targets)} (of {len(pdfs)} total)")
        ok = 0
        empty = 0
        for i, path in enumerate(targets, start=1):
            print(f"[{i}/{len(targets)}] OCR {path.name} ...", flush=True)
            try:
                text, method = extract_pdf_path(
                    path,
                    use_ocr=True,
                    max_pages=args.max_pages,
                    prefer_sidecar=not args.force_ocr,
                )
                if len(text) < 40:
                    empty += 1
                    print(f"  -> still empty ({method})")
                    continue
                if method.startswith("ocr"):
                    write_sidecar(path, text)
                ok += 1
                print(f"  -> {method}, {len(text)} chars")
            except Exception as exc:  # noqa: BLE001
                print(f"  -> FAILED: {exc}")

        print(f"OCR done: ok={ok} empty={empty}. Re-ingesting unindexed...")
        result = ingest_corpus(db, corpus_dir=str(args.corpus), use_ocr=True, only_unindexed=True)
        print(result["message"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
