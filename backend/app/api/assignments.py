from __future__ import annotations

import re
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.assignment import Assignment
from app.models.user import User
from app.schemas.assignment import AssignmentOut, TextSolveRequest
from app.services.export_docs import build_solution_docx, build_solution_dxf, build_solution_pdf
from app.services.llm import answer_solution_question
from app.services.ocr import extract_text, is_allowed_file
from app.services.solver import solve_problem

router = APIRouter(prefix="/assignments", tags=["assignments"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


class ChatResponse(BaseModel):
    reply: str


def _owned_assignment(db: Session, assignment_id: str, user_id: str) -> Assignment:
    item = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id, Assignment.user_id == user_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return item


def _safe_filename(title: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (title or "solution").strip())[:60] or "solution"
    return f"{base}.{ext}"


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


@router.get("/{assignment_id}/export.pdf")
def export_pdf(
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    item = _owned_assignment(db, assignment_id, user.id)
    sol = item.solution or {}
    pdf = build_solution_pdf(
        title=item.title or "Assignment",
        question=item.raw_text or "",
        explanation=sol.get("explanation") or "",
        answers=sol.get("final_answers") or [],
        diagram_svg=sol.get("diagram_svg"),
        subject=item.subject,
    )
    name = _safe_filename(item.title or "solution", "pdf")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/{assignment_id}/export.docx")
def export_docx(
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    item = _owned_assignment(db, assignment_id, user.id)
    sol = item.solution or {}
    docx = build_solution_docx(
        title=item.title or "Assignment",
        question=item.raw_text or "",
        explanation=sol.get("explanation") or "",
        answers=sol.get("final_answers") or [],
        subject=item.subject,
        diagram_svg=sol.get("diagram_svg"),
    )
    name = _safe_filename(item.title or "solution", "docx")
    return Response(
        content=docx,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/{assignment_id}/export.dxf")
def export_dxf(
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    item = _owned_assignment(db, assignment_id, user.id)
    sol = item.solution or {}
    dxf = build_solution_dxf(
        diagram_type=sol.get("diagram_type"),
        variables=sol.get("variables_extracted") or {},
    )
    name = _safe_filename(item.title or "drawing", "dxf")
    return Response(
        content=dxf,
        media_type="application/dxf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/{assignment_id}/chat", response_model=ChatResponse)
async def chat_about_solution(
    assignment_id: str,
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    item = _owned_assignment(db, assignment_id, user.id)
    if item.status != "done" or not item.solution:
        raise HTTPException(status_code=400, detail="Solution is not ready yet")
    reply = await answer_solution_question(
        payload.message,
        problem_text=item.raw_text or "",
        solution=item.solution,
    )
    return ChatResponse(reply=reply)
