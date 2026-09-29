"""Legacy entrypoint — delegates to the topic-solver pipeline."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.pipeline import solve_problem as _pipeline_solve


async def solve_problem(db: Session | None, problem_text: str, subject_hint: str | None = None) -> dict:
    return await _pipeline_solve(db, problem_text, subject_hint)
