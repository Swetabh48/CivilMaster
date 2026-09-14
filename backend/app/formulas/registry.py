"""Strength of Materials + Concrete formula registry with deterministic evaluation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class FormulaResult:
    formula_id: str
    name: str
    expression: str
    inputs: dict[str, float]
    value: float
    unit: str
    notes: str = ""


@dataclass
class FormulaDef:
    id: str
    name: str
    expression: str
    unit: str
    required_keys: list[str]
    compute: Callable[[dict[str, float]], float]
    keywords: list[str] = field(default_factory=list)
    subject: str = "strength_of_materials"
    notes: str = ""


def _f(inputs: dict[str, float], *keys: str) -> list[float]:
    return [float(inputs[k]) for k in keys]


FORMULAS: dict[str, FormulaDef] = {}


def _reg(f: FormulaDef) -> FormulaDef:
    FORMULAS[f.id] = f
    return f


_reg(
    FormulaDef(
        id="som.axial_stress",
        name="Axial stress",
        expression="σ = P / A",
        unit="N/mm²",
        required_keys=["P", "A"],
        compute=lambda i: i["P"] / i["A"],
        keywords=["axial stress", "direct stress", "normal stress", "σ =", "sigma"],
        notes="P in N, A in mm² → stress in N/mm² (MPa).",
    )
)
_reg(
    FormulaDef(
        id="som.axial_strain",
        name="Axial strain",
        expression="ε = δL / L",
        unit="-",
        required_keys=["delta_L", "L"],
        compute=lambda i: i["delta_L"] / i["L"],
        keywords=["axial strain", "longitudinal strain", "δl", "delta l"],
    )
)
_reg(
    FormulaDef(
        id="som.youngs_modulus",
        name="Young's modulus",
        expression="E = σ / ε",
        unit="N/mm²",
        required_keys=["sigma", "epsilon"],
        compute=lambda i: i["sigma"] / i["epsilon"],
        keywords=["young", "modulus of elasticity", "e ="],
    )
)
_reg(
    FormulaDef(
        id="som.hooke_elongation",
        name="Elongation (Hooke's law)",
        expression="δL = P L / (A E)",
        unit="mm",
        required_keys=["P", "L", "A", "E"],
        compute=lambda i: (i["P"] * i["L"]) / (i["A"] * i["E"]),
        keywords=["elongation", "extension", "shortening", "δl =", "delta"],
    )
)
_reg(
    FormulaDef(
        id="som.shear_stress",
        name="Average shear stress",
        expression="τ = P / A",
        unit="N/mm²",
        required_keys=["P", "A"],
        compute=lambda i: i["P"] / i["A"],
        keywords=["shear stress", "τ", "tau", "average shear"],
    )
)
_reg(
    FormulaDef(
        id="som.bending_stress",
        name="Bending stress",
        expression="σ = M y / I",
        unit="N/mm²",
        required_keys=["M", "y", "I"],
        compute=lambda i: (i["M"] * i["y"]) / i["I"],
        keywords=["bending stress", "flexural stress", "m y / i"],
    )
)
_reg(
    FormulaDef(
        id="som.section_modulus",
        name="Section modulus",
        expression="Z = I / y_max",
        unit="mm³",
        required_keys=["I", "y_max"],
        compute=lambda i: i["I"] / i["y_max"],
        keywords=["section modulus", "z ="],
    )
)
_reg(
    FormulaDef(
        id="som.rect_moment_inertia",
        name="Moment of inertia (rectangle)",
        expression="I = b d³ / 12",
        unit="mm⁴",
        required_keys=["b", "d"],
        compute=lambda i: (i["b"] * i["d"] ** 3) / 12.0,
        keywords=["moment of inertia", "i = bd", "rectangular section"],
    )
)
_reg(
    FormulaDef(
        id="som.circle_moment_inertia",
        name="Moment of inertia (circle)",
        expression="I = π d⁴ / 64",
        unit="mm⁴",
        required_keys=["d"],
        compute=lambda i: (math.pi * i["d"] ** 4) / 64.0,
        keywords=["circular section", "πd", "pi d"],
    )
)
_reg(
    FormulaDef(
        id="som.torsion_shear",
        name="Torsional shear stress",
        expression="τ = T r / J",
        unit="N/mm²",
        required_keys=["T", "r", "J"],
        compute=lambda i: (i["T"] * i["r"]) / i["J"],
        keywords=["torsion", "twisting", "polar"],
    )
)
_reg(
    FormulaDef(
        id="som.polar_inertia_circle",
        name="Polar moment of inertia (circle)",
        expression="J = π d⁴ / 32",
        unit="mm⁴",
        required_keys=["d"],
        compute=lambda i: (math.pi * i["d"] ** 4) / 32.0,
        keywords=["polar moment", "j ="],
    )
)
_reg(
    FormulaDef(
        id="som.ss_beam_max_moment",
        name="Simply supported beam — max BM (UDL)",
        expression="M_max = w L² / 8",
        unit="N·mm",
        required_keys=["w", "L"],
        compute=lambda i: (i["w"] * i["L"] ** 2) / 8.0,
        keywords=["simply supported", "udl", "bending moment", "max bm"],
        notes="w = load intensity, L = span. Units must be consistent.",
    )
)
_reg(
    FormulaDef(
        id="som.ss_beam_max_shear",
        name="Simply supported beam — max SF (UDL)",
        expression="V_max = w L / 2",
        unit="N",
        required_keys=["w", "L"],
        compute=lambda i: (i["w"] * i["L"]) / 2.0,
        keywords=["shear force", "max sf", "reaction"],
    )
)
_reg(
    FormulaDef(
        id="som.ss_point_load_moment",
        name="Simply supported beam — max BM (central point load)",
        expression="M_max = W L / 4",
        unit="N·mm",
        required_keys=["W", "L"],
        compute=lambda i: (i["W"] * i["L"]) / 4.0,
        keywords=["point load", "central load", "concentrated"],
    )
)
_reg(
    FormulaDef(
        id="rcc.modular_ratio",
        name="Modular ratio (IS approx)",
        expression="m = 280 / (3 σcbc)",
        unit="-",
        required_keys=["sigma_cbc"],
        compute=lambda i: 280.0 / (3.0 * i["sigma_cbc"]),
        keywords=["modular ratio", "m =", "working stress"],
        subject="concrete",
        notes="IS 456 working stress method approximation.",
    )
)
_reg(
    FormulaDef(
        id="rcc.neutral_axis_factor",
        name="Critical neutral axis depth factor",
        expression="k = m / (m + σst/σcbc)",
        unit="-",
        required_keys=["m", "sigma_st", "sigma_cbc"],
        compute=lambda i: i["m"] / (i["m"] + i["sigma_st"] / i["sigma_cbc"]),
        keywords=["neutral axis", "k =", "critical na"],
        subject="concrete",
    )
)
_reg(
    FormulaDef(
        id="rcc.lever_arm_factor",
        name="Lever arm factor",
        expression="j = 1 - k/3",
        unit="-",
        required_keys=["k"],
        compute=lambda i: 1.0 - i["k"] / 3.0,
        keywords=["lever arm", "j ="],
        subject="concrete",
    )
)
_reg(
    FormulaDef(
        id="rcc.moment_resistance",
        name="Moment of resistance (WSM)",
        expression="M = Q b d²",
        unit="N·mm",
        required_keys=["Q", "b", "d"],
        compute=lambda i: i["Q"] * i["b"] * i["d"] ** 2,
        keywords=["moment of resistance", "qbd", "mr ="],
        subject="concrete",
    )
)
_reg(
    FormulaDef(
        id="rcc.q_factor",
        name="Q factor (WSM)",
        expression="Q = (1/2) σcbc k j",
        unit="N/mm²",
        required_keys=["sigma_cbc", "k", "j"],
        compute=lambda i: 0.5 * i["sigma_cbc"] * i["k"] * i["j"],
        keywords=["q factor", "resistant moment factor"],
        subject="concrete",
    )
)
_reg(
    FormulaDef(
        id="rcc.ast_required",
        name="Required tensile steel (WSM)",
        expression="Ast = M / (σst j d)",
        unit="mm²",
        required_keys=["M", "sigma_st", "j", "d"],
        compute=lambda i: i["M"] / (i["sigma_st"] * i["j"] * i["d"]),
        keywords=["area of steel", "ast", "tensile reinforcement"],
        subject="concrete",
    )
)
_reg(
    FormulaDef(
        id="rcc.xu_max_fe415",
        name="xu,max / d for Fe415 (LSM)",
        expression="xu,max / d = 0.48",
        unit="-",
        required_keys=[],
        compute=lambda i: 0.48,
        keywords=["xu max", "limit state", "fe415", "balanced"],
        subject="concrete",
        notes="IS 456 Table G — Fe415.",
    )
)
_reg(
    FormulaDef(
        id="rcc.mulim_singly",
        name="Limiting moment (singly reinforced, Fe415)",
        expression="Mu,lim = 0.138 fck b d²",
        unit="N·mm",
        required_keys=["fck", "b", "d"],
        compute=lambda i: 0.138 * i["fck"] * i["b"] * i["d"] ** 2,
        keywords=["mulim", "limiting moment", "ultimate moment", "0.138"],
        subject="concrete",
    )
)
_reg(
    FormulaDef(
        id="geotech.bulk_unit_weight",
        name="Bulk unit weight",
        expression="γ = W / V",
        unit="kN/m³",
        required_keys=["W", "V"],
        compute=lambda i: i["W"] / i["V"],
        keywords=["bulk unit weight", "unit weight", "γ =", "gamma"],
        subject="geotechnical",
    )
)
_reg(
    FormulaDef(
        id="geotech.void_ratio",
        name="Void ratio",
        expression="e = Vv / Vs",
        unit="-",
        required_keys=["Vv", "Vs"],
        compute=lambda i: i["Vv"] / i["Vs"],
        keywords=["void ratio", "e =", "voids"],
        subject="geotechnical",
    )
)
_reg(
    FormulaDef(
        id="geotech.degree_saturation",
        name="Degree of saturation",
        expression="S = Vw / Vv",
        unit="-",
        required_keys=["Vw", "Vv"],
        compute=lambda i: i["Vw"] / i["Vv"],
        keywords=["degree of saturation", "saturation"],
        subject="geotechnical",
    )
)
_reg(
    FormulaDef(
        id="geotech.water_content",
        name="Water content",
        expression="w = Ww / Ws",
        unit="-",
        required_keys=["Ww", "Ws"],
        compute=lambda i: i["Ww"] / i["Ws"],
        keywords=["water content", "moisture content"],
        subject="geotechnical",
    )
)
_reg(
    FormulaDef(
        id="steel.slenderness",
        name="Slenderness ratio",
        expression="λ = L / r",
        unit="-",
        required_keys=["L", "r"],
        compute=lambda i: i["L"] / i["r"],
        keywords=["slenderness", "radius of gyration"],
        subject="steel",
    )
)


NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<label>"
    r"sigma_cbc|sigma_st|delta_L|y_max|fck|Ast|σcbc|σst|δL|"
    r"Vv|Vs|Vw|Ww|Ws|V|"
    r"P|A|L|E|M|W|w|b|d|I|J|T|r|y|Q|k|j|m|σ|ε"
    r")\s*[=:]\s*(?P<value>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
    r"\s*(?P<unit>kN\/mm2|N\/mm2|mm2|mm\u00b2|mm4|mm\u2074|kN|N|mm|MPa)?"
    ,
    re.UNICODE | re.IGNORECASE,
)

LABEL_MAP = {
    "p": "P",
    "a": "A",
    "l": "L",
    "e": "E",
    "w": "w",
    "m": "M",
    "b": "b",
    "d": "d",
    "i": "I",
    "j": "J",
    "t": "T",
    "r": "r",
    "y": "y",
    "q": "Q",
    "k": "k",
    "v": "V",
    "vv": "Vv",
    "vs": "Vs",
    "vw": "Vw",
    "ww": "Ww",
    "ws": "Ws",
    "fck": "fck",
    "ast": "Ast",
    "sigma": "sigma",
    "σ": "sigma",
    "ε": "epsilon",
    "epsilon": "epsilon",
    "sigmacbc": "sigma_cbc",
    "sigma_cbc": "sigma_cbc",
    "σcbc": "sigma_cbc",
    "sigmast": "sigma_st",
    "sigma_st": "sigma_st",
    "σst": "sigma_st",
    "deltal": "delta_L",
    "delta_l": "delta_L",
    "δl": "delta_L",
    "ymax": "y_max",
    "y_max": "y_max",
}


def extract_variables(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for match in NUMBER_PATTERN.finditer(text):
        label_raw = match.group("label")
        # Case-sensitive civil convention: M=moment, m=modular ratio
        if label_raw == "M":
            key = "M"
        elif label_raw == "m":
            key = "m"
        elif label_raw == "W":
            key = "W"
        elif label_raw == "w":
            key = "w"
        else:
            raw = label_raw.lower().replace("_", "")
            key = LABEL_MAP.get(label_raw.lower()) or LABEL_MAP.get(raw)
        if not key:
            continue
        try:
            value = float(match.group("value"))
        except ValueError:
            continue
        unit = (match.group("unit") or "").lower()
        if unit == "kn":
            value *= 1000.0
        found[key] = value
        if key == "P":
            found.setdefault("W", value)
        if key == "W":
            found.setdefault("P", value)

    kn = re.findall(r"(\d+(?:\.\d+)?)\s*kN\b", text, flags=re.I)
    if kn and "P" not in found and "W" not in found:
        found["P"] = float(kn[0]) * 1000.0
        found["W"] = found["P"]
    mm2 = re.findall(r"(\d+(?:\.\d+)?)\s*mm\s*[²2]\b", text, flags=re.I)
    if mm2 and "A" not in found:
        found["A"] = float(mm2[0])
    return found


def rank_formulas(text: str, limit: int = 8) -> list[FormulaDef]:
    lower = text.lower()
    scored: list[tuple[float, FormulaDef]] = []
    for f in FORMULAS.values():
        score = 0.0
        for kw in f.keywords:
            if kw.lower() in lower:
                score += 2.0
        if f.subject == "concrete" and any(
            w in lower for w in ("rcc", "concrete", "ast", "fck", "fe415", "is 456", "mulim")
        ):
            score += 1.5
        if f.subject == "geotechnical" and any(
            w in lower for w in ("soil", "void", "saturation", "geotech", "unit weight", "moisture")
        ):
            score += 1.5
        if f.subject == "steel" and any(w in lower for w in ("steel", "slenderness", "is 800")):
            score += 1.5
        if f.subject == "strength_of_materials" and any(
            w in lower for w in ("beam", "stress", "strain", "torsion", "bending", "shear")
        ):
            score += 1.0
        # Prefer formulas we can compute from extracted inputs later (light prior)
        if not f.required_keys:
            score -= 0.5
        if "axial" in lower and f.id == "som.shear_stress":
            score -= 5.0
        if score > 0:
            scored.append((score, f))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored[:limit]]


def evaluate_formula(formula_id: str, inputs: dict[str, float]) -> FormulaResult:
    f = FORMULAS.get(formula_id)
    if not f:
        raise KeyError(f"Unknown formula: {formula_id}")
    missing = [k for k in f.required_keys if k not in inputs]
    if missing:
        raise ValueError(f"Missing inputs for {formula_id}: {missing}")
    value = float(f.compute(inputs))
    used = {k: inputs[k] for k in f.required_keys}
    return FormulaResult(
        formula_id=f.id,
        name=f.name,
        expression=f.expression,
        inputs=used,
        value=value,
        unit=f.unit,
        notes=f.notes,
    )


def verify_result(result: FormulaResult) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    ok = True
    if not math.isfinite(result.value):
        ok = False
        checks.append({"check": "finite", "passed": False, "detail": "Non-finite result"})
    else:
        checks.append({"check": "finite", "passed": True})

    # Sanity ranges by formula family
    if "stress" in result.name.lower() or result.formula_id.endswith("stress"):
        passed = abs(result.value) < 1e6
        checks.append(
            {
                "check": "stress_range",
                "passed": passed,
                "detail": "Stress magnitude within plausible engineering range",
            }
        )
        ok = ok and passed
    if result.unit == "-" and abs(result.value) > 100:
        checks.append({"check": "dimensionless_range", "passed": False})
        ok = False
    else:
        checks.append({"check": "dimensionless_range", "passed": True})

    for v in result.inputs.values():
        if v == 0 and " / " in result.expression:
            checks.append({"check": "nonzero_divisor_inputs", "passed": True})
            break

    return {"ok": ok, "checks": checks, "value": result.value, "unit": result.unit}


def solve_with_registry(text: str) -> dict[str, Any]:
    variables = extract_variables(text)
    candidates = rank_formulas(text)
    steps: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    diagram_type = "none"

    lower = text.lower()
    if "beam" in lower or "bending" in lower or "udl" in lower or "shear force" in lower:
        diagram_type = "beam_sfd_bmd"
    elif "section" in lower or "rectangle" in lower or "circular" in lower:
        diagram_type = "section"
    elif any(w in lower for w in ("rcc", "concrete", "reinforcement", "ast")):
        diagram_type = "rcc_section"

    # Prefer formulas we can fully evaluate; skip bare constants unless nothing else works
    evaluated = 0
    deferred_constants: list[FormulaDef] = []
    for f in candidates:
        if not f.required_keys:
            deferred_constants.append(f)
            continue
        if all(k in variables for k in f.required_keys):
            try:
                local = dict(variables)
                res = evaluate_formula(f.id, local)
                ver = verify_result(res)
                step = {
                    "formula_id": res.formula_id,
                    "name": res.name,
                    "expression": res.expression,
                    "inputs": res.inputs,
                    "value": round(res.value, 6),
                    "unit": res.unit,
                    "notes": res.notes,
                    "verification": ver,
                }
                steps.append(step)
                results.append(
                    {
                        "label": res.name,
                        "value": round(res.value, 6),
                        "unit": res.unit,
                        "formula_id": res.formula_id,
                    }
                )
                if f.id == "rcc.modular_ratio":
                    variables["m"] = res.value
                if f.id == "rcc.neutral_axis_factor":
                    variables["k"] = res.value
                if f.id == "rcc.lever_arm_factor":
                    variables["j"] = res.value
                if f.id == "rcc.q_factor":
                    variables["Q"] = res.value
                if f.id == "som.rect_moment_inertia":
                    variables["I"] = res.value
                if f.id == "som.circle_moment_inertia":
                    variables["I"] = res.value
                if f.id == "som.polar_inertia_circle":
                    variables["J"] = res.value
                evaluated += 1
            except (ValueError, ZeroDivisionError, KeyError):
                continue

    if evaluated == 0:
        for f in deferred_constants:
            try:
                res = evaluate_formula(f.id, {})
                ver = verify_result(res)
                steps.append(
                    {
                        "formula_id": res.formula_id,
                        "name": res.name,
                        "expression": res.expression,
                        "inputs": res.inputs,
                        "value": round(res.value, 6),
                        "unit": res.unit,
                        "notes": res.notes,
                        "verification": ver,
                    }
                )
                results.append(
                    {
                        "label": res.name,
                        "value": round(res.value, 6),
                        "unit": res.unit,
                        "formula_id": res.formula_id,
                    }
                )
                evaluated += 1
            except (ValueError, ZeroDivisionError, KeyError):
                continue

    # If nothing matched but we have P and A, default axial stress
    if evaluated == 0 and "P" in variables and "A" in variables:
        res = evaluate_formula("som.axial_stress", variables)
        ver = verify_result(res)
        steps.append(
            {
                "formula_id": res.formula_id,
                "name": res.name,
                "expression": res.expression,
                "inputs": res.inputs,
                "value": round(res.value, 6),
                "unit": res.unit,
                "notes": res.notes,
                "verification": ver,
            }
        )
        results.append(
            {
                "label": res.name,
                "value": round(res.value, 6),
                "unit": res.unit,
                "formula_id": res.formula_id,
            }
        )
        evaluated = 1

    subject = "strength_of_materials"
    if any(s.get("formula_id", "").startswith("rcc.") for s in steps):
        subject = "concrete"
    elif any(s.get("formula_id", "").startswith("geotech.") for s in steps):
        subject = "geotechnical"
    elif any(s.get("formula_id", "").startswith("steel.") for s in steps):
        subject = "steel"

    return {
        "subject": subject,
        "variables_extracted": variables,
        "candidate_formulas": [
            {"id": f.id, "name": f.name, "expression": f.expression} for f in candidates
        ],
        "steps": steps,
        "final_answers": results,
        "diagram_type": diagram_type,
        "confidence": min(0.95, 0.4 + 0.15 * evaluated) if evaluated else 0.2,
        "method": "formula_registry",
    }


def list_formulas() -> list[dict[str, Any]]:
    return [
        {
            "id": f.id,
            "name": f.name,
            "expression": f.expression,
            "unit": f.unit,
            "subject": f.subject,
            "required_keys": f.required_keys,
            "notes": f.notes,
        }
        for f in FORMULAS.values()
    ]
