"""Bolted lap joint schematic from solver drawing_data."""

from __future__ import annotations

from typing import Any

from app.drawing.ir import Circle, Dimension, Drawing, Line, Polyline, Text
from app.drawing.svg import drawing_to_svg


def _f(data: dict[str, Any], *keys: str) -> float | None:
    for k in keys:
        if k in data and data[k] is not None:
            try:
                return float(data[k])
            except (TypeError, ValueError):
                continue
    return None


def _i(data: dict[str, Any], *keys: str) -> int | None:
    v = _f(data, *keys)
    if v is None:
        return None
    return int(round(v))


def _fmt(v: float) -> str:
    return f"{v:.4g}"


def build_joint_drawing(drawing_data: dict[str, Any]) -> str | None:
    """
    Bolted lap joint plan schematic.

    Required: n_bolts, d (bolt dia), pitch, edge, and plate dims
    (plate_width / width, and plate_length / length or computed from bolts).
    """
    n = _i(drawing_data, "n_bolts", "n", "bolts")
    d = _f(drawing_data, "d", "bolt_dia", "diameter")
    pitch = _f(drawing_data, "pitch", "p")
    edge = _f(drawing_data, "edge", "e", "edge_distance")
    plate_w = _f(drawing_data, "plate_width", "width", "b")
    plate_l = _f(drawing_data, "plate_length", "length", "L")

    if n is None or n < 1 or d is None or pitch is None or edge is None:
        return None
    if plate_w is None:
        return None

    # If length omitted, derive from bolt chain: 2*edge + (n-1)*pitch
    if plate_l is None:
        plate_l = 2 * edge + (n - 1) * pitch
        if plate_l <= 0:
            return None

    W, H = 640.0, 320.0
    drawing = Drawing(width=W, height=H, title="Bolted lap joint")

    drawing.add(
        Text(24, 28, "Bolted lap joint (plan)", font_size=15),
        Text(
            24,
            48,
            f"n = {n}  |  d = {_fmt(d)}  |  pitch = {_fmt(pitch)}  |  edge = {_fmt(edge)}",
            font_size=12,
            fill="#5a6573",
        ),
    )

    # Scale plates into drawing area
    margin_x, margin_y = 80.0, 90.0
    max_draw_w, max_draw_h = 480.0, 140.0
    scale = min(max_draw_w / plate_l, max_draw_h / plate_w)
    pw = plate_l * scale
    ph = plate_w * scale

    # Two overlapping plates (lap): lower and upper offset slightly
    ox, oy = margin_x, margin_y
    overlap = pw * 0.55
    # Plate A (left / bottom)
    drawing.add(
        Polyline(
            [
                (ox, oy + 12),
                (ox + pw, oy + 12),
                (ox + pw, oy + 12 + ph),
                (ox, oy + 12 + ph),
            ],
            closed=True,
            fill="#e8edf2",
            stroke="#1c2430",
            stroke_width=2,
        )
    )
    # Plate B (right / top, shifted)
    bx = ox + pw - overlap
    drawing.add(
        Polyline(
            [
                (bx, oy),
                (bx + pw, oy),
                (bx + pw, oy + ph),
                (bx, oy + ph),
            ],
            closed=True,
            fill="#efece4",
            stroke="#1c2430",
            stroke_width=2,
        )
    )

    # Bolt row along overlap centreline
    bolt_y = oy + ph / 2 + 6
    bolt_r = max(3.0, (d * scale) / 2)
    # Place n bolts spaced by pitch within the overlap zone
    usable = (n - 1) * pitch * scale if n > 1 else 0.0
    start_x = bx + (overlap - usable) / 2
    for i in range(n):
        cx = start_x + i * pitch * scale
        drawing.add(
            Circle(cx, bolt_y, bolt_r, fill="#1c2430", stroke="#1c2430"),
            Circle(cx, bolt_y, bolt_r * 0.45, fill="#f7f6f2", stroke="#1c2430", stroke_width=1),
        )

    # Dimensions
    if n > 1:
        drawing.add(
            Dimension(
                start_x,
                bolt_y + bolt_r + 4,
                start_x + pitch * scale,
                bolt_y + bolt_r + 4,
                f"p = {_fmt(pitch)}",
                offset=22,
            )
        )
    # Edge from first bolt to plate end of B (left of overlap ≈ edge)
    edge_end = start_x
    drawing.add(
        Dimension(
            bx,
            oy - 4,
            edge_end,
            oy - 4,
            f"e = {_fmt(edge)}",
            offset=-16,
        )
    )
    drawing.add(
        Dimension(
            ox,
            oy + 12 + ph,
            ox + pw,
            oy + 12 + ph,
            f"L = {_fmt(plate_l)}",
            offset=28,
        ),
        Dimension(
            ox + pw,
            oy + 12,
            ox + pw,
            oy + 12 + ph,
            f"b = {_fmt(plate_w)}",
            offset=24,
        ),
        Text(
            24,
            H - 24,
            f"Bolt dia d = {_fmt(d)} (schematic)",
            font_size=11,
            fill="#5a6573",
        ),
    )

    return drawing_to_svg(drawing)
