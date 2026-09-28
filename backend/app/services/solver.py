from __future__ import annotations

from sqlalchemy.orm import Session

from app.diagrams.svg_templates import render_diagram
from app.formulas.registry import solve_with_registry
from app.services.llm import generate_explanation, narrative_from_registry
from app.services.problem_prep import (
    detailing_guidance,
    is_assignment_pack,
    split_problems,
    strip_boilerplate,
)
from app.services.rag import retrieve


def _attach_diagram(registry: dict) -> None:
    params = dict(registry.get("variables_extracted") or {})
    for ans in registry.get("final_answers") or []:
        fid = ans.get("formula_id", "")
        if "moment" in (ans.get("label") or "").lower() or "bm" in fid:
            params["M_max"] = ans["value"]
        if "shear" in (ans.get("label") or "").lower() or "sf" in fid:
            params["V_max"] = ans["value"]
        if fid == "rcc.ast_required":
            params["Ast"] = ans["value"]

    dtype = registry.get("diagram_type") or "none"
    svg = render_diagram(dtype, params) if dtype and dtype != "none" else None
    if not svg and registry.get("steps"):
        fids = " ".join(a.get("formula_id") or "" for a in (registry.get("final_answers") or []))
        if any(k in fids for k in ("beam", "moment", "shear")):
            dtype = "beam_sfd_bmd"
        elif "rcc" in fids:
            dtype = "rcc_section"
        elif "inertia" in fids or "section" in fids:
            dtype = "section"
        elif "P" in params and "A" in params:
            dtype = "axial"
        else:
            dtype = "none"
        if dtype != "none":
            registry["diagram_type"] = dtype
            svg = render_diagram(dtype, params)
    # Never invent a diagram when we failed to solve
    if not registry.get("steps"):
        svg = None
        registry["diagram_type"] = "none"
    registry["diagram_svg"] = svg


async def _solve_one(
    db: Session,
    problem_text: str,
    subject_hint: str | None = None,
    *,
    use_llm: bool = True,
) -> dict:
    registry = solve_with_registry(problem_text)
    if subject_hint:
        registry["subject"] = subject_hint

    rag_hits = retrieve(db, problem_text, limit=5) if db is not None else []
    registry["rag_context"] = rag_hits
    _attach_diagram(registry)

    if use_llm:
        explanation = await generate_explanation(problem_text, registry, rag_hits)
        registry["explanation"] = explanation or narrative_from_registry(problem_text, registry)
        registry["llm_used"] = bool(explanation)
    else:
        registry["explanation"] = narrative_from_registry(problem_text, registry)
        registry["llm_used"] = False
    registry["export_question"] = problem_text[:2500]
    return registry


async def solve_problem(db: Session, problem_text: str, subject_hint: str | None = None) -> dict:
    raw = problem_text or ""
    cleaned = strip_boilerplate(raw)

    # Multi-question / lab assignment packs
    if is_assignment_pack(raw):
        problems = split_problems(raw)
        if len(problems) >= 2:
            return await _solve_pack(db, problems, subject_hint)

    # Single problem — still strip syllabus junk
    text = cleaned or raw
    # If still huge and mostly detailing syllabus, don't pretend we solved it
    if len(text) > 3500 and not re_has_clear_numeric(text):
        return _unsolvable_sheet(text)

    return await _solve_one(db, text, subject_hint)


def re_has_clear_numeric(text: str) -> bool:
    import re

    return bool(
        re.search(
            r"(?i)(p|w|m|v|l|a|fu|fy)\s*=\s*\d|\d+\s*(kn|n/mm|mpa|mm2|n·mm)",
            text,
        )
    )


def _unsolvable_sheet(text: str) -> dict:
    guidance = detailing_guidance(text)
    return {
        "subject": "steel",
        "pack": False,
        "variables_extracted": {},
        "steps": [],
        "final_answers": [],
        "diagram_type": "none",
        "diagram_svg": None,
        "confidence": 0.15,
        "method": "assignment_sheet",
        "export_question": (
            "Uploaded file looks like a full drawing / lab assignment sheet "
            "(multiple detailing tasks), not one numerical problem."
        ),
        "explanation": (
            "## What CivilMaster can do with this upload\n\n"
            + guidance
            + "\n\n## Tip\n"
            "Paste **one** question at a time, e.g.\n"
            "`Design a lap joint for 145 kN using M16 grade 4.6 bolts, plates 12 mm × 120 mm, E250.`"
        ),
        "llm_used": False,
        "rag_context": [],
    }


