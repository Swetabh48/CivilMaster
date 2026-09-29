"""Render Drawing IR to an SVG string (viewBox from Drawing width/height)."""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

from app.drawing.ir import (
    Arrow,
    Circle,
    Dimension,
    Drawing,
    Line,
    Polyline,
    Primitive,
    Text,
)


def _dash_attr(dash: str | None) -> str:
    return f' stroke-dasharray="{escape(dash)}"' if dash else ""


def _render_line(el: Line) -> str:
    return (
        f'<line x1="{el.x1}" y1="{el.y1}" x2="{el.x2}" y2="{el.y2}" '
        f'stroke="{escape(el.stroke)}" stroke-width="{el.stroke_width}"'
        f"{_dash_attr(el.dash)}/>"
    )


def _render_polyline(el: Polyline) -> str:
    if not el.points:
        return ""
    pts = " ".join(f"{x},{y}" for x, y in el.points)
    tag = "polygon" if el.closed else "polyline"
    return (
        f'<{tag} points="{pts}" fill="{escape(el.fill)}" '
        f'stroke="{escape(el.stroke)}" stroke-width="{el.stroke_width}"'
        f"{_dash_attr(el.dash)}/>"
    )


def _render_circle(el: Circle) -> str:
    return (
        f'<circle cx="{el.cx}" cy="{el.cy}" r="{el.r}" '
        f'fill="{escape(el.fill)}" stroke="{escape(el.stroke)}" '
        f'stroke-width="{el.stroke_width}"/>'
    )


def _render_text(el: Text) -> str:
    return (
        f'<text x="{el.x}" y="{el.y}" text-anchor="{escape(el.anchor)}" '
        f'font-family="{escape(el.font_family)}" font-size="{el.font_size}" '
        f'fill="{escape(el.fill)}">{escape(el.content)}</text>'
    )


def _render_arrow(el: Arrow) -> str:
    dx = el.x2 - el.x1
    dy = el.y2 - el.y1
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return ""
    ux, uy = dx / length, dy / length
    # perpendicular
    px, py = -uy, ux
    hs = el.head_size
    hx = el.x2 - ux * hs
    hy = el.y2 - uy * hs
    tip = f"{el.x2},{el.y2}"
    left = f"{hx + px * hs * 0.45},{hy + py * hs * 0.45}"
    right = f"{hx - px * hs * 0.45},{hy - py * hs * 0.45}"
    return (
        f'<line x1="{el.x1}" y1="{el.y1}" x2="{el.x2}" y2="{el.y2}" '
        f'stroke="{escape(el.stroke)}" stroke-width="{el.stroke_width}"/>'
        f'<polygon points="{tip} {left} {right}" fill="{escape(el.stroke)}" '
        f'stroke="none"/>'
    )


def _render_dimension(el: Dimension) -> str:
    dx = el.x2 - el.x1
    dy = el.y2 - el.y1
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return ""
    ux, uy = dx / length, dy / length
    # outward normal (prefer upward for horizontal dims)
    nx, ny = -uy, ux
    if ny > 0:
        nx, ny = -nx, -ny
    o = el.offset
    a1x, a1y = el.x1 + nx * o, el.y1 + ny * o
    a2x, a2y = el.x2 + nx * o, el.y2 + ny * o
    mx, my = (a1x + a2x) / 2, (a1y + a2y) / 2
    # tick marks
    tick = 6
    parts = [
        f'<line x1="{el.x1}" y1="{el.y1}" x2="{a1x}" y2="{a1y}" '
        f'stroke="{escape(el.stroke)}" stroke-width="{el.stroke_width}"/>',
        f'<line x1="{el.x2}" y1="{el.y2}" x2="{a2x}" y2="{a2y}" '
        f'stroke="{escape(el.stroke)}" stroke-width="{el.stroke_width}"/>',
        f'<line x1="{a1x}" y1="{a1y}" x2="{a2x}" y2="{a2y}" '
        f'stroke="{escape(el.stroke)}" stroke-width="{el.stroke_width}"/>',
        f'<line x1="{a1x - ux * tick}" y1="{a1y - uy * tick}" '
        f'x2="{a1x + ux * tick}" y2="{a1y + uy * tick}" '
        f'stroke="{escape(el.stroke)}" stroke-width="{el.stroke_width}"/>',
        f'<line x1="{a2x - ux * tick}" y1="{a2y - uy * tick}" '
        f'x2="{a2x + ux * tick}" y2="{a2y + uy * tick}" '
        f'stroke="{escape(el.stroke)}" stroke-width="{el.stroke_width}"/>',
        f'<text x="{mx}" y="{my - 4}" text-anchor="middle" '
        f'font-family="IBM Plex Sans, sans-serif" font-size="{el.font_size}" '
        f'fill="{escape(el.stroke)}">{escape(el.label)}</text>',
    ]
    return "".join(parts)


def _render_primitive(el: Primitive) -> str:
    if isinstance(el, Line):
        return _render_line(el)
    if isinstance(el, Polyline):
        return _render_polyline(el)
    if isinstance(el, Circle):
        return _render_circle(el)
    if isinstance(el, Text):
        return _render_text(el)
    if isinstance(el, Arrow):
        return _render_arrow(el)
    if isinstance(el, Dimension):
        return _render_dimension(el)
    return ""


def drawing_to_svg(drawing: Drawing) -> str:
    w = drawing.width
    h = drawing.height
    body = "".join(_render_primitive(el) for el in drawing.elements)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(drawing.title)}">'
        f'<rect width="100%" height="100%" fill="{escape(drawing.background)}"/>'
        f"{body}</svg>"
    )
