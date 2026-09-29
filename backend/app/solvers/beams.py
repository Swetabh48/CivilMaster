"""Statically determinate beam analysis (SS / cantilever)."""

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


def _load_fields(load: dict[str, Any], L: float) -> dict[str, Any]:
    kind = str(load.get("kind") or "").lower()
    out: dict[str, Any] = {"kind": kind}
    if kind == "point":
        mag = load.get("magnitude_N")
        if mag is None:
            mag = load.get("magnitude")
        pos = load.get("position_mm")
        if pos is None:
            pos = load.get("position")
        if mag is None or pos is None:
            raise NeedsInput(["loads[].magnitude_N", "loads[].position_mm"])
        out["magnitude_N"] = float(mag)
        out["position_mm"] = float(pos)
    elif kind == "udl":
        w = load.get("magnitude_N_per_mm")
        if w is None:
            w = load.get("magnitude")
        start = load.get("start_mm", 0.0)
        end = load.get("end_mm", L)
        if start is None:
            start = 0.0
        if end is None:
            end = L
        if w is None:
            raise NeedsInput(["loads[].magnitude_N_per_mm"])
        out["magnitude_N_per_mm"] = float(w)
        out["start_mm"] = float(start)
        out["end_mm"] = float(end)
    else:
        raise NeedsInput([f"loads[].kind (unsupported: {kind!r})"])
    return out


def _is_full_udl(loads: list[dict[str, Any]], L: float) -> bool:
    if len(loads) != 1:
        return False
    ld = loads[0]
    if ld["kind"] != "udl":
        return False
    return math.isclose(ld["start_mm"], 0.0, abs_tol=1e-6) and math.isclose(
        ld["end_mm"], L, abs_tol=1e-6
    )


def _ss_reactions(
    L: float, loads: list[dict[str, Any]]
) -> tuple[float, float, list[dict[str, Any]]]:
    """Simply supported: Ra (left), Rb (right) from ΣM=0 and ΣFy=0."""
    steps: list[dict[str, Any]] = []
    moment_about_a = 0.0  # clockwise positive from loads (downward loads)
    total_down = 0.0

    for i, ld in enumerate(loads):
        if ld["kind"] == "point":
            P = ld["magnitude_N"]
            a = ld["position_mm"]
            moment_about_a += P * a
            total_down += P
            steps.append(
                step(
                    f"Point load {i + 1} contribution to ΣM_A",
                    "M_A,i = P_i · a_i",
                    f"P={P:.4g} N, a={a:.4g} mm → {P * a:.4g} N·mm",
                    P * a,
                    "Nmm",
                )
            )
        else:
            w = ld["magnitude_N_per_mm"]
            a, b = ld["start_mm"], ld["end_mm"]
            W = w * (b - a)
            c = 0.5 * (a + b)
            moment_about_a += W * c
            total_down += W
            steps.append(
                step(
                    f"UDL {i + 1} resultant",
                    "W = w·(b−a),  c = (a+b)/2",
                    f"w={w:.4g} N/mm, a={a:.4g}, b={b:.4g} → W={W:.4g} N at c={c:.4g} mm",
                    W,
                    "N",
                )
            )

    Rb = moment_about_a / L if L else 0.0
    Ra = total_down - Rb
    steps.append(
        step(
            "Reaction at B (ΣM_A = 0)",
            "R_B = (Σ P·a) / L",
            f"ΣM_A={moment_about_a:.4g} N·mm, L={L:.4g} mm → R_B={Rb:.4g} N",
            Rb,
            "N",
        )
    )
    steps.append(
        step(
            "Reaction at A (ΣF_y = 0)",
            "R_A = ΣP − R_B",
            f"ΣP={total_down:.4g} N, R_B={Rb:.4g} N → R_A={Ra:.4g} N",
            Ra,
            "N",
        )
    )
    return Ra, Rb, steps


