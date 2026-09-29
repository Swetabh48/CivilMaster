"""Solution v2 schema — one Solution, always a list of ProblemSolution."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.problem_spec import ProblemSpec, Quantity


class Step(BaseModel):
    title: str
    formula_latex: str
    substitution_latex: str
    result: Quantity
    clause: str | None = None  # e.g. "IS 800:2007 Cl. 10.3.3"
    note: str | None = None


class Check(BaseModel):
    name: str
    passed: bool
    detail: str


class Answer(BaseModel):
    name: str
    value: Quantity
    note: str | None = None


class Diagram(BaseModel):
    kind: str
    svg: str
    caption: str
    has_dxf: bool = False


class Source(BaseModel):
    source_name: str
    excerpt: str | None = None
    score: float | None = None


class Provenance(BaseModel):
    solver_id: str | None = None
    solver_version: str | None = None
    llm_model: str | None = None
    prompt_version: str | None = None
    grounding_ok: bool | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ProblemSolution(BaseModel):
    spec: ProblemSpec | None = None
    status: Literal["verified", "unverified", "needs_input", "unsupported"]
    given: list[tuple[str, Quantity]] = Field(default_factory=list)
    to_find: list[str] = Field(default_factory=list)
    diagrams: list[Diagram] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    answers: list[Answer] = Field(default_factory=list)
    narrative_md: str = ""
    sources: list[Source] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)


class Solution(BaseModel):
    schema_version: Literal[2] = 2
    problems: list[ProblemSolution]
