"""IS 800:2007 — bolted lap joint design (shear + bearing)."""

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

# Bolt ultimate stress from grade: first digit × 100 (N/mm²)
_BOLT_FU = {
    "4.6": 400.0,
    "4.8": 400.0,
    "5.6": 500.0,
    "5.8": 500.0,
    "6.8": 600.0,
    "8.8": 800.0,
    "10.9": 1000.0,
}

# Plate fu from steel grade (IS 2062 / IS 800 Table)
_PLATE_FU = {
    "E250": 410.0,
    "E410": 540.0,
    "E450": 570.0,
    "Fe410": 410.0,
    "Fe250": 410.0,
}

GAMMA_MB = 1.25


def solve_steel_bolted_lap(spec: dict[str, Any]) -> dict[str, Any]:
    """Design number of bolts for a lap joint (IS 800 Cl. 10.3)."""
    subject = "Steel Design — IS 800 Bolted Lap Joint"
    try:
        require(spec, "Tu_N", "bolt_d_mm", "bolt_grade", "plate_t_mm", "plate_w_mm", "steel_grade")
        Tu = float(spec["Tu_N"])
        d = float(spec["bolt_d_mm"])
        grade = str(spec["bolt_grade"]).strip()
        t = float(spec["plate_t_mm"])
        w = float(spec["plate_w_mm"])
        steel = str(spec["steel_grade"]).strip()
        kb = float(spec.get("kb", 0.5))
        nn = int(spec.get("nn", 1))  # shear planes; lap → 1
        if d <= 0 or t <= 0 or Tu <= 0:
            raise NeedsInput(["bolt_d_mm / plate_t_mm / Tu_N (must be > 0)"])
        fu_bolt = _BOLT_FU.get(grade)
        if fu_bolt is None:
            raise NeedsInput([f"bolt_grade (unsupported: {grade!r})"])
        fu_plate = _PLATE_FU.get(steel) or _PLATE_FU.get(steel.upper())
        if fu_plate is None:
            # try numeric override
            if "fu_plate" in spec:
                fu_plate = float(spec["fu_plate"])
            else:
                raise NeedsInput([f"steel_grade (unsupported: {steel!r})"])
    except NeedsInput as e:
        return empty_result(status="needs_input", subject=subject, missing=e.missing)

    given = [
        ("Tu", Tu, "N"),
        ("d", d, "mm"),
        ("bolt_grade", grade, ""),
        ("t", t, "mm"),
        ("w", w, "mm"),
        ("steel_grade", steel, ""),
        ("kb", kb, ""),
        ("nn", nn, ""),
    ]

    steps: list[dict[str, Any]] = []

    # Net shear area of bolt
    Anb = 0.78 * math.pi * d**2 / 4.0
    steps.append(
        step(
            "Net shear area of bolt",
            "A_nb = 0.78 · (π d² / 4)",
            f"d={d:.4g} mm → A_nb = {Anb:.4g} mm²",
            Anb,
            "mm2",
            clause="IS 800:2007 Cl. 10.3.3",
        )
    )

    # Nominal shear capacity
    Vnsb = (fu_bolt / math.sqrt(3.0)) * nn * Anb
    steps.append(
        step(
            "Nominal shear capacity of bolt",
            "V_nsb = (f_u / √3) · n_n · A_nb",
            f"f_u={fu_bolt:.4g} N/mm² (grade {grade}), n_n={nn} → V_nsb={Vnsb:.4g} N",
            Vnsb,
            "N",
            clause="IS 800:2007 Cl. 10.3.3",
        )
    )

    Vdb = Vnsb / GAMMA_MB
    steps.append(
        step(
            "Design shear strength of bolt",
            "V_db = V_nsb / γ_mb",
            f"γ_mb={GAMMA_MB} → V_db={Vdb:.4g} N",
            Vdb,
            "N",
            clause="IS 800:2007 Cl. 10.3.3",
        )
    )

    # Bearing strength
    Vdpb = 2.5 * kb * d * t * fu_plate / GAMMA_MB
    steps.append(
        step(
            "Design bearing strength of bolt",
            "V_dpb = 2.5 · k_b · d · t · f_u / γ_mb",
            f"k_b={kb}, d={d}, t={t}, f_u,plate={fu_plate} → V_dpb={Vdpb:.4g} N",
            Vdpb,
            "N",
            clause="IS 800:2007 Cl. 10.3.4",
        )
    )

    V_bolt = min(Vdb, Vdpb)
    governing = "shear" if Vdb <= Vdpb else "bearing"
    steps.append(
        step(
            "Bolt strength (governing)",
            "V_bolt = min(V_db, V_dpb)",
            f"min({Vdb:.4g}, {Vdpb:.4g}) = {V_bolt:.4g} N ({governing})",
            V_bolt,
            "N",
            clause="IS 800:2007 Cl. 10.3",
        )
    )

    n = math.ceil(Tu / V_bolt) if V_bolt > 0 else 0
    steps.append(
        step(
            "Number of bolts required",
            "n = ⌈ T_u / V_bolt ⌉",
            f"T_u={Tu:.4g} N → n = {n}",
            n,
            "",
            clause="IS 800:2007 Cl. 10.3",
        )
    )

    pitch = 2.5 * d
    edge = 1.5 * d
    steps.append(
        step(
            "Minimum pitch",
            "p ≥ 2.5 d",
            f"p_min = 2.5×{d:.4g} = {pitch:.4g} mm",
            pitch,
            "mm",
            clause="IS 800:2007 Cl. 10.2.2",
        )
    )
    steps.append(
        step(
            "Minimum edge distance",
            "e ≥ 1.5 d_h ≈ 1.5 d (for standard holes)",
            f"e_min = 1.5×{d:.4g} = {edge:.4g} mm",
            edge,
            "mm",
            clause="IS 800:2007 Cl. 10.2.4",
        )
    )

    capacity = n * V_bolt
    ok_cap = capacity + 1e-9 >= Tu
    checks = [
        check(
            "Capacity ≥ Tu",
            ok_cap,
            f"n·V_bolt={capacity:.4g} N vs Tu={Tu:.4g} N",
        ),
        check(
            "Pitch ≥ 2.5d",
            True,
            f"Adopt p ≥ {pitch:.4g} mm",
        ),
        check(
            "Edge ≥ 1.5d",
            True,
            f"Adopt e ≥ {edge:.4g} mm",
        ),
    ]

    Tu_d, Tu_u = format_output(Tu, "force")
    Vdb_d, Vdb_u = format_output(Vdb, "force")
    Vdpb_d, Vdpb_u = format_output(Vdpb, "force")
    Vbolt_d, Vbolt_u = format_output(V_bolt, "force")

    answers = [
        answer("n_bolts", n, ""),
        answer("V_db", Vdb_d, Vdb_u),
        answer("V_dpb", Vdpb_d, Vdpb_u),
        answer("V_bolt", Vbolt_d, Vbolt_u),
        answer("pitch_min", pitch, "mm"),
        answer("edge_min", edge, "mm"),
        answer("Anb", round(Anb, 4), "mm2"),
        answer("Tu", Tu_d, Tu_u),
    ]

    # Simple single-row layout for drawing
    drawing_data = {
        "kind": "bolted_lap_joint",
        "Tu_N": Tu,
        "bolt_d_mm": d,
        "bolt_grade": grade,
        "plate_t_mm": t,
        "plate_w_mm": w,
        "steel_grade": steel,
        "n_bolts": n,
        "pitch_mm": pitch,
        "edge_mm": edge,
        "V_db_N": Vdb,
        "V_dpb_N": Vdpb,
        "V_bolt_N": V_bolt,
        "governing": governing,
        "layout": {
            "rows": 1,
            "cols": n,
            "pitch_mm": pitch,
            "edge_mm": edge,
        },
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
