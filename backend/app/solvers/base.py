"""Shared solver types and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, NotRequired, TypedDict


class NeedsInput(Exception):
    """Raised when required inputs are missing — never guess defaults."""

    def __init__(self, missing: list[str]):
        self.missing = list(missing)
        msg = f"Missing required inputs: {', '.join(self.missing)}"
        super().__init__(msg)


class StepDict(TypedDict):
    title: str
    formula: str
    substitution: str
    result_value: float | int | str | None
    result_unit: str
    clause: NotRequired[str | None]


class AnswerDict(TypedDict):
    label: str
    value: float | int | str
    unit: str


class CheckDict(TypedDict):
    name: str
    passed: bool
    detail: str


GivenItem = tuple[str, float | int | str, str]

Status = Literal["verified", "needs_input", "unsupported"]


@dataclass
class SolverResult:
    steps: list[StepDict] = field(default_factory=list)
    answers: list[AnswerDict] = field(default_factory=list)
    checks: list[CheckDict] = field(default_factory=list)
    drawing_data: dict[str, Any] | None = None
    subject: str = ""
    status: Status = "verified"
    missing_inputs: list[str] = field(default_factory=list)
    given: list[GivenItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "subject": self.subject,
            "steps": list(self.steps),
            "answers": list(self.answers),
            "checks": list(self.checks),
            "drawing_data": self.drawing_data,
            "missing_inputs": list(self.missing_inputs),
            "given": list(self.given),
        }


def require(spec: dict[str, Any], *keys: str) -> None:
    """Raise NeedsInput listing every missing key."""
    missing = [k for k in keys if spec.get(k) is None]
    if missing:
        raise NeedsInput(missing)


def empty_result(
    *,
    status: Status,
    subject: str = "",
    missing: list[str] | None = None,
    given: list[GivenItem] | None = None,
) -> dict[str, Any]:
    return SolverResult(
        status=status,
        subject=subject,
        missing_inputs=list(missing or []),
        given=list(given or []),
    ).to_dict()


def step(
    title: str,
    formula: str,
    substitution: str,
    result_value: float | int | str | None,
    result_unit: str = "",
    clause: str | None = None,
) -> StepDict:
    d: StepDict = {
        "title": title,
        "formula": formula,
        "substitution": substitution,
        "result_value": result_value,
        "result_unit": result_unit,
    }
    if clause is not None:
        d["clause"] = clause
    return d


def answer(label: str, value: float | int | str, unit: str = "") -> AnswerDict:
    return {"label": label, "value": value, "unit": unit}


def check(name: str, passed: bool, detail: str) -> CheckDict:
    return {"name": name, "passed": passed, "detail": detail}
