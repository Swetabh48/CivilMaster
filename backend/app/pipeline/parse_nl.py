"""Natural-language → topic solver spec (deterministic).

Parses common B.Tech phrasing into solver dicts. Does NOT invent answers —
only extracts givens. LLM gateway can replace/augment this when configured.
"""

from __future__ import annotations

import re
from typing import Any


def _num(pat: str, text: str, flags: int = re.I) -> float | None:
    m = re.search(pat, text, flags)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _span_mm(text: str) -> float | None:
    # span of 6 m / 6m span / length 3 m / L = 6 m
    m = re.search(
        r"(?:span|length|L)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(m|mm)\b",
        text,
        re.I,
    )
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(m|mm)\s+(?:span|long|cantilever)", text, re.I)
    if not m:
        return None
    v = float(m.group(1))
    return v if m.group(2).lower() == "mm" else v * 1000.0


def _force_N(text: str) -> float | None:
    m = re.search(
        r"(?:force|tension|load|Tu|P)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(kN|N)\b",
        text,
        re.I,
    )
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(kN|N)\b", text, re.I)
    if not m:
        return None
    v = float(m.group(1))
    return v * 1000.0 if m.group(2).lower() == "kn" else v


def _udl_N_per_mm(text: str) -> float | None:
    # UDL of 20 kN/m
    m = re.search(
        r"(?:UDL|uniformly\s+distributed\s+load|udl)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(kN/m|N/mm|N/m)\b",
        text,
        re.I,
    )
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(kN/m)\b", text, re.I)
    if not m:
        return None
    v = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "kn/m":
        return v  # 1 kN/m = 1 N/mm
    if unit == "n/mm":
        return v
    if unit == "n/m":
        return v / 1000.0
    return None


def _point_loads(text: str, span_mm: float) -> list[dict[str, Any]]:
    """Extract '20 kN at 1 m and 30 kN at 3 m from A' style loads."""
    loads: list[dict[str, Any]] = []
    for m in re.finditer(
        r"(\d+(?:\.\d+)?)\s*(kN|N)\s+at\s+(\d+(?:\.\d+)?)\s*(m|mm)",
        text,
        re.I,
    ):
        mag = float(m.group(1))
        if m.group(2).lower() == "kn":
            mag *= 1000.0
        pos = float(m.group(3))
        if m.group(4).lower() == "m":
            pos *= 1000.0
        loads.append({"kind": "point", "magnitude_N": mag, "position_mm": pos})
    return loads


