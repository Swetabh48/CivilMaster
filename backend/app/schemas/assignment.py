from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AssignmentOut(BaseModel):
    id: str
    title: str
    original_filename: str | None
    subject: str | None
    status: str
    raw_text: str | None
    solution: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TextSolveRequest(BaseModel):
    title: str = "Text assignment"
    text: str = Field(min_length=10, max_length=50000)
    subject: str | None = None


class FeedbackCreate(BaseModel):
    assignment_id: str
    is_correct: bool
    faculty_key: str | None = None
    notes: str | None = None


class FeedbackOut(BaseModel):
    id: str
    assignment_id: str | None
    is_correct: bool
    faculty_key: str | None
    notes: str | None
    review_status: str
    question_text: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackReview(BaseModel):
    review_status: str = Field(pattern="^(approved|rejected)$")


class IngestResponse(BaseModel):
    files_processed: int
    chunks_created: int
    message: str
    files_skipped: int = 0
    files_failed: int = 0
    files_empty_text: int = 0
    files_ocr_used: int = 0
    chunks_total: int = 0


class CorpusSearchHit(BaseModel):
    id: str
    source_name: str
    semester: str | None
    subject: str | None
    content: str
    score: float


class CorpusSearchResponse(BaseModel):
    hits: list[CorpusSearchHit]
