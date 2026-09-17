from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user, require_admin
from app.database import get_db
from app.formulas.registry import list_formulas
from app.models.assignment import Assignment
from app.models.feedback import FeedbackItem
from app.models.user import User
from app.schemas.assignment import (
    CorpusSearchHit,
    CorpusSearchResponse,
    FeedbackCreate,
    FeedbackOut,
    FeedbackReview,
    IngestResponse,
)
from app.services.rag import corpus_coverage, ingest_corpus, retrieve

router = APIRouter(tags=["corpus"])


def _feedback_to_pair(item: FeedbackItem) -> dict:
    sol = item.solution_snapshot or {}
    if item.faculty_key:
        answer = item.faculty_key
    else:
        answer = sol.get("explanation") or str(sol.get("final_answers"))
    return {
        "id": item.id,
        "instruction": "Solve this B.Tech Civil Engineering problem with correct formulas.",
        "input": item.question_text or "",
        "output": answer,
        "is_correct_flag": item.is_correct,
    }


def _append_approved_pair(pair: dict) -> Path:
    settings = get_settings()
    path = settings.resolved_feedback_export_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(pair, ensure_ascii=False) + "\n")
    return path


@router.post("/corpus/ingest", response_model=IngestResponse)
def corpus_ingest(
    force: bool = Query(default=False),
    limit_files: int | None = Query(default=None, ge=1, le=5000),
    use_ocr: bool | None = Query(default=None),
    only_unindexed: bool = Query(default=False),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IngestResponse:
    result = ingest_corpus(
        db,
        force=force,
        limit_files=limit_files,
        use_ocr=use_ocr,
        only_unindexed=only_unindexed,
    )
    return IngestResponse(**result)


@router.get("/corpus/stats")
def corpus_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ = user
    return corpus_coverage(db)


@router.get("/corpus/search", response_model=CorpusSearchResponse)
def corpus_search(
    q: str = Query(min_length=3, max_length=2000),
    limit: int = Query(default=5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorpusSearchResponse:
    _ = user
    hits = retrieve(db, q, limit=limit)
    return CorpusSearchResponse(hits=[CorpusSearchHit(**h) for h in hits])


@router.get("/formulas")
def formulas(user: User = Depends(get_current_user)) -> dict:
    _ = user
    return {"formulas": list_formulas()}


@router.post("/feedback", response_model=FeedbackOut, status_code=201)
def create_feedback(
    payload: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackItem:
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == payload.assignment_id, Assignment.user_id == user.id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    item = FeedbackItem(
        user_id=user.id,
        assignment_id=assignment.id,
        is_correct=payload.is_correct,
        faculty_key=payload.faculty_key,
        notes=payload.notes,
        question_text=assignment.raw_text,
        solution_snapshot=assignment.solution,
        review_status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/admin/feedback", response_model=list[FeedbackOut])
def list_feedback(
    status_filter: str | None = Query(default="pending", alias="status"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[FeedbackItem]:
    q = db.query(FeedbackItem).order_by(FeedbackItem.created_at.desc())
    if status_filter:
        q = q.filter(FeedbackItem.review_status == status_filter)
    return q.limit(100).all()


@router.post("/admin/feedback/{feedback_id}/review", response_model=FeedbackOut)
def review_feedback(
    feedback_id: str,
    payload: FeedbackReview,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FeedbackItem:
    item = db.query(FeedbackItem).filter(FeedbackItem.id == feedback_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Feedback not found")
    item.review_status = payload.review_status
    item.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    if payload.review_status == "approved":
        try:
            _append_approved_pair(_feedback_to_pair(item))
        except OSError:
            pass
    return item


@router.get("/admin/training-export")
def training_export(
    persist: bool = Query(default=True),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Export approved feedback as instruction pairs for QLoRA."""
    items = (
        db.query(FeedbackItem)
        .filter(FeedbackItem.review_status == "approved")
        .order_by(FeedbackItem.created_at.asc())
        .all()
    )
    pairs = [_feedback_to_pair(item) for item in items]
    export_path = None
    if persist and pairs:
        settings = get_settings()
        path = settings.resolved_feedback_export_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Rewrite full snapshot as JSON (and keep jsonl append trail)
        snapshot = path.with_suffix(".json")
        snapshot.write_text(
            json.dumps({"count": len(pairs), "pairs": pairs}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        export_path = str(snapshot)
    return {"count": len(pairs), "pairs": pairs, "export_path": export_path}


@router.post("/admin/curate-training")
def curate_training(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Merge seed + approved feedback into training/datasets/civilmaster_sft.jsonl."""
    import subprocess
    import sys

    settings = get_settings()
    root = Path(__file__).resolve().parents[3]
    script = root / "training" / "scripts" / "curate_dataset.py"

    items = (
        db.query(FeedbackItem)
        .filter(FeedbackItem.review_status == "approved")
        .order_by(FeedbackItem.created_at.asc())
        .all()
    )
    pairs = [_feedback_to_pair(item) for item in items]
    approved = settings.resolved_feedback_export_path().with_suffix(".json")
    approved.parent.mkdir(parents=True, exist_ok=True)
    approved.write_text(
        json.dumps({"count": len(pairs), "pairs": pairs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    cmd = [sys.executable, str(script), "--approved", str(approved)]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root), check=False)
    return {
        "ok": proc.returncode == 0,
        "count": len(pairs),
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-1000:],
        "approved_json": str(approved),
    }