def try_parse_problem(text: str) -> dict[str, Any] | None:
    """Return a solver spec dict, or None if no topic matched confidently."""
    t = text or ""
    lower = t.lower()

    # --- Soil phase ---
    if any(k in lower for k in ("void ratio", "degree of saturation", "bulk density", "water content")) and (
        "g =" in lower or "g=" in lower or "specific gravity" in lower
    ):
        G = _num(r"(?:G|specific\s+gravity)\s*[=:]\s*(\d+(?:\.\d+)?)", t)
        w = _num(r"(?:water\s+content|w)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*%?", t)
        rho = _num(r"(?:bulk\s+density|ρ|rho)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(?:g/cc|g/cm)", t)
        gamma = _num(r"(?:γ|gamma|unit\s+weight)\s*[=:]\s*(\d+(?:\.\d+)?)", t)
        if G is not None and w is not None and (rho is not None or gamma is not None):
            if w > 1.0:  # percent
                w = w / 100.0
            spec: dict[str, Any] = {"topic": "phase_relations", "G": G, "w": w}
            if rho is not None:
                spec["rho_g_cc"] = rho
            if gamma is not None:
                spec["gamma_kN_m3"] = gamma
            return spec

    # --- Section bending stress ---
    if (
        ("bending stress" in lower or "maximum bending stress" in lower or "σ" in t or "sigma" in lower)
        and re.search(r"(\d+)\s*mm\s*(?:wide|width|×|x)", lower)
    ):
        b = _num(r"(\d+(?:\.\d+)?)\s*mm\s*(?:wide|width)", t)
        d = _num(r"(\d+(?:\.\d+)?)\s*mm\s*(?:deep|depth|thick)", t)
        if b is None or d is None:
            m = re.search(
                r"(\d+(?:\.\d+)?)\s*mm\s*[×x]\s*(\d+(?:\.\d+)?)\s*mm",
                t,
                re.I,
            )
            if m:
                b, d = float(m.group(1)), float(m.group(2))
        M = _num(r"(?:bending\s+moment|M)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(kNm|kN·m|Nmm|N·mm)", t)
        M_unit = None
        mu = re.search(
            r"(?:bending\s+moment|M)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(kNm|kN·m|kN-m|Nmm|N·mm)",
            t,
            re.I,
        )
        if mu:
            M = float(mu.group(1))
            M_unit = mu.group(2).lower()
        if b and d and M is not None:
            M_Nmm = M * 1e6 if M_unit and "kn" in M_unit else M
            return {
                "topic": "bending_stress",
                "b_mm": b,
                "d_mm": d,
                "M_Nmm": M_Nmm,
            }

    # --- RCC LSM ---
    if any(k in lower for k in ("fe415", "fe250", "fe500", "m20", "m25", "factored moment", "singly reinforced", "lsm")) and (
        "beam" in lower or "ast" in lower or "mu" in lower or "moment" in lower
    ):
        dims = re.search(
            r"(\d+(?:\.\d+)?)\s*mm\s*[×x]\s*(\d+(?:\.\d+)?)\s*mm",
            t,
            re.I,
        )
        b = d = None
        if dims:
            b, d = float(dims.group(1)), float(dims.group(2))
        d2 = _num(r"effective\s+depth\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*mm", t)
        if d2:
            d = d2
        b2 = _num(r"(?:width|b)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*mm", t)
        if b2:
            b = b2
        Mu = None
        mu = re.search(
            r"(?:factored\s+moment|Mu|M_u)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*(kNm|kN·m|kN-m)",
            t,
            re.I,
        )
        if mu:
            Mu = float(mu.group(1)) * 1e6  # kNm → N·mm
        fck = 20.0 if "m20" in lower else (25.0 if "m25" in lower else None)
        fy = 415.0 if "fe415" in lower else (250.0 if "fe250" in lower else (500.0 if "fe500" in lower else None))
        fck_m = _num(r"fck\s*[=:]\s*(\d+(?:\.\d+)?)", t)
        fy_m = _num(r"fy\s*[=:]\s*(\d+(?:\.\d+)?)", t)
        if fck_m:
            fck = fck_m
        if fy_m:
            fy = fy_m
        if b and d and Mu and fck and fy:
            return {
                "topic": "rcc_singly_lsm",
                "b_mm": b,
                "d_mm": d,
                "Mu_Nmm": Mu,
                "fck": fck,
                "fy": fy,
            }

    # --- Steel bolted lap ---
    if ("lap joint" in lower or "bolted" in lower) and (
        "bolt" in lower or "m16" in lower or "m20" in lower or "m24" in lower
    ):
        Tu = _force_N(t)
        dm = re.search(r"M\s*(\d+)", t, re.I)
        d_bolt = float(dm.group(1)) if dm else None
        grade_m = re.search(r"grade\s*(\d+\.\d+)", t, re.I)
        grade = grade_m.group(1) if grade_m else "4.6"
        plate = re.search(
            r"(\d+(?:\.\d+)?)\s*mm\s*[×x]\s*(\d+(?:\.\d+)?)\s*mm",
            t,
            re.I,
        )
        t_mm = w_mm = None
        if plate:
            t_mm, w_mm = float(plate.group(1)), float(plate.group(2))
        if t_mm is None:
            t_mm = _num(r"(\d+(?:\.\d+)?)\s*mm\s*thick", t) or _num(
                r"plates?\s*(?:are|=|:)?\s*(\d+(?:\.\d+)?)\s*mm", t
            )
        if w_mm is None:
            w_mm = _num(r"(\d+(?:\.\d+)?)\s*mm\s*wide", t)
        steel = "E250"
        if "e250" in lower or "fe410" in lower:
            steel = "E250"
        if Tu and d_bolt and t_mm and w_mm:
            return {
                "topic": "is800_bolted_lap",
                "Tu_N": Tu,
                "bolt_d_mm": d_bolt,
                "bolt_grade": grade,
                "plate_t_mm": t_mm,
                "plate_w_mm": w_mm,
                "steel_grade": steel,
            }

    # --- Beams (SFD/BMD) ---
    is_beam = any(
        k in lower
        for k in (
            "simply supported",
            "cantilever",
            "sfd",
            "bmd",
            "bending moment",
            "shear force",
            "udl",
        )
    ) and ("beam" in lower or "cantilever" in lower or "span" in lower)
    if is_beam:
        support = "cantilever" if "cantilever" in lower else "simply_supported"
        L = _span_mm(t)
        if not L:
            return None
        loads = _point_loads(t, L)
        w = _udl_N_per_mm(t)
        if w is not None and not loads:
            loads = [
                {
                    "kind": "udl",
                    "magnitude_N_per_mm": w,
                    "start_mm": 0.0,
                    "end_mm": L,
                }
            ]
        if not loads:
            return None
        return {
            "topic": "beam_analysis",
            "support": support,
            "span_mm": L,
            "loads": loads,
        }

    return None
