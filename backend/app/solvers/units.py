"""Lightweight quantity parsing and SI-N-mm conversion (pint optional)."""

from __future__ import annotations

import math
import re
from typing import Any

_PINT = None
try:
    import pint  # type: ignore

    _PINT = pint.UnitRegistry()
except Exception:  # pragma: no cover - pint is optional
    _PINT = None

# Canonical SI-N-mm base units used internally by solvers.
_LENGTH_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "km": 1_000_000.0,
}

_FORCE_TO_N = {
    "n": 1.0,
    "kn": 1000.0,
    "mn": 1_000_000.0,
}

# Compound unit aliases → (kind, scale_to_base)
# kind: "force" | "length" | "force_per_length" | "moment" | "stress" | "dimensionless"
_ALIASES: dict[str, tuple[str, float]] = {
    "n": ("force", 1.0),
    "kn": ("force", 1000.0),
    "mn": ("force", 1_000_000.0),
    "mm": ("length", 1.0),
    "cm": ("length", 10.0),
    "m": ("length", 1000.0),
    "km": ("length", 1_000_000.0),
    # force / length → N/mm
    "n/mm": ("force_per_length", 1.0),
    "n/m": ("force_per_length", 1.0 / 1000.0),
    "kn/m": ("force_per_length", 1000.0 / 1000.0),  # 1 kN/m = 1 N/mm
    "kn/mm": ("force_per_length", 1000.0),
    "n/cm": ("force_per_length", 1.0 / 10.0),
    # moment → N·mm
    "nmm": ("moment", 1.0),
    "n·mm": ("moment", 1.0),
    "n.mm": ("moment", 1.0),
    "n-mm": ("moment", 1.0),
    "nm": ("moment", 1000.0),  # N·m
    "n·m": ("moment", 1000.0),
    "n.m": ("moment", 1000.0),
    "knm": ("moment", 1_000_000.0),  # kN·m → N·mm
    "kn·m": ("moment", 1_000_000.0),
    "kn.m": ("moment", 1_000_000.0),
    "kn-m": ("moment", 1_000_000.0),
    "knmm": ("moment", 1000.0),
    "kn·mm": ("moment", 1000.0),
    # stress → N/mm²
    "n/mm2": ("stress", 1.0),
    "n/mm²": ("stress", 1.0),
    "n/mm^2": ("stress", 1.0),
    "mpa": ("stress", 1.0),
    "n/m2": ("stress", 1e-6),
    "pa": ("stress", 1e-6),
    "kpa": ("stress", 1e-3),
    "kn/m2": ("stress", 1e-3),
    "kn/mm2": ("stress", 1000.0),
}


_QTY_RE = re.compile(
    r"""^\s*
    (?P<sign>[+-])?
    (?P<num>\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)
    \s*
    (?P<unit>[A-Za-zµμ°/%·.^²³2/\-]+)?
    \s*$
    """,
    re.VERBOSE,
)


def _norm_unit(unit: str) -> str:
    u = unit.strip().lower()
    u = (
        u.replace("µ", "u")
        .replace("μ", "u")
        .replace("²", "2")
        .replace("³", "3")
        .replace("**", "^")
        .replace(" ", "")
    )
    # unify middle dots / hyphens for compound moments
    u = u.replace("⋅", "·")
    return u


def parse_quantity(text: str | float | int | tuple | list) -> tuple[float, str]:
    """Parse a quantity string or number into (value, unit).

    Accepts:
      - "6 m", "20 kN/m", "145 kN", "12 mm"
      - bare numbers → unit ""
      - (value, unit) tuples/lists
    """
    if isinstance(text, (int, float)):
        return float(text), ""
    if isinstance(text, (tuple, list)) and len(text) >= 2:
        return float(text[0]), str(text[1])
    if not isinstance(text, str):
        raise TypeError(f"Cannot parse quantity from {type(text)!r}")

    s = text.strip()
    if not s:
        raise ValueError("Empty quantity string")

    # percentage like "15%" or "15 %"
    if s.endswith("%"):
        num = float(s[:-1].strip().replace(",", "."))
        return num, "%"

    m = _QTY_RE.match(s)
    if not m:
        # try pint fallback
        if _PINT is not None:
            q = _PINT.Quantity(s)
            return float(q.magnitude), str(q.units)
        raise ValueError(f"Cannot parse quantity: {text!r}")

    sign = -1.0 if m.group("sign") == "-" else 1.0
    num = sign * float(m.group("num").replace(",", "."))
    unit = m.group("unit") or ""
    return num, unit


