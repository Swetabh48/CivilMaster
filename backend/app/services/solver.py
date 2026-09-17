from __future__ import annotations

from sqlalchemy.orm import Session

from app.diagrams.svg_templates import render_diagram
from app.formulas.registry import solve_with_registry
from app.services.llm import generate_explanation, narrative_from_registry
from app.services.rag import retrieve


async def solve_problem(db: Session, problem_text: str, subject_hint: str | None = None) -> dict:
    registry = solve_with_registry(problem_text)
    if subject_hint:
        registry["subject"] = subject_hint

    rag_hits = retrieve(db, problem_text, limit=5)
    registry["rag_context"] = rag_hits

    # Diagram params from variables + answers
    params = dict(registry.get("variables_extracted") or {})
    for ans in registry.get("final_answers") or []:
        fid = ans.get("formula_id", "")
        if "moment" in (ans.get("label") or "").lower() or "bm" in fid:
            params["M_max"] = ans["value"]
        if "shear" in (ans.get("label") or "").lower() or "sf" in fid:
            params["V_max"] = ans["value"]
        if fid == "rcc.ast_required":
            params["Ast"] = ans["value"]

    svg = render_diagram(registry.get("diagram_type") or "none", params)
    registry["diagram_svg"] = svg

    explanation = await generate_explanation(problem_text, registry, rag_hits)
    registry["explanation"] = explanation or narrative_from_registry(problem_text, registry)
    registry["llm_used"] = bool(explanation)
    return registry
