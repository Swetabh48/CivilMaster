"""Pipeline orchestrator — parse → solve → draw → narrate → legacy Solution dict."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.drawing.render import diagram_from_solver
from app.pipeline.parse_nl import try_parse_problem
from app.services.problem_prep import (
    detailing_guidance,
    is_assignment_pack,
    split_problems,
    strip_boilerplate,
)
from app.solvers import solve_topic


def _narrate_from_solver(question: str, result: dict[str, Any]) -> str:
    lines = ["## Worked solution", ""]
    if result.get("given"):
        lines.append("**Given:**")
        for g in result["given"]:
            if isinstance(g, (list, tuple)) and len(g) >= 3:
                lines.append(f"- {g[0]} = {g[1]} {g[2]}")
            elif isinstance(g, (list, tuple)) and len(g) == 2:
                lines.append(f"- {g[0]} = {g[1]}")
        lines.append("")
    for i, step in enumerate(result.get("steps") or [], start=1):
        title = step.get("title") or step.get("name") or f"Step {i}"
        lines.append(f"**Step {i}: {title}**")
        if step.get("formula") or step.get("expression"):
            lines.append(f"- Formula: `{step.get('formula') or step.get('expression')}`")
        if step.get("substitution"):
            lines.append(f"- Substitution: {step['substitution']}")
        elif step.get("inputs"):
            lines.append(
                "- Substitution: "
                + ", ".join(f"{k}={v}" for k, v in step["inputs"].items())
            )
        val = step.get("result_value", step.get("value"))
        unit = step.get("result_unit") or step.get("unit") or ""
        if val is not None:
            lines.append(f"- Result: **{val} {unit}**")
        if step.get("clause"):
            lines.append(f"- Clause: {step['clause']}")
        lines.append("")
    if result.get("checks"):
        lines.append("**Checks:**")
        for c in result["checks"]:
            mark = "✓" if c.get("passed") else "✗"
            lines.append(f"- {mark} {c.get('name')}: {c.get('detail', '')}")
        lines.append("")
    if result.get("answers"):
        lines.append("**Final answers:**")
        for a in result["answers"]:
            lines.append(f"- {a.get('label')}: {a.get('value')} {a.get('unit')}")
    status = result.get("status")
    if status == "needs_input":
        lines.append("")
        lines.append(
            "**Status: needs input** — missing: "
            + ", ".join(result.get("missing_inputs") or [])
        )
    elif status == "unsupported":
        lines.append("")
        lines.append("**Status: unsupported** by the current topic solvers.")
    elif not result.get("steps"):
        lines.append("**Status: not solved**")
    return "\n".join(lines)


def _legacy_from_solver(
    question: str,
    result: dict[str, Any],
    *,
    title: str | None = None,
) -> dict[str, Any]:
    """Map solver result → existing API/UI/PDF shape."""
    svg = diagram_from_solver(result.get("drawing_data"))
    answers = []
    for a in result.get("answers") or []:
        answers.append(
            {
                "label": a.get("label"),
                "value": a.get("value"),
                "unit": a.get("unit") or "",
                "formula_id": a.get("formula_id") or result.get("subject") or "solver",
            }
        )
    steps = []
    for s in result.get("steps") or []:
        steps.append(
            {
                "formula_id": s.get("clause") or "solver",
                "name": s.get("title") or s.get("name") or "Step",
                "expression": s.get("formula") or s.get("expression") or "",
                "inputs": s.get("inputs") or {},
                "value": s.get("result_value", s.get("value")),
                "unit": s.get("result_unit") or s.get("unit") or "",
                "notes": s.get("clause") or s.get("note") or "",
            }
        )
    dtype = "none"
    dd = result.get("drawing_data") or {}
    if svg:
        dtype = str(dd.get("kind") or "beam_sfd_bmd")
    explanation = _narrate_from_solver(question, result)
    return {
        "subject": result.get("subject") or "civil",
        "pack": False,
        "variables_extracted": {
            g[0]: g[1] for g in (result.get("given") or []) if isinstance(g, (list, tuple)) and len(g) >= 2
        },
        "steps": steps,
        "final_answers": answers,
        "diagram_type": dtype,
        "diagram_svg": svg,
        "confidence": 0.9 if result.get("status") == "verified" else 0.35,
        "method": "topic_solver",
        "status": result.get("status") or "unsupported",
        "export_question": (question or "")[:2500],
        "explanation": explanation,
        "llm_used": False,
        "rag_context": [],
        "drawing_data": dd,
        "checks": result.get("checks") or [],
        "schema_version": 2,
        "title": title,
    }


def _solve_one_text(text: str, subject_hint: str | None = None) -> dict[str, Any]:
    cleaned = strip_boilerplate(text) or text
    spec = try_parse_problem(cleaned)
    if spec:
        result = solve_topic(spec)
        if result.get("status") == "verified" or result.get("answers") or result.get("steps"):
            out = _legacy_from_solver(cleaned, result)
            if subject_hint:
                out["subject"] = subject_hint
            return out

    # Detailing / drawing-only
    lower = cleaned.lower()
    if any(
        k in lower
        for k in ("draw the", "detailing", "sectional details", "autocad", "scheme of symbols")
    ) and not any(k in lower for k in ("design and detail", "calculate", "find the")):
        guidance = detailing_guidance(cleaned)
        return {
            "subject": subject_hint or "steel",
            "pack": False,
            "variables_extracted": {},
            "steps": [],
            "final_answers": [],
            "diagram_type": "none",
            "diagram_svg": None,
            "confidence": 0.4,
            "method": "detailing_guidance",
            "status": "detailing",
            "export_question": cleaned[:2500],
            "explanation": guidance,
            "llm_used": False,
            "rag_context": [],
            "schema_version": 2,
        }

    # Honest not-solved (no fake diagram / constant answers)
    return {
        "subject": subject_hint or "civil",
        "pack": False,
        "variables_extracted": {},
        "steps": [],
        "final_answers": [],
        "diagram_type": "none",
        "diagram_svg": None,
        "confidence": 0.2,
        "method": "unsolved",
        "status": "unsupported",
        "export_question": cleaned[:2500],
        "explanation": (
            "## Status: not solved\n\n"
            "No topic solver matched this wording with enough clear inputs.\n\n"
            "Supported today (computed, not templated):\n"
            "- Beams (SS / cantilever) with UDL or point loads → reactions, SFD/BMD values\n"
            "- IS 800 bolted lap joints\n"
            "- IS 456 singly reinforced LSM beams (Ast)\n"
            "- Section bending stress σ = My/I\n"
            "- Soil phase relations (e, S)\n"
        ),
        "llm_used": False,
        "rag_context": [],
        "schema_version": 2,
    }


async def solve_problem(db: Session | None, problem_text: str, subject_hint: str | None = None) -> dict:
    """Main entry — assignment packs or single question via topic solvers."""
    raw = problem_text or ""
    if is_assignment_pack(raw):
        problems = split_problems(raw)
        if len(problems) >= 2:
            return await _solve_pack(problems, subject_hint)

    return _solve_one_text(raw, subject_hint)


async def _solve_pack(problems: list[dict], subject_hint: str | None) -> dict:
    solved: list[dict] = []
    all_answers: list[dict] = []
    expl_parts = [
        "## Assignment pack — solved question by question\n",
        "Each item uses a topic solver when inputs parse; otherwise honest guidance.\n",
    ]

    for prob in problems:
        one = _solve_one_text(prob["text"], subject_hint)
        entry = {
            "id": prob["id"],
            "title": prob["title"],
            "kind": prob.get("kind") or one.get("status") or "numerical",
            "question": prob["text"],
            "explanation": one.get("explanation"),
            "steps": one.get("steps") or [],
            "final_answers": one.get("final_answers") or [],
            "diagram_svg": one.get("diagram_svg"),
            "diagram_type": one.get("diagram_type"),
            "variables_extracted": one.get("variables_extracted") or {},
            "confidence": one.get("confidence"),
            "status": one.get("status"),
        }
        # Detailing override when pack classifier said detailing and solver didn't verify
        if prob.get("kind") == "detailing" and one.get("method") == "unsolved":
            entry["kind"] = "detailing"
            entry["explanation"] = detailing_guidance(prob["text"])
            entry["steps"] = []
            entry["final_answers"] = []
            entry["diagram_svg"] = None
            entry["diagram_type"] = "none"
        for a in entry["final_answers"]:
            all_answers.append({**a, "label": f"{prob['id']}: {a.get('label')}"})
        expl_parts.append(f"\n### {prob['title']}\n")
        expl_parts.append(entry["explanation"] or "")
        solved.append(entry)

    return {
        "subject": subject_hint or "civil",
        "pack": True,
        "problems": solved,
        "variables_extracted": {},
        "steps": [],
        "final_answers": all_answers,
        "diagram_type": "none",
        "diagram_svg": None,
        "confidence": 0.75 if all_answers else 0.4,
        "method": "assignment_pack",
        "export_question": (
            f"Pack of {len(solved)} questions. Each is answered separately in the UI and PDF."
        ),
        "explanation": "\n".join(expl_parts)[:12000],
        "llm_used": False,
        "rag_context": [],
        "schema_version": 2,
    }