def _convert(value: float, unit: str, expected_kind: str) -> float:
    if not unit:
        # already assumed to be in the target base unit
        return value

    key = _norm_unit(unit)
    if key in _ALIASES:
        kind, scale = _ALIASES[key]
        if kind != expected_kind:
            raise ValueError(
                f"Unit {unit!r} is {kind}, expected {expected_kind}"
            )
        return value * scale

    # pint fallback for exotic units
    if _PINT is not None:
        try:
            q = value * _PINT(unit)
            if expected_kind == "force":
                return float(q.to("newton").magnitude)
            if expected_kind == "length":
                return float(q.to("millimeter").magnitude)
            if expected_kind == "force_per_length":
                return float(q.to("newton / millimeter").magnitude)
            if expected_kind == "moment":
                return float(q.to("newton * millimeter").magnitude)
            if expected_kind == "stress":
                return float(q.to("newton / millimeter**2").magnitude)
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"Cannot convert {value} {unit} to {expected_kind}") from exc

    raise ValueError(f"Unknown unit {unit!r} for {expected_kind}")


def to_N(text: str | float | int | tuple | list) -> float:
    """Convert a force quantity to newtons."""
    v, u = parse_quantity(text)
    if not u:
        return v
    return _convert(v, u, "force")


def to_mm(text: str | float | int | tuple | list) -> float:
    """Convert a length quantity to millimetres."""
    v, u = parse_quantity(text)
    if not u:
        return v
    return _convert(v, u, "length")


def to_N_per_mm(text: str | float | int | tuple | list) -> float:
    """Convert a distributed force (UDL) to N/mm."""
    v, u = parse_quantity(text)
    if not u:
        return v
    return _convert(v, u, "force_per_length")


def to_Nmm(text: str | float | int | tuple | list) -> float:
    """Convert a moment quantity to N·mm."""
    v, u = parse_quantity(text)
    if not u:
        return v
    return _convert(v, u, "moment")


def to_stress_N_per_mm2(text: str | float | int | tuple | list) -> float:
    """Convert stress to N/mm² (= MPa)."""
    v, u = parse_quantity(text)
    if not u:
        return v
    return _convert(v, u, "stress")


def format_output(
    value: float,
    kind: str,
    *,
    digits: int = 4,
) -> tuple[float, str]:
    """Choose a friendly display unit.

    kind: "force" | "moment" | "length" | "stress" | "force_per_length" | "area"
    Returns (display_value, unit_string).
    """
    kind = kind.lower()
    if kind == "force":
        if abs(value) >= 1e6:
            return _round(value / 1e6, digits), "MN"
        if abs(value) >= 1000:
            return _round(value / 1000, digits), "kN"
        return _round(value, digits), "N"
    if kind == "moment":
        # value in N·mm
        if abs(value) >= 1e6:
            return _round(value / 1e6, digits), "kNm"
        if abs(value) >= 1000:
            return _round(value / 1000, digits), "Nm"
        return _round(value, digits), "Nmm"
    if kind == "length":
        if abs(value) >= 1000:
            return _round(value / 1000, digits), "m"
        return _round(value, digits), "mm"
    if kind == "stress":
        return _round(value, digits), "N/mm2"
    if kind == "force_per_length":
        # N/mm → prefer kN/m (numerically equal)
        return _round(value, digits), "kN/m"
    if kind == "area":
        return _round(value, digits), "mm2"
    return _round(value, digits), ""


def _round(v: float, digits: int) -> float:
    if not math.isfinite(v):
        return v
    return round(v, digits)


def coerce_number(x: Any) -> float:
    """Pull a float from a bare number, quantity string, or {value, unit} dict."""
    if isinstance(x, dict):
        if "value" in x:
            unit = x.get("unit") or ""
            if unit:
                return parse_quantity(f"{x['value']} {unit}")[0]
            return float(x["value"])
        raise TypeError(f"Cannot coerce dict without 'value': {x!r}")
    if isinstance(x, str):
        return parse_quantity(x)[0]
    return float(x)
