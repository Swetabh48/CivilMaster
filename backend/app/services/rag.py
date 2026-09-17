from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import using_sqlite
from app.models.corpus import CorpusChunk
from app.services.embeddings import embed_query, embed_texts
from app.services.ocr import chunk_text, extract_native_pdf_text, extract_pdf_path

logger = logging.getLogger(__name__)

SEMESTER_RE = re.compile(r"(\d)(rd|th|st|nd)\s*Semester", re.I)
FP_RE = re.compile(r"^\[fp:([a-f0-9]+)\]\n?")

MAX_PAGES_PER_PDF = 120
MAX_CHARS_PER_FILE = 350_000
SKIP_IF_SMALLER_THAN = 200  # bytes


def infer_meta(path: Path, corpus_root: Path) -> tuple[str | None, str | None]:
    try:
        rel = str(path.relative_to(corpus_root)).replace("\\", "/")
    except ValueError:
        rel = str(path).replace("\\", "/")
    semester = None
    m = SEMESTER_RE.search(rel)
    if m:
        semester = f"{m.group(1)}{m.group(2)} Semester"
    parts = Path(rel).parts
    subject = None
    if len(parts) >= 2:
        subject = parts[1] if "semester" in parts[0].lower() else parts[0]
    elif path.parent != corpus_root:
        subject = path.parent.name
    return semester, subject


def extract_pdf_text_limited(data: bytes, max_pages: int = MAX_PAGES_PER_PDF) -> str:
    """Native PDF text only (no OCR). Kept for callers that pass raw bytes."""
    text_out = extract_native_pdf_text(data, max_pages=max_pages)
    if len(text_out) > MAX_CHARS_PER_FILE:
        text_out = text_out[:MAX_CHARS_PER_FILE] + "\n[Truncated by character limit]"
    return text_out


def file_fingerprint(path: Path) -> str:
    st = path.stat()
    side = path.with_name(path.name + ".ocr.txt")
    side_tag = f"|ocr:{int(side.stat().st_mtime)}" if side.is_file() else ""
    payload = f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}{side_tag}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _stored_fingerprint(chunk: CorpusChunk | None) -> str | None:
    if not chunk or not chunk.content:
        return None
    m = FP_RE.match(chunk.content)
    return m.group(1) if m else None


def corpus_coverage(db: Session, corpus_dir: str | None = None) -> dict:
    """Report indexed vs on-disk corpus coverage (for admin stats)."""
    settings = get_settings()
    root = Path(corpus_dir or settings.resolved_corpus_dir()).resolve()
    files = sorted(list(root.rglob("*.pdf")) + list(root.rglob("*.txt")))
    indexed_paths = {
        row[0]
        for row in db.query(CorpusChunk.source_path).distinct().all()
        if row[0]
    }
    on_disk = {str(p.resolve()) for p in files}
    # Also match by normalized string forms used at ingest time
    on_disk_raw = {str(p) for p in files}
    indexed = len(indexed_paths)
    unindexed = [
        str(p)
        for p in files
        if str(p) not in indexed_paths and str(p.resolve()) not in indexed_paths
    ]
    sidecars = sum(1 for p in files if p.suffix.lower() == ".pdf" and p.with_name(p.name + ".ocr.txt").is_file())
    chunks = db.query(CorpusChunk).count()
    return {
        "chunks": chunks,
        "sources": indexed,
        "files_on_disk": len(files),
        "files_unindexed": len(unindexed),
        "ocr_sidecars": sidecars,
        "unindexed_sample": unindexed[:15],
    }


