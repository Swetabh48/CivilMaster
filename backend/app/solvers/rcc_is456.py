"""IS 456:2000 — singly reinforced rectangular section (LSM)."""

from __future__ import annotations

import math
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

# xu,max / d from IS 456 Annex G / Cl. 38.1 (limiting neutral axis)
_XU_MAX_RATIO = {
    250: 0.53,
    415: 0.48,
    500: 0.46,
}


def _xu_max_ratio(fy: float) -> float:
    fy_i = int(round(fy))
    if fy_i in _XU_MAX_RATIO:
        return _XU_MAX_RATIO[fy_i]
    # nearest known grade
    nearest = min(_XU_MAX_RATIO.keys(), key=lambda g: abs(g - fy))
    return _XU_MAX_RATIO[nearest]


def solve_rcc_singly(spec: dict[str, Any]) -> dict[str, Any]:
    """Singly reinforced LSM beam/section: Ast for given Mu."""
    subject = "RCC Design — IS 456 Singly Reinforced LSM"
    try:
        require(spec, "b_mm", "d_mm", "Mu_Nmm", "fck", "fy")
        b = float(spec["b_mm"])
        d = float(spec["d_mm"])
        Mu = float(spec["Mu_Nmm"])
        fck = float(spec["fck"])
        fy = float(spec["fy"])
        if b <= 0 or d <= 0 or Mu <= 0 or fck <= 0 or fy <= 0:
            raise NeedsInput(["b_mm, d_mm, Mu_Nmm, fck, fy (must be > 0)"])
    except NeedsInput as e:
        return empty_result(status="needs_input", subject=subject, missing=e.missing)

    given = [
        ("b", b, "mm"),
        ("d", d, "mm"),
        ("Mu", Mu, "Nmm"),
        ("fck", fck, "N/mm2"),
        ("fy", fy, "N/mm2"),
    ]

    steps: list[dict[str, Any]] = []
    xu_ratio = _xu_max_ratio(fy)
    xu_max = xu_ratio * d
    steps.append(
        step(
            "Limiting neutral-axis depth",
            "x_u,max / d = ratio(fy)",
            f"fy={fy:.4g} → x_u,max/d = {xu_ratio} → x_u,max = {xu_max:.4g} mm",
            xu_max,
            "mm",
            clause="IS 456:2000 Cl. 38.1 / Annex G",
        )
    )

    # Mu,lim = 0.36 fck b xu_max (d − 0.42 xu_max)
    Mu_lim = 0.36 * fck * b * xu_max * (d - 0.42 * xu_max)
    steps.append(
        step(
            "Limiting moment of resistance",
            "M_u,lim = 0.36 f_ck b x_u,max (d − 0.42 x_u,max)",
            f"= 0.36×{fck}×{b}×{xu_max:.4g}×({d}−0.42×{xu_max:.4g}) = {Mu_lim:.4g} N·mm",
            Mu_lim,
            "Nmm",
            clause="IS 456:2000 Annex G",
        )
    )

    # Also show Fe415 shortcut when applicable
    if abs(fy - 415.0) < 1.0:
        Mu_lim_alt = 0.138 * fck * b * d**2
        steps.append(
            step(
                "Check Mu,lim (Fe415 shortcut)",
                "M_u,lim ≈ 0.138 f_ck b d²",
                f"= 0.138×{fck}×{b}×{d}² = {Mu_lim_alt:.4g} N·mm",
                Mu_lim_alt,
                "Nmm",
                clause="IS 456:2000 (Fe415)",
            )
        )
        # Prefer the closed form for Fe415 consistency with textbook
        Mu_lim = Mu_lim_alt

    Mu_disp, Mu_u = format_output(Mu, "moment")
    Mulim_disp, Mulim_u = format_output(Mu_lim, "moment")

    under_reinforced = Mu <= Mu_lim + 1e-6
    checks = [
        check(
            "Mu ≤ Mu,lim (singly reinforced)",
            under_reinforced,
            f"Mu={Mu_disp} {Mu_u}, Mu,lim={Mulim_disp} {Mulim_u}",
        )
    ]

    answers = [
        answer("Mu_lim", Mulim_disp, Mulim_u),
        answer("xu_max", round(xu_max, 4), "mm"),
        answer("xu_max/d", xu_ratio, ""),
    ]

    if not under_reinforced:
        steps.append(
            step(
                "Section classification",
                "Mu > Mu,lim → doubly reinforced / revise section",
                f"Mu={Mu:.4g} > Mu,lim={Mu_lim:.4g} N·mm",
                None,
                "",
                clause="IS 456:2000 Cl. 38.1",
            )
        )
        answers.append(answer("Ast", "doubly reinforced / revise", ""))
        drawing_data = {
            "kind": "rcc_section",
            "b_mm": b,
            "d_mm": d,
            "fck": fck,
            "fy": fy,
            "Mu_Nmm": Mu,
            "Mu_lim_Nmm": Mu_lim,
            "Ast_mm2": None,
            "singly": False,
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

    # Ast = 0.5 fck/fy (1 − sqrt(1 − 4.6 Mu/(fck b d²))) b d
    arg = 4.6 * Mu / (fck * b * d**2)
    if arg > 1.0:
        # numerical clamp — should not happen if Mu ≤ Mu,lim for Fe415
        arg = min(arg, 0.999999)
    Ast = 0.5 * (fck / fy) * (1.0 - math.sqrt(1.0 - arg)) * b * d
    steps.append(
        step(
            "Area of tension steel",
            "A_st = 0.5 (f_ck/f_y) [1 − √(1 − 4.6 M_u/(f_ck b d²))] b d",
            f"4.6 Mu/(fck b d²)={arg:.6g} → A_st={Ast:.4g} mm²",
            Ast,
            "mm2",
            clause="IS 456:2000 Annex G / SP 16",
        )
    )

    # Min steel check (Cl. 26.5.1.1): Ast,min = 0.85 bd / fy
    Ast_min = 0.85 * b * d / fy
    steps.append(
        step(
            "Minimum tension steel",
            "A_st,min = 0.85 b d / f_y",
            f"= 0.85×{b}×{d}/{fy} = {Ast_min:.4g} mm²",
            Ast_min,
            "mm2",
            clause="IS 456:2000 Cl. 26.5.1.1",
        )
    )
    Ast_prov = max(Ast, Ast_min)
    checks.append(
        check(
            "Ast ≥ Ast,min",
            Ast + 1e-9 >= Ast_min,
            f"Ast={Ast:.4g} mm², Ast,min={Ast_min:.4g} mm²",
        )
    )

    answers.append(answer("Ast", round(Ast, 4), "mm2"))
    answers.append(answer("Ast_min", round(Ast_min, 4), "mm2"))
    if Ast_prov > Ast:
        answers.append(answer("Ast_provide", round(Ast_prov, 4), "mm2"))

    drawing_data = {
        "kind": "rcc_section",
        "b_mm": b,
        "d_mm": d,
        "fck": fck,
        "fy": fy,
        "Mu_Nmm": Mu,
        "Mu_lim_Nmm": Mu_lim,
        "Ast_mm2": Ast,
        "xu_max_mm": xu_max,
        "singly": True,
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
