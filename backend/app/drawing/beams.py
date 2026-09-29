"""Beam loading diagram + schematic SFD/BMD from solver drawing_data."""

from __future__ import annotations

from typing import Any

from app.drawing.ir import Arrow, Circle, Dimension, Drawing, Line, Polyline, Text
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


def build_beam_drawing(drawing_data: dict[str, Any]) -> str | None:
    """
    Build loading diagram + schematic SFD/BMD with actual L, Vmax, Mmax.

    Required: span (L / L_mm), V_max, M_max. UDL w preferred when present.
    Returns None if incomplete — never invents defaults.
    """
    L = _f(drawing_data, "L", "L_mm", "span", "span_mm")
    v_max = _f(drawing_data, "V_max", "Vmax", "v_max")
    m_max = _f(drawing_data, "M_max", "Mmax", "m_max")
    w = _f(drawing_data, "w", "W", "udl", "w_N_per_mm")

    if w is None:
        for load in drawing_data.get("loads") or []:
            if not isinstance(load, dict):
                continue
            if str(load.get("kind") or "").lower() == "udl":
                w = _f(load, "magnitude_N_per_mm", "w", "W", "magnitude")
                if w is not None:
                    break

    if L is None or v_max is None or m_max is None:
        return None

    L_label = L / 1000.0 if L >= 100 else L
    L_unit = "m" if L >= 100 else "mm"
    w_disp = f"w = {_fmt(w)}" if w is not None else "loads: see solution"
    support = str(drawing_data.get("support") or "simply_supported")

    W, H = 640.0, 420.0
    d = Drawing(width=W, height=H, title="Beam loading / SFD / BMD")

    x0, x1 = 80.0, 560.0
    beam_y = 100.0
    span_px = x1 - x0

    d.add(
        Text(
            24,
            28,
            f"{support.replace('_', ' ').title()} — loading / SFD / BMD",
            font_size=15,
        ),
        Text(
            24,
            48,
            f"L = {_fmt(L_label)} {L_unit}  |  {w_disp}  |  Vmax = {_fmt(v_max)}  |  Mmax = {_fmt(m_max)}",
            font_size=12,
            fill="#5a6573",
        ),
    )

    d.add(Line(x0, beam_y, x1, beam_y, stroke_width=4))
    if support == "cantilever":
        d.add(Line(x0 - 4, beam_y - 30, x0 - 4, beam_y + 30, stroke_width=6))
        for yi in range(-28, 30, 8):
            d.add(Line(x0 - 4, beam_y + yi, x0 - 18, beam_y + yi + 8, stroke_width=1.5))
    else:
        d.add(
            Polyline(
                [(x0, beam_y), (x0 - 12, beam_y + 22), (x0 + 12, beam_y + 22)],
                closed=True,
                fill="#1c2430",
                stroke="#1c2430",
            )
        )
        d.add(
            Line(x1 - 10, beam_y, x1 + 10, beam_y, stroke_width=2),
            Circle(x1, beam_y + 14, 8, fill="none", stroke_width=2),
            Line(x1 - 14, beam_y + 24, x1 + 14, beam_y + 24, stroke_width=1.5),
        )

    load_top = beam_y - 36
    for i in range(7):
        t = i / 6
        xa = x0 + t * span_px
        d.add(Arrow(xa, load_top, xa, beam_y - 6, stroke="#c4a35a", stroke_width=1.5))
    d.add(Line(x0, load_top, x1, load_top, stroke="#c4a35a", stroke_width=2))
    d.add(
        Text(
            (x0 + x1) / 2,
            load_top - 8,
            w_disp,
            anchor="middle",
            font_size=12,
            fill="#8a6d2f",
        )
    )
    d.add(
        Dimension(
            x0,
            beam_y + 22,
            x1,
            beam_y + 22,
            f"L = {_fmt(L_label)} {L_unit}",
            offset=28,
        )
    )

    sfd_base = 230.0
    sfd_amp = 40.0
    d.add(
        Text(24, sfd_base - sfd_amp - 8, "SFD", font_size=13),
        Line(x0, sfd_base, x1, sfd_base, stroke="#9aa3ad", stroke_width=1),
        Polyline(
            [
                (x0, sfd_base),
                (x0, sfd_base - sfd_amp),
                (x1, sfd_base + sfd_amp),
                (x1, sfd_base),
            ],
            closed=True,
            fill="#dbe7f3",
            stroke="#2f5d8a",
            stroke_width=2,
        ),
        Text(
            x0 + 8,
            sfd_base - sfd_amp - 4,
            f"Vmax={_fmt(v_max)}",
            font_size=11,
            fill="#2f5d8a",
        ),
    )

    bmd_base = 340.0
    bmd_amp = 45.0
    mid = (x0 + x1) / 2
    d.add(
        Text(24, bmd_base - 8, "BMD", font_size=13),
        Line(x0, bmd_base, x1, bmd_base, stroke="#9aa3ad", stroke_width=1),
        Polyline(
            [(x0, bmd_base), (mid, bmd_base + bmd_amp), (x1, bmd_base)],
            closed=False,
            fill="none",
            stroke="#8a4b2f",
            stroke_width=2,
        ),
        Text(
            mid,
            bmd_base + bmd_amp + 14,
            f"Mmax={_fmt(m_max)}",
            anchor="middle",
            font_size=11,
            fill="#8a4b2f",
        ),
    )

    return drawing_to_svg(d)
