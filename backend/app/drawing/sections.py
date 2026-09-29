"""Rectangular / RCC section diagrams from solver drawing_data."""

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


def _fmt(v: float) -> str:
    return f"{v:.4g}"


def build_section_drawing(drawing_data: dict[str, Any]) -> str | None:
    """
    Rectangular section or RCC section with Ast label.

    Required: b, d (or h). Optional: Ast / Ast_provided for RCC labelling.
    kind in drawing_data may be 'section', 'section_rect', 'rcc_section'.
    """
    b = _f(drawing_data, "b", "width")
    d = _f(drawing_data, "d", "h", "depth", "effective_depth")
    if b is None or d is None:
        return None

    kind = str(drawing_data.get("kind", "section_rect")).lower()
    is_rcc = kind in {"rcc_section", "rcc", "rcc_beam", "lsm_beam"}
    # Also treat as RCC if Ast is present
    ast = _f(drawing_data, "Ast", "ast", "Ast_provided", "Ast_req")
    if ast is not None:
        is_rcc = True

    W, H = 480.0, 420.0
    title = "RCC beam section" if is_rcc else "Rectangular section"
    drawing = Drawing(width=W, height=H, title=title)

    drawing.add(Text(24, 28, title, font_size=15))
    subtitle = f"b = {_fmt(b)}  |  d = {_fmt(d)}"
    if ast is not None:
        subtitle += f"  |  Ast = {_fmt(ast)}"
    drawing.add(Text(24, 48, subtitle, font_size=12, fill="#5a6573"))

    # Fit rectangle in canvas
    max_w, max_h = 220.0, 260.0
    scale = min(max_w / b, max_h / d)
    rw, rh = b * scale, d * scale
    ox = (W - rw) / 2
    oy = 70.0

    fill = "#efece4" if is_rcc else "#e8edf2"
    drawing.add(
        Polyline(
            [(ox, oy), (ox + rw, oy), (ox + rw, oy + rh), (ox, oy + rh)],
            closed=True,
            fill=fill,
            stroke="#1c2430",
            stroke_width=3,
        )
    )

    # Neutral axis at mid-depth (schematic)
    na_y = oy + rh / 2
    drawing.add(
        Line(ox, na_y, ox + rw, na_y, stroke="#9aa3ad", stroke_width=1.2, dash="6 4"),
        Text(ox + rw + 8, na_y + 4, "NA", font_size=11, fill="#5a6573"),
    )

    if is_rcc:
        # Compression zone tint
        comp_h = rh * 0.28
        drawing.add(
            Polyline(
                [(ox, oy), (ox + rw, oy), (ox + rw, oy + comp_h), (ox, oy + comp_h)],
                closed=True,
                fill="#d7e0ea",
                stroke="none",
            ),
            Text(
                ox + rw / 2,
                oy + comp_h / 2 + 4,
                "Compression",
                anchor="middle",
                font_size=11,
                fill="#2f5d8a",
            ),
        )
        # Tensile bars near bottom
        bar_y = oy + rh - 18
        n_bars = 4
        for i in range(n_bars):
            t = (i + 1) / (n_bars + 1)
            cx = ox + t * rw
            drawing.add(Circle(cx, bar_y, 7, fill="#1c2430", stroke="#1c2430"))
        ast_label = f"Ast = {_fmt(ast)}" if ast is not None else "Ast (tensile steel)"
        drawing.add(
            Text(
                ox + rw / 2,
                oy + rh + 28,
                ast_label,
                anchor="middle",
                font_size=12,
                fill="#1c2430",
            )
        )
    else:
        drawing.add(
            Dimension(ox, oy + rh, ox + rw, oy + rh, f"b = {_fmt(b)}", offset=22),
            Dimension(ox + rw, oy, ox + rw, oy + rh, f"d = {_fmt(d)}", offset=22),
        )

    if is_rcc:
        drawing.add(
            Dimension(ox, oy + rh, ox + rw, oy + rh, f"b = {_fmt(b)}", offset=44),
            Dimension(ox + rw, oy, ox + rw, oy + rh, f"d = {_fmt(d)}", offset=22),
        )

    return drawing_to_svg(drawing)