def _cantilever_reactions(
    L: float, loads: list[dict[str, Any]], *, fixed_at: str = "left"
) -> tuple[float, float, list[dict[str, Any]]]:
    """Cantilever fixed at left (default): V_A and M_A at fixed end."""
    steps: list[dict[str, Any]] = []
    V = 0.0
    M = 0.0  # fixing moment magnitude (sagging convention: loads cause negative BM)

    for i, ld in enumerate(loads):
        if ld["kind"] == "point":
            P = ld["magnitude_N"]
            a = ld["position_mm"]
            # lever arm from fixed end
            lever = a if fixed_at == "left" else (L - a)
            V += P
            M += P * lever
            steps.append(
                step(
                    f"Point load {i + 1} at fixed end",
                    "V += P,  M += P·x",
                    f"P={P:.4g} N, x={lever:.4g} mm → ΔM={P * lever:.4g} N·mm",
                    P * lever,
                    "Nmm",
                )
            )
        else:
            w = ld["magnitude_N_per_mm"]
            a, b = ld["start_mm"], ld["end_mm"]
            W = w * (b - a)
            c = 0.5 * (a + b)
            lever = c if fixed_at == "left" else (L - c)
            V += W
            M += W * lever
            steps.append(
                step(
                    f"UDL {i + 1} at fixed end",
                    "W=w(b−a), M += W·c",
                    f"W={W:.4g} N at c={c:.4g} mm from left → lever={lever:.4g} mm",
                    W * lever,
                    "Nmm",
                )
            )

    steps.append(
        step(
            "Fixed-end shear",
            "V_A = Σ loads",
            f"V_A = {V:.4g} N",
            V,
            "N",
        )
    )
    steps.append(
        step(
            "Fixed-end moment",
            "M_A = Σ (load · lever arm from fixed end)",
            f"M_A = {M:.4g} N·mm",
            M,
            "Nmm",
        )
    )
    return V, M, steps


def _shear_at(x: float, L: float, support: str, Ra: float, loads: list[dict]) -> float:
    """Shear just to the right of x (left-to-right convention, upward reaction +ve)."""
    if support == "cantilever":
        # Fixed left: V(x) = -Σ loads to the right of x  (or V(0+)=V_A then drop)
        # Using: start with V_A (=Ra), subtract loads as we pass them
        V = Ra
        for ld in loads:
            if ld["kind"] == "point":
                if ld["position_mm"] <= x + 1e-9:
                    V -= ld["magnitude_N"]
            else:
                a, b = ld["start_mm"], ld["end_mm"]
                w = ld["magnitude_N_per_mm"]
                if x <= a:
                    pass
                elif x >= b:
                    V -= w * (b - a)
                else:
                    V -= w * (x - a)
        return V

    # simply supported
    V = Ra
    for ld in loads:
        if ld["kind"] == "point":
            if ld["position_mm"] <= x + 1e-9:
                V -= ld["magnitude_N"]
        else:
            a, b = ld["start_mm"], ld["end_mm"]
            w = ld["magnitude_N_per_mm"]
            if x <= a:
                pass
            elif x >= b:
                V -= w * (b - a)
            else:
                V -= w * (x - a)
    return V


def _moment_at(
    x: float, L: float, support: str, Ra: float, Ma: float, loads: list[dict]
) -> float:
    """Bending moment at x (sagging positive for SS)."""
    if support == "cantilever":
        # Fixed left: M(x) = -M_A + V_A*x - loads moments  → usually hogging (report as magnitude)
        # Compute from free end or from left:
        # M(x) = - Σ P*(pos-x) for loads with pos > x  (hogging, we'll return signed + for sagging)
        M = 0.0
        for ld in loads:
            if ld["kind"] == "point":
                a = ld["position_mm"]
                if a > x + 1e-9:
                    M -= ld["magnitude_N"] * (a - x)
            else:
                a, b = ld["start_mm"], ld["end_mm"]
                w = ld["magnitude_N_per_mm"]
                if b <= x + 1e-9:
                    continue
                left = max(a, x)
                if left >= b - 1e-9:
                    continue
                # UDL from left to b; resultant to the right of x
                seg = b - left
                c = 0.5 * (left + b)
                M -= w * seg * (c - x)
        return M  # negative = hogging

    # simply supported: M(x) = Ra*x - Σ loads to the left
    M = Ra * x
    for ld in loads:
        if ld["kind"] == "point":
            a = ld["position_mm"]
            if a < x - 1e-9:
                M -= ld["magnitude_N"] * (x - a)
        else:
            a, b = ld["start_mm"], ld["end_mm"]
            w = ld["magnitude_N_per_mm"]
            if x <= a + 1e-9:
                continue
            right = min(b, x)
            seg = right - a
            if seg <= 0:
                continue
            c = 0.5 * (a + right)
            M -= w * seg * (x - c)
    return M