def ingest_corpus(
    db: Session,
    corpus_dir: str | None = None,
    *,
    limit_files: int | None = None,
    force: bool = False,
    use_ocr: bool | None = None,
    only_unindexed: bool = False,
) -> dict:
    settings = get_settings()
    root = Path(corpus_dir or settings.resolved_corpus_dir()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    ocr_on = settings.ocr_enabled if use_ocr is None else use_ocr
    ocr_pages = min(MAX_PAGES_PER_PDF, int(settings.ocr_max_pages))

    files = sorted(list(root.rglob("*.pdf")) + list(root.rglob("*.txt")))
    if only_unindexed:
        indexed_paths = {
            row[0] for row in db.query(CorpusChunk.source_path).distinct().all() if row[0]
        }
        files = [p for p in files if str(p) not in indexed_paths]
    if limit_files is not None:
        files = files[:limit_files]

    files_processed = 0
    files_skipped = 0
    files_failed = 0
    chunks_created = 0
    empty_text = 0
    ocr_used = 0

    for path in files:
        try:
            if path.stat().st_size < SKIP_IF_SMALLER_THAN:
                files_skipped += 1
                continue

            fp = file_fingerprint(path)
            existing = (
                db.query(CorpusChunk)
                .filter(CorpusChunk.source_path == str(path))
                .order_by(CorpusChunk.chunk_index.asc())
                .first()
            )
            stored_fp = _stored_fingerprint(existing)
            if existing and not force and stored_fp == fp:
                files_skipped += 1
                continue
            if existing and not force and stored_fp is None:
                # Legacy rows without fingerprint — skip unless force / OCR sidecar appeared
                side = path.with_name(path.name + ".ocr.txt")
                if not side.is_file():
                    files_skipped += 1
                    continue

            if path.suffix.lower() == ".pdf":
                content, method = extract_pdf_path(
                    path,
                    use_ocr=ocr_on,
                    max_pages=ocr_pages if ocr_on else MAX_PAGES_PER_PDF,
                    prefer_sidecar=True,
                )
                if method.startswith("ocr") or method == "sidecar":
                    ocr_used += 1
            else:
                content = path.read_text(encoding="utf-8", errors="ignore")
                method = "txt"

            if len(content) > MAX_CHARS_PER_FILE:
                content = content[:MAX_CHARS_PER_FILE] + "\n[Truncated by character limit]"

            pieces = chunk_text(content)
            if not pieces:
                empty_text += 1
                files_skipped += 1
                logger.info("Empty text after extract (%s): %s", method, path.name)
                continue

            db.query(CorpusChunk).filter(CorpusChunk.source_path == str(path)).delete()
            semester, subject = infer_meta(path, root)
            pieces[0] = f"[fp:{fp}]\n{pieces[0]}"
            vectors = embed_texts(pieces)
            for idx, (piece, vector) in enumerate(zip(pieces, vectors)):
                db.add(
                    CorpusChunk(
                        source_path=str(path),
                        source_name=path.name,
                        semester=semester,
                        subject=subject,
                        chunk_index=idx,
                        content=piece,
                        embedding=vector,
                    )
                )
                chunks_created += 1
            files_processed += 1
            db.commit()
            if files_processed % 10 == 0:
                logger.info(
                    "Ingest progress: processed=%s ocr=%s chunks=%s skipped=%s failed=%s",
                    files_processed,
                    ocr_used,
                    chunks_created,
                    files_skipped,
                    files_failed,
                )
        except Exception as exc:  # noqa: BLE001
            files_failed += 1
            logger.exception("Failed ingesting %s: %s", path, exc)
            db.rollback()

    if not using_sqlite():
        try:
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS corpus_chunks_embedding_idx "
                    "ON corpus_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
                )
            )
            db.commit()
        except Exception:
            db.rollback()

    total_chunks = db.query(CorpusChunk).count()
    return {
        "files_processed": files_processed,
        "files_skipped": files_skipped,
        "files_failed": files_failed,
        "files_empty_text": empty_text,
        "files_ocr_used": ocr_used,
        "chunks_created": chunks_created,
        "chunks_total": total_chunks,
        "message": (
            f"Ingested {files_processed} files ({chunks_created} chunks, OCR/sidecar {ocr_used}). "
            f"Skipped {files_skipped}, empty {empty_text}, failed {files_failed}. "
            f"Corpus now has {total_chunks} chunks."
        ),
    }


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def retrieve(db: Session, query: str, limit: int = 5) -> list[dict]:
    vector = embed_query(query)
    keywords = re.findall(r"[A-Za-z]{4,}", query.lower())
    keywords = [k for k in keywords if k not in {"find", "with", "from", "that", "this", "when", "have"}][:8]

    q = db.query(CorpusChunk).filter(CorpusChunk.embedding.is_not(None))
    if keywords:
        from sqlalchemy import or_

        q = q.filter(or_(*[CorpusChunk.content.ilike(f"%{k}%") for k in keywords[:5]]))
    candidates = q.limit(400).all()
    if len(candidates) < 20:
        candidates = (
            db.query(CorpusChunk)
            .filter(CorpusChunk.embedding.is_not(None))
            .limit(300)
            .all()
        )

    if using_sqlite() or candidates:
        scored: list[tuple[float, object]] = []
        kw_set = set(keywords)
        for chunk in candidates:
            emb = chunk.embedding
            if not emb:
                continue
            cos = _cosine(vector, emb)
            text_l = (chunk.content or "").lower()
            name_l = (chunk.source_name or "").lower()
            kw_hits = sum(1 for k in kw_set if k in text_l or k in name_l)
            score = 0.55 * cos + 0.45 * (kw_hits / max(len(kw_set), 1))
            if any(k in name_l for k in ("som", "strength", "mechanics", "concrete", "rcc", "steel", "soil")):
                score += 0.05
            scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = []
        for score, chunk in scored[:limit]:
            hits.append(
                {
                    "id": chunk.id,
                    "source_name": chunk.source_name,
                    "semester": chunk.semester,
                    "subject": chunk.subject,
                    "content": chunk.content[:1200],
                    "score": round(float(score), 4),
                }
            )
        if hits:
            return hits

    if not using_sqlite():
        try:
            stmt = (
                select(
                    CorpusChunk,
                    CorpusChunk.embedding.cosine_distance(vector).label("distance"),
                )
                .where(CorpusChunk.embedding.is_not(None))
                .order_by(text("distance"))
                .limit(limit)
            )
            rows = db.execute(stmt).all()
            hits = []
            for chunk, distance in rows:
                score = 1.0 / (1.0 + float(distance))
                hits.append(
                    {
                        "id": chunk.id,
                        "source_name": chunk.source_name,
                        "semester": chunk.semester,
                        "subject": chunk.subject,
                        "content": chunk.content[:1200],
                        "score": round(score, 4),
                    }
                )
            if hits:
                return hits
        except Exception as exc:  # noqa: BLE001
            logger.warning("pgvector retrieve failed: %s", exc)

    hits = []
    for chunk in (candidates or db.query(CorpusChunk).limit(limit).all())[:limit]:
        hits.append(
            {
                "id": chunk.id,
                "source_name": chunk.source_name,
                "semester": chunk.semester,
                "subject": chunk.subject,
                "content": chunk.content[:1200],
                "score": 0.3,
            }
        )
    return hits