def _design_checklist(question: str, variables: dict) -> str:
    q = (question or "").lower()
    lines = [
        "## Design path (IS 800) — work this by hand / AutoCAD",
        "",
        "CivilMaster classified this as a **design** question. Full connection design is not in the formula registry yet, so use this checklist:",
        "",
    ]
    if variables:
        lines.append("**Values extracted from the question:**")
        for k, v in list(variables.items())[:12]:
            lines.append(f"- {k} = {v}")
        lines.append("")
    if "bolt" in q or "bolted" in q or "lap joint" in q or "butt joint" in q:
        lines.extend(
            [
                "1. Find design strength of bolt in shear / bearing / tension (IS 800 Cl. 10.3).",
                "2. Number of bolts ≥ T_u / V_db (or governing strength).",
                "3. Check pitch, gauge, edge & end distances.",
                "4. Check plate rupture / block shear / efficiency.",
                "5. Draw FV + plan with bolt schedule and plate sizes.",
                "",
            ]
        )
    if "weld" in q or "fillet" in q:
        lines.extend(
            [
                "1. Find design strength of fillet weld (IS 800 Cl. 10.5).",
                "2. Size / length of weld for the factored force.",
                "3. Check min/max weld size and return length.",
                "4. Detail with IS 813 weld symbols.",
                "",
            ]
        )
    if "beam" in q or "column" in q or "girder" in q or "truss" in q:
        lines.extend(
            [
                "1. Compute design loads (IS 875) and factored forces (IS 800).",
                "2. Select / check section for strength & serviceability.",
                "3. Detail connections, stiffeners, and splices as asked.",
                "",
            ]
        )
    lines.append(
        "Detail connections in AutoCAD with IS 813 symbols and full dimensions."
    )
    return "\n".join(lines)


async def _solve_pack(
    db: Session,
    problems: list[dict],
    subject_hint: str | None,
) -> dict:
    solved: list[dict] = []
    all_answers: list[dict] = []
    expl_parts: list[str] = [
        "## Assignment pack — solved question by question\n",
        "Drawing/detailing items get CAD guidance. Numerical items use the formula engine.\n",
    ]

    for prob in problems:
        entry: dict = {
            "id": prob["id"],
            "title": prob["title"],
            "kind": prob["kind"],
            "question": prob["text"],
        }
        if prob["kind"] == "detailing":
            entry["explanation"] = detailing_guidance(prob["text"])
            entry["steps"] = []
            entry["final_answers"] = []
            entry["diagram_svg"] = None
            entry["diagram_type"] = "none"
            expl_parts.append(f"\n### {prob['title']} (detailing)\n")
            expl_parts.append(entry["explanation"])
        else:
            one = await _solve_one(db, prob["text"], subject_hint, use_llm=False)
            entry.update(
                {
                    "explanation": one.get("explanation"),
                    "steps": one.get("steps") or [],
                    "final_answers": one.get("final_answers") or [],
                    "diagram_svg": one.get("diagram_svg"),
                    "diagram_type": one.get("diagram_type"),
                    "variables_extracted": one.get("variables_extracted") or {},
                    "confidence": one.get("confidence"),
                }
            )
            if not entry["steps"] and not entry["final_answers"]:
                entry["explanation"] = _design_checklist(prob["text"], one.get("variables_extracted") or {})
            for a in entry["final_answers"]:
                all_answers.append({**a, "label": f"{prob['id']}: {a.get('label')}"})
            expl_parts.append(f"\n### {prob['title']} (numerical)\n")
            expl_parts.append(entry["explanation"] or "")
        solved.append(entry)

    return {
        "subject": subject_hint or "steel",
        "pack": True,
        "problems": solved,
        "variables_extracted": {},
        "steps": [],
        "final_answers": all_answers,
        "diagram_type": "none",
        "diagram_svg": None,
        "confidence": 0.55 if all_answers else 0.35,
        "method": "assignment_pack",
        "export_question": (
            f"Pack of {len(solved)} questions extracted from your upload. "
            "Each question is answered separately below / in the PDF."
        ),
        "explanation": "\n".join(expl_parts)[:12000],
        "llm_used": False,
        "rag_context": [],
    }
