"""Soil phase relations (void ratio, degree of saturation)."""

from __future__ import annotations

from typing import Any

import sympy as sp

from app.solvers.base import (
    SolverResult,
    answer,
    check,
    empty_result,
    step,
)

GAMMA_W = 9.81  # kN/m³


def _as_decimal_w(w: float) -> float:
    """Accept water content as decimal (0.15) or percent (15)."""
    if w > 1.0:
        return w / 100.0
    return w


def solve_phase_relations(spec: dict[str, Any]) -> dict[str, Any]:
    """Compute e, S (and related) from any consistent subset of G, w, γ, ρ.

    Relations (γ in kN/m³):
      γ = G (1+w) γ_w / (1+e)   ⇒  e = G(1+w)·9.81/γ − 1
      S = w G / e
      γ (kN/m³) = ρ (g/cc) · 9.81
    """
    subject = "Geotechnical Engineering — Phase Relations"

    G = spec.get("G")
    w_raw = spec.get("w")
    gamma = spec.get("gamma_kN_m3")
    rho = spec.get("rho_g_cc")
    e_in = spec.get("e")
    S_in = spec.get("S")

    given: list[tuple[str, float | int | str, str]] = []

    if G is not None:
        G = float(G)
        given.append(("G", G, ""))

    w: float | None
    if w_raw is not None:
        if isinstance(w_raw, str) and w_raw.strip().endswith("%"):
            w = float(w_raw.strip().rstrip("%").strip()) / 100.0
        else:
            w_val = float(w_raw)
            if spec.get("w_is_percent"):
                w = w_val / 100.0
            else:
                w = _as_decimal_w(w_val)
        given.append(("w", w, "decimal"))
        given.append(("w_percent", w * 100.0, "%"))
    else:
        w = None

    if rho is not None and gamma is None:
        rho = float(rho)
        gamma = rho * GAMMA_W
        given.append(("rho", rho, "g/cc"))
        given.append(("gamma", gamma, "kN/m3"))
    elif gamma is not None:
        gamma = float(gamma)
        given.append(("gamma", gamma, "kN/m3"))
        if rho is not None:
            given.append(("rho", float(rho), "g/cc"))

    if e_in is not None:
        e_in = float(e_in)
        given.append(("e", e_in, ""))
    if S_in is not None:
        S_in = float(S_in)
        if S_in > 1.0:
            S_in = S_in / 100.0
        given.append(("S", S_in, "decimal"))

    steps: list[dict[str, Any]] = []

    # Path 1: G, w, gamma → e, S (sympy system solve)
    if G is not None and w is not None and gamma is not None:
        if gamma <= 0:
            return empty_result(
                status="needs_input",
                subject=subject,
                missing=["gamma_kN_m3 (must be > 0)"],
                given=given,
            )

        e_s, S_s, G_s, w_s, gam_s, gw = sp.symbols(
            "e S G w gamma gamma_w", positive=True
        )
        eqs = [
            sp.Eq(gam_s, G_s * (1 + w_s) * gw / (1 + e_s)),
            sp.Eq(S_s, w_s * G_s / e_s),
        ]
        sol = sp.solve(eqs, [e_s, S_s], dict=True)
        if not sol:
            return empty_result(status="unsupported", subject=subject, given=given)

        e = float(sol[0][e_s].subs({G_s: G, w_s: w, gam_s: gamma, gw: GAMMA_W}))
        S = float(sol[0][S_s].subs({G_s: G, w_s: w, gam_s: gamma, gw: GAMMA_W}))

        steps.append(
            step(
                "Bulk unit weight ↔ void ratio",
                "γ = G(1+w) γ_w / (1+e)  ⇒  e = G(1+w)·9.81/γ − 1",
                f"G={G}, w={w:.6g}, γ={gamma:.6g} kN/m³ → e={e:.6g}",
                e,
                "",
            )
        )
        steps.append(
            step(
                "Degree of saturation",
                "S = w G / e",
                f"S = {w:.6g}×{G}/{e:.6g} = {S:.6g}",
                S,
                "",
            )
        )

        gamma_check = G * (1 + w) * GAMMA_W / (1 + e)
        ok = abs(gamma_check - gamma) / max(abs(gamma), 1e-9) < 1e-6
        checks = [
            check(
                "γ reconstruction",
                ok,
                f"γ_calc={gamma_check:.6g} vs γ_given={gamma:.6g}",
            ),
            check("0 ≤ S ≤ 1", -1e-6 <= S <= 1.0 + 1e-6, f"S={S:.6g}"),
            check("e > 0", e > 0, f"e={e:.6g}"),
        ]
        answers = [
            answer("e", round(e, 6), ""),
            answer("S", round(S, 6), ""),
            answer("S_percent", round(S * 100.0, 4), "%"),
            answer("gamma", round(gamma, 6), "kN/m3"),
        ]
        return SolverResult(
            status="verified",
            subject=subject,
            steps=steps,
            answers=answers,
            checks=checks,
            drawing_data={
                "kind": "phase_diagram",
                "G": G,
                "w": w,
                "e": e,
                "S": S,
                "gamma": gamma,
            },
            given=given,
        ).to_dict()

    # Path 2: G, w, e → S (and γ)
    if G is not None and w is not None and e_in is not None:
        e = float(e_in)
        if e <= 0:
            return empty_result(
                status="needs_input",
                subject=subject,
                missing=["e (must be > 0)"],
                given=given,
            )
        S = w * G / e
        steps.append(
            step(
                "Degree of saturation",
                "S = w G / e",
                f"S = {w:.6g}×{G}/{e:.6g} = {S:.6g}",
                S,
                "",
            )
        )
        answers = [
            answer("e", round(e, 6), ""),
            answer("S", round(S, 6), ""),
            answer("S_percent", round(S * 100.0, 4), "%"),
        ]
        if gamma is None:
            gamma = G * (1 + w) * GAMMA_W / (1 + e)
            steps.append(
                step(
                    "Bulk unit weight",
                    "γ = G(1+w) γ_w / (1+e)",
                    f"γ = {gamma:.6g} kN/m³",
                    gamma,
                    "kN/m3",
                )
            )
            answers.append(answer("gamma", round(gamma, 6), "kN/m3"))

        checks = [
            check("0 ≤ S ≤ 1", -1e-6 <= S <= 1.0 + 1e-6, f"S={S:.6g}"),
            check("e > 0", e > 0, f"e={e:.6g}"),
        ]
        return SolverResult(
            status="verified",
            subject=subject,
            steps=steps,
            answers=answers,
            checks=checks,
            drawing_data={
                "kind": "phase_diagram",
                "G": G,
                "w": w,
                "e": e,
                "S": S,
                "gamma": gamma,
            },
            given=given,
        ).to_dict()

    # Path 3: G, e, S → w, γ
    if G is not None and e_in is not None and S_in is not None:
        e = float(e_in)
        S = float(S_in)
        w = S * e / G
        steps.append(
            step(
                "Water content from S and e",
                "w = S e / G",
                f"w = {S:.6g}×{e:.6g}/{G} = {w:.6g}",
                w,
                "",
            )
        )
        gamma_calc = G * (1 + w) * GAMMA_W / (1 + e)
        steps.append(
            step(
                "Bulk unit weight",
                "γ = G(1+w) γ_w / (1+e)",
                f"γ = {gamma_calc:.6g} kN/m³",
                gamma_calc,
                "kN/m3",
            )
        )
        return SolverResult(
            status="verified",
            subject=subject,
            steps=steps,
            answers=[
                answer("w", round(w, 6), ""),
                answer("w_percent", round(w * 100.0, 4), "%"),
                answer("e", round(e, 6), ""),
                answer("S", round(S, 6), ""),
                answer("gamma", round(gamma_calc, 6), "kN/m3"),
            ],
            checks=[
                check("0 ≤ S ≤ 1", -1e-6 <= S <= 1.0 + 1e-6, f"S={S:.6g}"),
            ],
            drawing_data={
                "kind": "phase_diagram",
                "G": G,
                "w": w,
                "e": e,
                "S": S,
                "gamma": gamma_calc,
            },
            given=given,
        ).to_dict()

    missing: list[str] = []
    if G is None:
        missing.append("G")
    if w is None and not (e_in is not None and S_in is not None):
        missing.append("w")
    if gamma is None and e_in is None:
        missing.append("gamma_kN_m3 or rho_g_cc or e")
    if not missing:
        missing = ["insufficient combination of G, w, gamma/rho, e, S"]
    return empty_result(
        status="needs_input", subject=subject, missing=missing, given=given
    )
