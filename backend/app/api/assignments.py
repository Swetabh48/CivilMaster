from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.assignment import Assignment
from app.models.user import User
from app.schemas.assignment import AssignmentOut, TextSolveRequest
from app.services.ocr import extract_text, is_allowed_file
from app.services.solver import solve_problem

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("", response_model=list[AssignmentOut])
def list_assignments(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Assignment]:
    return (
        db.query(Assignment)
        .filter(Assignment.user_id == user.id)
        .order_by(Assignment.created_at.desc())
        .limit(50)
        .all()
    )


@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment(
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Assignment:
    item = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id, Assignment.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return item


@router.post("/solve-text", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def solve_text(
    payload: TextSolveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Assignment:
    assignment = Assignment(
        user_id=user.id,
        title=payload.title,
        raw_text=payload.text,
        subject=payload.subject,
        status="processing",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    try:
        solution = await solve_problem(db, payload.text, payload.subject)
        assignment.solution = solution
        assignment.subject = solution.get("subject") or payload.subject
        assignment.status = "done"
    except Exception as exc:  # noqa: BLE001
        assignment.status = "failed"
        assignment.error_message = str(exc)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/upload", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def upload_assignment(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    subject: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Assignment:
    settings = get_settings()
    if not file.filename or not is_allowed_file(file.filename, file.content_type):
        raise HTTPException(
            status_code=400,
            detail="Only PDF, PNG, JPG, WEBP, or TXT files are allowed",
        )

    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_upload_mb} MB limit")

    upload_root = Path(settings.resolved_upload_dir())
    upload_root.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix.lower()
    stored_name = f"{user.id}_{uuid.uuid4().hex}{ext}"
    dest = upload_root / stored_name
    async with aiofiles.open(dest, "wb") as out:
        await out.write(data)

    try:
        raw_text = extract_text(file.filename, data, file.content_type)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}") from exc

    if not raw_text.strip():
        raw_text = (
            f"[Image/PDF with little extractable text: {file.filename}]\n"
            "Please also paste the question text if OCR could not read it."
        )

    assignment = Assignment(
        user_id=user.id,
        title=title or file.filename,
        original_filename=file.filename,
        file_path=str(dest),
        content_type=file.content_type,
        raw_text=raw_text,
        subject=subject,
        status="processing",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    try:
        solution = await solve_problem(db, raw_text, subject)
        assignment.solution = solution
        assignment.subject = solution.get("subject") or subject
        assignment.status = "done"
    except Exception as exc:  # noqa: BLE001
        assignment.status = "failed"
        assignment.error_message = str(exc)
    db.commit()
    db.refresh(assignment)
    return assignment
