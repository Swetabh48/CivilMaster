"""Dispatch solver drawing_data to the appropriate topic renderer."""

from __future__ import annotations

from typing import Any

from app.drawing.beams import build_beam_drawing
from app.drawing.joints import build_joint_drawing
from app.drawing.sections import build_section_drawing


def diagram_from_solver(drawing_data: dict[str, Any] | None) -> str | None:
    """
    Render an SVG string from solver `drawing_data`, or None if kind unknown /
    required values missing. Never invents geometry defaults.
    """
    if not drawing_data:
        return None

    kind = str(drawing_data.get("kind", "")).lower().strip()
    if not kind:
        return None

    if kind in {
        "beam",
        "beam_sfd_bmd",
        "beam_loading",
        "beam_analysis",
        "sfd_bmd",
    }:
        return build_beam_drawing(drawing_data)

    if kind in {
        "bolted_lap",
        "bolted_joint",
        "bolted_lap_joint",
        "is800_bolted_joint",
        "lap_joint",
        "joint",
    }:
        data = dict(drawing_data)
        layout = data.get("layout") if isinstance(data.get("layout"), dict) else {}
        if "d" not in data:
            data["d"] = data.get("bolt_d_mm") or data.get("bolt_dia")
        if "pitch" not in data:
            data["pitch"] = data.get("pitch_mm") or layout.get("pitch_mm")
        if "edge" not in data:
            data["edge"] = data.get("edge_mm") or layout.get("edge_mm")
        if "plate_width" not in data:
            data["plate_width"] = data.get("plate_w_mm") or data.get("width")
        if "n_bolts" not in data and layout.get("cols"):
            data["n_bolts"] = layout.get("cols")
        return build_joint_drawing(data)

    if kind in {
        "section",
        "section_rect",
        "rect_section",
        "section_bending_stress",
        "rcc_section",
        "rcc",
        "rcc_beam",
        "rcc_lsm_beam",
        "lsm_beam",
    }:
        # Normalize solver aliases
        data = dict(drawing_data)
        if "b" not in data and "b_mm" in data:
            data["b"] = data["b_mm"]
        if "d" not in data and "d_mm" in data:
            data["d"] = data["d_mm"]
        if "Ast" not in data and "Ast_mm2" in data:
            data["Ast"] = data["Ast_mm2"]
        return build_section_drawing(data)

    return None
