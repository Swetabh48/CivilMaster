"""Parametric SVG diagram templates for civil engineering sketches."""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape


def _svg(body: str, width: int = 640, height: int = 360, title: str = "Diagram") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
        f"<rect width=\"100%\" height=\"100%\" fill=\"#f7f6f2\"/>"
        f"{body}</svg>"
    )


def beam_sfd_bmd(params: dict[str, Any] | None = None) -> str:
    p = params or {}
    L = float(p.get("L", 4000))
    w = float(p.get("w", p.get("W", 10)))
    m_max = p.get("M_max")
    v_max = p.get("V_max")
    if m_max is None and "w" in p:
        m_max = (w * L**2) / 8.0
    if v_max is None and "w" in p:
        v_max = (w * L) / 2.0

    label_m = f"Mmax={m_max:.3g}" if m_max is not None else "Mmax"
    label_v = f"Vmax={v_max:.3g}" if v_max is not None else "Vmax"

    body = f"""
    <text x="24" y="28" font-family="IBM Plex Sans, sans-serif" font-size="16" fill="#1c2430">Simply supported beam — SFD / BMD sketch</text>
    <text x="24" y="50" font-family="IBM Plex Sans, sans-serif" font-size="12" fill="#5a6573">Span L={L:g} | UDL w={w:g}</text>
    <!-- beam -->
    <line x1="80" y1="110" x2="560" y2="110" stroke="#1c2430" stroke-width="4"/>
    <polygon points="80,110 70,130 90,130" fill="#1c2430"/>
    <rect x="548" y="110" width="16" height="14" fill="none" stroke="#1c2430" stroke-width="2"/>
    <!-- UDL arrows -->
    <line x1="120" y1="70" x2="120" y2="100" stroke="#c4a35a" stroke-width="2" marker-end="url(#arrow)"/>
    <line x1="200" y1="70" x2="200" y2="100" stroke="#c4a35a" stroke-width="2"/>
    <line x1="280" y1="70" x2="280" y2="100" stroke="#c4a35a" stroke-width="2"/>
    <line x1="360" y1="70" x2="360" y2="100" stroke="#c4a35a" stroke-width="2"/>
    <line x1="440" y1="70" x2="440" y2="100" stroke="#c4a35a" stroke-width="2"/>
    <line x1="520" y1="70" x2="520" y2="100" stroke="#c4a35a" stroke-width="2"/>
    <line x1="120" y1="70" x2="520" y2="70" stroke="#c4a35a" stroke-width="2"/>
    <text x="300" y="62" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="12" fill="#8a6d2f">w</text>
    <!-- SFD -->
    <text x="80" y="170" font-family="IBM Plex Sans, sans-serif" font-size="13" fill="#1c2430">SFD</text>
    <line x1="80" y1="210" x2="560" y2="210" stroke="#9aa3ad" stroke-width="1"/>
    <polygon points="80,210 80,170 320,210 560,250 560,210" fill="#dbe7f3" stroke="#2f5d8a" stroke-width="2"/>
    <text x="90" y="165" font-size="11" fill="#2f5d8a" font-family="IBM Plex Sans, sans-serif">{escape(label_v)}</text>
    <!-- BMD -->
    <text x="80" y="280" font-family="IBM Plex Sans, sans-serif" font-size="13" fill="#1c2430">BMD</text>
    <line x1="80" y1="300" x2="560" y2="300" stroke="#9aa3ad" stroke-width="1"/>
    <path d="M80,300 Q320,360 560,300" fill="#f3e6db" stroke="#8a4b2f" stroke-width="2"/>
    <text x="300" y="350" text-anchor="middle" font-size="11" fill="#8a4b2f" font-family="IBM Plex Sans, sans-serif">{escape(label_m)}</text>
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
        <path d="M0,0 L8,4 L0,8 z" fill="#c4a35a"/>
      </marker>
    </defs>
    """
    return _svg(body, title="Beam SFD BMD")


