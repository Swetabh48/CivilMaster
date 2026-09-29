"""CivilMaster topic solvers — dispatch by topic key."""

from __future__ import annotations

from typing import Any, Callable

from app.solvers.base import NeedsInput, empty_result
from app.solvers.beams import solve_beam
from app.solvers.geotech import solve_phase_relations
from app.solvers.rcc_is456 import solve_rcc_singly
from app.solvers.sections import solve_bending_stress
from app.solvers.steel_is800 import solve_steel_bolted_lap

_TOPIC_ALIASES: dict[str, str] = {
    "beam": "beam_analysis",
    "beam_analysis": "beam_analysis",
    "beams": "beam_analysis",
    "sfd_bmd": "beam_analysis",
    "is800_bolted_joint": "is800_bolted_lap",
    "is800_bolted_lap": "is800_bolted_lap",
    "bolted_lap": "is800_bolted_lap",
    "steel_bolted_lap": "is800_bolted_lap",
    "steel": "is800_bolted_lap",
    "rcc_singly": "rcc_singly_lsm",
    "rcc_singly_lsm": "rcc_singly_lsm",
    "rcc_lsm": "rcc_singly_lsm",
    "rcc": "rcc_singly_lsm",
    "is456": "rcc_singly_lsm",
    "geotech": "phase_relations",
    "phase_relations": "phase_relations",
    "soil_phase": "phase_relations",
    "phase": "phase_relations",
    "section": "bending_stress",
    "bending_stress": "bending_stress",
    "sections": "bending_stress",
    "flexure_stress": "bending_stress",
}

_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "beam_analysis": solve_beam,
    "is800_bolted_lap": solve_steel_bolted_lap,
    "rcc_singly_lsm": solve_rcc_singly,
    "phase_relations": solve_phase_relations,
    "bending_stress": solve_bending_stress,
}


def solve_topic(spec_dict: dict[str, Any]) -> dict[str, Any]:
    """Route a problem spec dict to the matching topic solver.

    Spec must include ``topic`` (or ``kind``). Returns the standard result dict:
    status, subject, steps, answers, checks, drawing_data, missing_inputs, given.
    """
    if not isinstance(spec_dict, dict):
        return empty_result(
            status="needs_input",
            missing=["spec_dict"],
        )

    raw = spec_dict.get("topic") or spec_dict.get("kind") or spec_dict.get("solver")
    if not raw:
        return empty_result(
            status="needs_input",
            missing=["topic"],
        )

    key = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    topic = _TOPIC_ALIASES.get(key, key)
    handler = _HANDLERS.get(topic)
    if handler is None:
        return empty_result(
            status="unsupported",
            subject=str(raw),
            missing=[f"topic={raw!r}"],
        )

    try:
        return handler(spec_dict)
    except NeedsInput as e:
        return empty_result(
            status="needs_input",
            subject=topic,
            missing=e.missing,
        )


__all__ = [
    "solve_topic",
    "solve_beam",
    "solve_steel_bolted_lap",
    "solve_rcc_singly",
    "solve_phase_relations",
    "solve_bending_stress",
    "NeedsInput",
]