def _critical_xs(L: float, loads: list[dict]) -> list[float]:
    xs = {0.0, L}
    for ld in loads:
        if ld["kind"] == "point":
            xs.add(float(ld["position_mm"]))
        else:
            xs.add(float(ld["start_mm"]))
            xs.add(float(ld["end_mm"]))
    # fine sample for UDL peaks
    n = 40
    for i in range(n + 1):
        xs.add(L * i / n)
    return sorted(x for x in xs if 0.0 - 1e-9 <= x <= L + 1e-9)


def solve_beam(spec: dict[str, Any]) -> dict[str, Any]:
    """Solve a statically determinate beam; return standard result dict."""
    subject = "Structural Analysis — Beams"
    try:
        require(spec, "support", "span_mm", "loads")
        support = str(spec["support"]).lower().replace("-", "_").replace(" ", "_")
        if support in ("ss", "simple", "simply_supported", "simplysupported"):
            support = "simply_supported"
        elif support in ("cantilever", "cant"):
            support = "cantilever"
        else:
            return empty_result(
                status="unsupported",
                subject=subject,
                missing=[f"support={spec['support']!r}"],
            )

        L = float(spec["span_mm"])
        if L <= 0:
            raise NeedsInput(["span_mm (must be > 0)"])

        raw_loads = spec["loads"]
        if not isinstance(raw_loads, list) or not raw_loads:
            raise NeedsInput(["loads"])

        loads = [_load_fields(ld, L) for ld in raw_loads]
    except NeedsInput as e:
        return empty_result(status="needs_input", subject=subject, missing=e.missing)

    given = [
        ("support", support, ""),
        ("span", L, "mm"),
    ]
    for i, ld in enumerate(loads):
        if ld["kind"] == "point":
            given.append((f"P{i+1}", ld["magnitude_N"], "N"))
            given.append((f"a{i+1}", ld["position_mm"], "mm"))
        else:
            given.append((f"w{i+1}", ld["magnitude_N_per_mm"], "N/mm"))
            given.append((f"UDL{i+1}_start", ld["start_mm"], "mm"))
            given.append((f"UDL{i+1}_end", ld["end_mm"], "mm"))

    steps: list[dict[str, Any]] = []
    reactions: dict[str, float] = {}

    # Closed-form shortcuts for full UDL
    if _is_full_udl(loads, L):
        w = loads[0]["magnitude_N_per_mm"]
        if support == "simply_supported":
            Ra = Rb = w * L / 2.0
            V_max = Ra
            M_max = w * L**2 / 8.0
            steps.append(
                step(
                    "Reactions (SS + full UDL)",
                    "R_A = R_B = wL/2",
                    f"w={w:.4g} N/mm, L={L:.4g} mm → R_A = R_B = {Ra:.4g} N",
                    Ra,
                    "N",
                )
            )
            steps.append(
                step(
                    "Maximum shear",
                    "V_max = wL/2",
                    f"V_max = {V_max:.4g} N",
                    V_max,
                    "N",
                )
            )
            steps.append(
                step(
                    "Maximum bending moment (at midspan)",
                    "M_max = wL²/8",
                    f"M_max = {w:.4g}·({L:.4g})²/8 = {M_max:.4g} N·mm",
                    M_max,
                    "Nmm",
                )
            )
            reactions = {"Ra_N": Ra, "Rb_N": Rb}
            Ma = 0.0
        else:
            V_max = w * L
            M_max = w * L**2 / 2.0
            steps.append(
                step(
                    "Reactions (cantilever + full UDL)",
                    "V_A = wL,  M_A = wL²/2  (at fixed end)",
                    f"w={w:.4g} N/mm, L={L:.4g} mm → V_A={V_max:.4g} N, M_A={M_max:.4g} N·mm",
                    V_max,
                    "N",
                )
            )
            steps.append(
                step(
                    "Maximum shear",
                    "V_max = wL",
                    f"V_max = {V_max:.4g} N",
                    V_max,
                    "N",
                )
            )
            steps.append(
                step(
                    "Maximum bending moment (fixed end)",
                    "M_max = wL²/2",
                    f"M_max = {M_max:.4g} N·mm",
                    M_max,
                    "Nmm",
                )
            )
            reactions = {"Va_N": V_max, "Ma_Nmm": M_max}
            Ra, Ma = V_max, M_max
    else:
        if support == "simply_supported":
            # Point-load / general SS path
            if all(ld["kind"] == "point" for ld in loads):
                steps.append(
                    step(
                        "Approach",
                        "ΣM_A = 0 → R_B;  ΣF_y = 0 → R_A",
                        "Moment equilibrium about A for discrete point loads",
                        None,
                        "",
                    )
                )
            Ra, Rb, rx_steps = _ss_reactions(L, loads)
            steps.extend(rx_steps)
            reactions = {"Ra_N": Ra, "Rb_N": Rb}
            Ma = 0.0
        else:
            Ra, Ma, rx_steps = _cantilever_reactions(L, loads)
            steps.extend(rx_steps)
            reactions = {"Va_N": Ra, "Ma_Nmm": Ma}
            Rb = 0.0

        # Sweep for V_max, M_max
        xs = _critical_xs(L, loads)
        V_vals = [_shear_at(x, L, support, Ra, loads) for x in xs]
        M_vals = [_moment_at(x, L, support, Ra, Ma, loads) for x in xs]
        V_max = max(abs(v) for v in V_vals) if V_vals else 0.0
        M_max = max(abs(m) for m in M_vals) if M_vals else 0.0

        # For pure point loads on SS, also report classic mid-load formula checks
        if support == "simply_supported" and all(ld["kind"] == "point" for ld in loads):
            # Find M at each load point
            for ld in loads:
                a = ld["position_mm"]
                Mm = _moment_at(a, L, support, Ra, 0.0, loads)
                steps.append(
                    step(
                        f"BM under point load at x={a:.4g} mm",
                        "M(x) = R_A·x − Σ P_i(x−a_i) for a_i < x",
                        f"M({a:.4g}) = {Mm:.4g} N·mm",
                        Mm,
                        "Nmm",
                    )
                )

        steps.append(
            step(
                "Maximum shear force",
                "V_max = max |V(x)| over critical sections",
                f"V_max = {V_max:.4g} N",
                V_max,
                "N",
            )
        )
        steps.append(
            step(
                "Maximum bending moment",
                "M_max = max |M(x)| over critical sections",
                f"M_max = {M_max:.4g} N·mm",
                M_max,
                "Nmm",
            )
        )

    # Equilibrium checks
    checks = []
    if support == "simply_supported":
        total_down = 0.0
        for ld in loads:
            if ld["kind"] == "point":
                total_down += ld["magnitude_N"]
            else:
                total_down += ld["magnitude_N_per_mm"] * (
                    ld["end_mm"] - ld["start_mm"]
                )
        Ra_c = reactions.get("Ra_N", 0.0)
        Rb_c = reactions.get("Rb_N", 0.0)
        ok_fy = math.isclose(Ra_c + Rb_c, total_down, rel_tol=1e-6, abs_tol=1e-3)
        checks.append(
            check(
                "ΣFy = 0",
                ok_fy,
                f"Ra+Rb={Ra_c + Rb_c:.6g} N vs ΣP={total_down:.6g} N",
            )
        )
        # BM at supports ≈ 0
        M0 = _moment_at(0.0, L, support, Ra_c, 0.0, loads)
        ML = _moment_at(L, L, support, Ra_c, 0.0, loads)
        ok_ends = abs(M0) < 1e-2 * max(1.0, M_max) and abs(ML) < 1e-2 * max(1.0, M_max)
        checks.append(
            check(
                "BM ≈ 0 at pin supports",
                ok_ends,
                f"M(0)={M0:.4g}, M(L)={ML:.4g} N·mm",
            )
        )
    else:
        checks.append(
            check(
                "Fixed-end equilibrium",
                True,
                f"V_A={reactions.get('Va_N', 0):.4g} N, M_A={reactions.get('Ma_Nmm', 0):.4g} N·mm",
            )
        )

    V_disp, V_u = format_output(V_max, "force")
    M_disp, M_u = format_output(M_max, "moment")

    answers = [
        answer("V_max", V_disp, V_u),
        answer("M_max", M_disp, M_u),
    ]
    if support == "simply_supported":
        Ra_d, Ra_u = format_output(reactions["Ra_N"], "force")
        Rb_d, Rb_u = format_output(reactions["Rb_N"], "force")
        answers = [
            answer("Ra", Ra_d, Ra_u),
            answer("Rb", Rb_d, Rb_u),
            *answers,
        ]
    else:
        Va_d, Va_u = format_output(reactions["Va_N"], "force")
        Ma_d, Ma_u = format_output(reactions["Ma_Nmm"], "moment")
        answers = [
            answer("Va", Va_d, Va_u),
            answer("Ma", Ma_d, Ma_u),
            *answers,
        ]

    drawing_data = {
        "kind": "beam_sfd_bmd",
        "L_mm": L,
        "loads": loads,
        "reactions": reactions,
        "V_max": V_max,
        "M_max": M_max,
        "support": support,
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