def section_rect(params: dict[str, Any] | None = None) -> str:
    p = params or {}
    b = float(p.get("b", 200))
    d = float(p.get("d", 300))
    body = f"""
    <text x="24" y="28" font-family="IBM Plex Sans, sans-serif" font-size="16" fill="#1c2430">Rectangular section</text>
    <rect x="220" y="70" width="200" height="240" fill="#e8edf2" stroke="#1c2430" stroke-width="3"/>
    <line x1="220" y1="330" x2="420" y2="330" stroke="#2f5d8a" stroke-width="2"/>
    <text x="320" y="350" text-anchor="middle" font-size="13" fill="#2f5d8a" font-family="IBM Plex Sans, sans-serif">b = {b:g}</text>
    <line x1="440" y1="70" x2="440" y2="310" stroke="#8a4b2f" stroke-width="2"/>
    <text x="455" y="200" font-size="13" fill="#8a4b2f" font-family="IBM Plex Sans, sans-serif">d = {d:g}</text>
    <line x1="220" y1="190" x2="420" y2="190" stroke="#9aa3ad" stroke-dasharray="6 4"/>
    <text x="320" y="185" text-anchor="middle" font-size="11" fill="#5a6573" font-family="IBM Plex Sans, sans-serif">NA</text>
    """
    return _svg(body, title="Rectangular section")


def rcc_section(params: dict[str, Any] | None = None) -> str:
    p = params or {}
    b = float(p.get("b", 230))
    d = float(p.get("d", 450))
    ast = p.get("Ast")
    ast_label = f"Ast = {float(ast):.3g} mm²" if ast is not None else "Ast (tensile steel)"
    body = f"""
    <text x="24" y="28" font-family="IBM Plex Sans, sans-serif" font-size="16" fill="#1c2430">RCC beam section (schematic)</text>
    <text x="24" y="48" font-family="IBM Plex Sans, sans-serif" font-size="12" fill="#5a6573">b={b:g} mm, effective d={d:g} mm</text>
    <rect x="200" y="70" width="220" height="250" fill="#efece4" stroke="#1c2430" stroke-width="3"/>
    <!-- compression zone hatch -->
    <rect x="200" y="70" width="220" height="70" fill="#d7e0ea" opacity="0.7"/>
    <text x="310" y="110" text-anchor="middle" font-size="12" fill="#2f5d8a" font-family="IBM Plex Sans, sans-serif">Compression</text>
    <line x1="200" y1="140" x2="420" y2="140" stroke="#2f5d8a" stroke-dasharray="5 4"/>
    <text x="430" y="144" font-size="11" fill="#2f5d8a" font-family="IBM Plex Sans, sans-serif">NA</text>
    <!-- steel bars -->
    <circle cx="240" cy="300" r="8" fill="#1c2430"/>
    <circle cx="280" cy="300" r="8" fill="#1c2430"/>
    <circle cx="320" cy="300" r="8" fill="#1c2430"/>
    <circle cx="360" cy="300" r="8" fill="#1c2430"/>
    <text x="310" y="335" text-anchor="middle" font-size="12" fill="#1c2430" font-family="IBM Plex Sans, sans-serif">{escape(ast_label)}</text>
    """
    return _svg(body, title="RCC section")


def render_diagram(diagram_type: str, params: dict[str, Any] | None = None) -> str | None:
    if diagram_type == "beam_sfd_bmd":
        return beam_sfd_bmd(params)
    if diagram_type == "section":
        return section_rect(params)
    if diagram_type == "rcc_section":
        return rcc_section(params)
    if diagram_type == "axial":
        return axial_member(params)
    return None


def axial_member(params: dict[str, Any] | None = None) -> str:
    p = params or {}
    P = float(p.get("P", 100000))
    A = float(p.get("A", 500))
    body = f"""
    <text x="24" y="28" font-family="IBM Plex Sans, sans-serif" font-size="16" fill="#1c2430">Axial loaded member</text>
    <text x="24" y="50" font-family="IBM Plex Sans, sans-serif" font-size="12" fill="#5a6573">P={P:g} | A={A:g}</text>
    <rect x="180" y="140" width="280" height="70" fill="#e8edf2" stroke="#1c2430" stroke-width="3"/>
    <line x1="80" y1="175" x2="180" y2="175" stroke="#8a4b2f" stroke-width="3" marker-end="url(#arrowP)"/>
    <line x1="460" y1="175" x2="560" y2="175" stroke="#8a4b2f" stroke-width="3" marker-end="url(#arrowP)"/>
    <text x="100" y="160" font-size="14" fill="#8a4b2f" font-family="IBM Plex Sans, sans-serif">P</text>
    <text x="520" y="160" font-size="14" fill="#8a4b2f" font-family="IBM Plex Sans, sans-serif">P</text>
    <text x="320" y="250" text-anchor="middle" font-size="13" fill="#2f5d8a" font-family="IBM Plex Sans, sans-serif">σ = P / A</text>
    <defs>
      <marker id="arrowP" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
        <path d="M0,0 L10,5 L0,10 z" fill="#8a4b2f"/>
      </marker>
    </defs>
    """
    return _svg(body, title="Axial member")
