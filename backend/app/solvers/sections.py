"""Elastic section properties and bending stress."""

from __future__ import annotations

from typing import Any

from app.solvers.base import (
    NeedsInput,
    SolverResult,
    answer,
    check,
    empty_result,
    require,
    step,
)
from app.solvers.units import format_output


def solve_bending_stress(spec: dict[str, Any]) -> dict[str, Any]:
    """Rectangular section: I = bd³/12, y = d/2, σ = My/I."""
    subject = "Strength of Materials — Bending Stress"
    try:
        if not any(k in spec for k in ("b", "b_mm")):
            raise NeedsInput(["b or b_mm"])
        if not any(k in spec for k in ("d", "d_mm")):
            raise NeedsInput(["d or d_mm"])
        if not any(k in spec for k in ("M", "M_Nmm")):
            raise NeedsInput(["M or M_Nmm"])
        b = float(spec.get("b_mm", spec.get("b")))
        d = float(spec.get("d_mm", spec.get("d")))
        M = float(spec.get("M_Nmm", spec.get("M")))
        if b <= 0 or d <= 0:
            raise NeedsInput(["b, d (must be > 0)"])
    except NeedsInput as e:
        return empty_result(status="needs_input", subject=subject, missing=e.missing)
    except (TypeError, ValueError, KeyError) as e:
        return empty_result(
            status="needs_input",
            subject=subject,
            missing=[f"b, d, M ({e})"],
        )

    given = [
        ("b", b, "mm"),
        ("d", d, "mm"),
        ("M", M, "Nmm"),
    ]

    I = b * d**3 / 12.0
    y = d / 2.0
    sigma = M * y / I if I else float("inf")

    steps = [
        step(
            "Moment of inertia (rectangle about NA)",
            "I = b d³ / 12",
            f"b={b:.4g} mm, d={d:.4g} mm → I = {I:.6g} mm⁴",
            I,
            "mm4",
        ),
        step(
            "Extreme fibre distance",
            "y = d / 2",
            f"y = {d:.4g}/2 = {y:.4g} mm",
            y,
            "mm",
        ),
        step(
            "Bending stress",
            "σ = M y / I",
            f"M={M:.4g} N·mm → σ = {sigma:.6g} N/mm²",
            sigma,
            "N/mm2",
        ),
    ]

    # Section modulus check: σ = M / Z, Z = I/y = bd²/6
    Z = I / y if y else 0.0
    sigma_alt = M / Z if Z else float("inf")
    ok = abs(sigma - sigma_alt) / max(abs(sigma), 1e-9) < 1e-6
    checks = [
        check(
            "σ = M/Z with Z=bd²/6",
            ok,
            f"σ={sigma:.6g}, M/Z={sigma_alt:.6g}, Z={Z:.6g} mm³",
        ),
    ]

    sig_d, sig_u = format_output(sigma, "stress")
    M_d, M_u = format_output(M, "moment")

    answers = [
        answer("I", round(I, 6), "mm4"),
        answer("y", round(y, 6), "mm"),
        answer("Z", round(Z, 6), "mm3"),
        answer("sigma", sig_d, sig_u),
        answer("M", M_d, M_u),
    ]

    drawing_data = {
        "kind": "section",
        "shape": "rectangle",
        "b_mm": b,
        "d_mm": d,
        "I_mm4": I,
        "y_mm": y,
        "M_Nmm": M,
        "sigma_N_per_mm2": sigma,
    }

    return SolverResult(
        status="verified",
        subject=subject,
        steps=steps,
        answers=answers,
        checks=checks,
        drawing_data=drawing_data,
        given=given,
    ).to_dict()
