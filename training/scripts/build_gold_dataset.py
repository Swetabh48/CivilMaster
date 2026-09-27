"""Generate high-quality CivilMaster SFT pairs from formulas + corpus + doubt drills."""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.formulas.registry import FORMULAS, evaluate_formula  # noqa: E402

OUT_SYN = ROOT / "training" / "datasets" / "synthetic_qa.json"
OUT_DOUBT = ROOT / "training" / "datasets" / "doubt_qa.json"
OUT_NL = ROOT / "training" / "datasets" / "nl_synthetic_qa.json"
SEED = 3407


def _fmt(v: float) -> str:
    if abs(v) >= 1000 or (abs(v) < 0.01 and v != 0):
        return f"{v:.6g}"
    return f"{v:.4g}"


NL_TEMPLATES = {
    "som.axial_stress": [
        "A member carries axial load P = {P} N on area A = {A} mm2. Find axial stress.",
        "Find the axial stress if P = {P} N and A = {A} mm².",
        "Calculate σ for P = {P} N acting on A = {A} mm2.",
    ],
    "som.hooke_elongation": [
        "A rod L = {L} mm, A = {A} mm2, E = {E} N/mm2 carries P = {P} N. Find elongation.",
        "Using δ = PL/AE, find elongation for P={P} N, L={L} mm, A={A} mm2, E={E} N/mm2.",
    ],
    "som.ss_beam_max_moment": [
        "Simply supported beam span L = {L} mm with UDL w = {w} N/mm. Find max bending moment.",
        "For SS beam + full UDL, L={L} mm, w={w} N/mm, compute M_max.",
    ],
    "som.ss_beam_max_shear": [
        "Simply supported beam L = {L} mm carries UDL w = {w} N/mm. Find max shear force.",
    ],
    "som.rect_moment_inertia": [
        "Rectangular section b = {b} mm, d = {d} mm. Find I about the centroidal axis parallel to b.",
    ],
    "som.bending_stress": [
        "Find bending stress for M = {M} N·mm, y = {y} mm, I = {I} mm4.",
    ],
    "rcc.modular_ratio": [
        "Working stress method: σcbc = {σcbc} N/mm2. Find modular ratio m = 280/(3σcbc).",
    ],
}


def formula_pairs(rng: random.Random, per_formula: int = 12) -> list[dict]:
    pairs: list[dict] = []
    for fid, f in FORMULAS.items():
        for _i in range(per_formula):
            inputs: dict[str, float] = {}
            for name in f.required_keys:
                base = rng.choice([0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000])
                jitter = rng.uniform(0.7, 1.4)
                inputs[name] = round(base * jitter, 4)
            try:
                result = evaluate_formula(fid, inputs)
            except Exception:
                continue
            if result.value is None or not (result.value == result.value):
                continue
            if abs(float(result.value)) > 1e12:
                continue
            given = ", ".join(f"{k} = {_fmt(v)}" for k, v in inputs.items())
            question = (
                f"{f.name}. Given {given}. "
                f"Using {f.expression}, find the result in {f.unit}."
            )
            answer = (
                f"Formula: {f.expression}\n"
                f"Substitute: {given}\n"
                f"Result: {_fmt(float(result.value))} {f.unit}\n"
                f"Explanation: apply {f.name.lower()} with consistent units."
            )
            pairs.append(
                {
                    "instruction": "Solve this B.Tech Civil Engineering problem with correct formulas.",
                    "input": question,
                    "output": answer,
                    "source": f"registry:{fid}",
                    "quality": "gold",
                }
            )
            # Natural-language variant when we have a template
            templates = NL_TEMPLATES.get(fid) or []
            if templates:
                try:
                    q_nl = rng.choice(templates).format(**inputs)
                except Exception:
                    q_nl = None
                if q_nl:
                    pairs.append(
                        {
                            "instruction": "Solve this B.Tech Civil Engineering problem with correct formulas.",
                            "input": q_nl,
                            "output": (
                                f"Formula: {f.expression} (`{fid}`).\n"
                                f"Substitution: {given}.\n"
                                f"Result: {_fmt(float(result.value))} {f.unit}."
                            ),
                            "source": f"nl_registry:{fid}",
                            "quality": "gold",
                        }
                    )
    return pairs


def worked_example_pairs(rng: random.Random) -> list[dict]:
    """Canonical textbook-style drills with exact answers."""
    drills = [
        (
            "A steel bar carries an axial load P = 100000 N on a cross-sectional area A = 500 mm2. Find the axial stress.",
            "Axial stress σ = P / A = 100000 / 500 = 200 N/mm2.",
        ),
        (
            "A rod of length L = 2000 mm, area A = 400 mm2, and E = 200000 N/mm2 carries P = 80000 N. Find elongation.",
            "Elongation δL = P L / (A E) = 80000 × 2000 / (400 × 200000) = 2 mm.",
        ),
        (
            "A simply supported beam of span L = 4000 mm carries UDL w = 5 N/mm. Find max shear force and max bending moment.",
            "V_max = w L / 2 = 5 × 4000 / 2 = 10000 N.\nM_max = w L^2 / 8 = 5 × 4000^2 / 8 = 10000000 N·mm.",
        ),
        (
            "For a rectangular section b = 200 mm, d = 300 mm, find moment of inertia about the centroidal axis parallel to breadth.",
            "I = b d^3 / 12 = 200 × 300^3 / 12 = 4.5 × 10^8 mm4.",
        ),
        (
            "A soil has cohesion c = 20 kN/m2, friction angle φ = 0 (undrained clay). Find undrained shear strength.",
            "For φ = 0, su = c = 20 kN/m2.",
        ),
        (
            "Design tensile strength of a plate with fu = 410 MPa and net area An = 1200 mm2 (IS 800 approximate Tu = 0.9 An fu / γm1 with γm1 = 1.25).",
            "Tu = 0.9 × An × fu / 1.25 = 0.9 × 1200 × 410 / 1.25 = 354240 N ≈ 354.2 kN.",
        ),
        (
            "A circular shaft diameter d = 50 mm. Find polar moment of inertia J = π d^4 / 32.",
            "J = π × 50^4 / 32 = π × 6250000 / 32 ≈ 613592 mm4.",
        ),
        (
            "Bending stress: M = 5e6 N·mm, y = 150 mm, I = 4.5e8 mm4. Find σb = M y / I.",
            "σb = M y / I = 5e6 × 150 / 4.5e8 = 1.6667 N/mm2.",
        ),
        (
            "Shear stress τ = V / A with V = 12000 N and A = 800 mm2. Find τ.",
            "τ = V / A = 12000 / 800 = 15 N/mm2.",
        ),
        (
            "Simply supported beam with central point load W = 20 kN and span L = 4 m. Find max bending moment (use N, mm: W=20000 N, L=4000 mm).",
            "M_max = W L / 4 = 20000 × 4000 / 4 = 2.0e7 N·mm.",
        ),
        (
            "RCC WSM: σcbc = 7 N/mm2. Find modular ratio m = 280/(3 σcbc).",
            "m = 280 / (3 × 7) = 280 / 21 ≈ 13.333.",
        ),
        (
            "Void ratio: voids volume Vv = 0.45 m3, solids Vs = 0.55 m3. Find e = Vv/Vs.",
            "e = 0.45 / 0.55 ≈ 0.8182.",
        ),
        (
            "Degree of saturation S = Vw/Vv with Vw = 0.30 m3 and Vv = 0.40 m3.",
            "S = 0.30 / 0.40 = 0.75 (or 75%).",
        ),
        (
            "Young's modulus: stress σ = 200 N/mm2, strain ε = 0.001. Find E = σ/ε.",
            "E = 200 / 0.001 = 200000 N/mm2.",
        ),
        (
            "Section modulus for rectangle b=200 mm, d=300 mm: Z = I/(d/2) with I=bd^3/12.",
            "I = 200×300^3/12 = 4.5e8 mm4; Z = I/(150) = 3.0e6 mm3.",
        ),
    ]
    pairs = []
    for q, a in drills:
        pairs.append(
            {
                "instruction": "Solve this B.Tech Civil Engineering problem with correct formulas.",
                "input": q,
                "output": a,
                "source": "canonical_drill",
                "quality": "gold",
            }
        )
    for q, a in drills:
        pairs.append(
            {
                "instruction": "Show neat steps and the final numeric answer with units.",
                "input": "Please solve: " + q,
                "output": a,
                "source": "canonical_paraphrase",
                "quality": "gold",
            }
        )
        if rng.random() < 0.6:
            pairs.append(
                {
                    "instruction": "Solve step-by-step for a B.Tech Civil exam.",
                    "input": "Work this out carefully:\n" + q,
                    "output": a + "\nKeep units consistent throughout.",
                    "source": "canonical_exam_style",
                    "quality": "gold",
                }
            )
    return pairs


def doubt_pairs() -> list[dict]:
    """Chat-style doubts about solutions (for solution Q&A head)."""
    items = [
        (
            "In the beam UDL example, why is max moment wL^2/8 and not wL^2/4?",
            "For a simply supported beam with full-span UDL, shear is zero at midspan and the moment diagram is parabolic. "
            "Integrating load gives M_max = wL^2/8 at midspan. wL^2/4 would overstate the midspan moment for this case.",
        ),
        (
            "Why do we divide P by A for axial stress? Should self-weight be included?",
            "Average axial stress is force over resisting area: σ = P/A. Self-weight is only added if the problem states "
            "to include it or gives density/length for gravity load; otherwise use the given axial load only.",
        ),
        (
            "Units: if P is in N and A in mm2, what is σ?",
            "σ = P/A then has units N/mm2, which is the same as MPa. Keep units consistent before substituting.",
        ),
        (
            "For elongation δ = PL/AE, what if temperature also changes?",
            "The PL/AE term is mechanical elongation only. Temperature change adds α ΔT L. Only include it when ΔT (and α) are given.",
        ),
        (
            "Can I use the same M_max = wL^2/8 for a cantilever with UDL?",
            "No. Cantilever with full UDL has M_max = wL^2/2 at the fixed end. wL^2/8 is specifically for simply supported + full UDL.",
        ),
        (
            "What is the difference between gross area and net area in tension members?",
            "Gross area is the full cross-section. Net area deducts bolt holes and other openings along the critical rupture path. "
            "Design checks often use net area for rupture and gross area for yielding.",
        ),
        (
            "Why is modular ratio m = 280/(3σcbc) in WSM concrete?",
            "IS 456 working-stress method uses that empirical expression for the modular ratio relating steel and concrete moduli "
            "for transformed-section analysis. Do not mix it into limit-state Mu formulas.",
        ),
        (
            "In soil mechanics, void ratio e = Vv/Vs — can it be greater than 1?",
            "Yes. If voids volume exceeds solids volume, e > 1. That is common in soft/loose soils. Porosity n = e/(1+e) stays below 1.",
        ),
        (
            "For a rectangular section, is I = bd^3/12 about any axis?",
            "No. bd^3/12 is about the centroidal axis parallel to the breadth b (neutral axis for bending about that axis). "
            "About the other centroidal axis it is db^3/12.",
        ),
        (
            "If the solution shows V_max = wL/2, where does that act?",
            "For simply supported beam with full UDL, support reactions are each wL/2, so maximum shear is at the supports "
            "just inside the span. Shear decreases linearly to zero at midspan.",
        ),
        (
            "Why is N/mm2 the same as MPa?",
            "By definition 1 MPa = 1 N/mm2. So axial stress reported in N/mm2 can be labeled MPa without numerical conversion.",
        ),
        (
            "Should I convert span from m to mm before using beam formulas?",
            "Yes if your load is in N/mm or N and you want M in N·mm. Convert everything to one consistent set before substituting; "
            "do not mix m and mm in the same formula.",
        ),
        (
            "What does γm1 = 1.25 mean in the steel tension formula?",
            "γm1 is the partial safety factor for material strength in IS 800 limit-state design (rupture). Dividing by 1.25 "
            "reduces the design strength relative to the characteristic ultimate strength.",
        ),
        (
            "Is average shear stress V/A exact for beams?",
            "V/A is the average shear stress. Elastic beam theory has a parabolic distribution for rectangles (max = 1.5 V/A). "
            "Use the form required by the question; many intro problems accept average τ = V/A.",
        ),
        (
            "Why do we use I = πd^4/64 for bending of a circular section but J = πd^4/32 for torsion?",
            "I is the second moment of area about a diameter (bending). J is the polar moment (torsion) and for a circle J = 2I = πd^4/32.",
        ),
        (
            "Can CivilMaster invent a number that is not in the problem?",
            "No. Only use given data (and standard IS factors the problem explicitly asks for). If a value is missing, say what is missing.",
        ),
        (
            "Difference between WSM and LSM for RCC?",
            "Working stress method uses permissible stresses and modular ratio. Limit state method uses partial factors and ultimate "
            "section capacities (Mu, etc.). Do not mix m-based WSM formulas into LSM Mu checks.",
        ),
        (
            "For point load at midspan on SS beam, is M_max = WL/4 or WL/8?",
            "Central concentrated load: M_max = WL/4 at midspan. WL/8 is for full UDL (with wL playing the role of total load W=wL, M=wL^2/8=WL/8).",
        ),
    ]
    out = []
    for q, a in items:
        out.append(
            {
                "instruction": "Answer the student's doubt using only correct civil engineering theory. Be brief.",
                "input": q,
                "output": a,
                "source": "doubt_drill",
                "quality": "gold",
            }
        )
        out.append(
            {
                "instruction": "Clarify this doubt about the worked solution. Do not invent new numbers.",
                "input": "Doubt: " + q,
                "output": a,
                "source": "doubt_paraphrase",
                "quality": "gold",
            }
        )
    return out


def main() -> None:
    rng = random.Random(SEED)
    pairs = []
    pairs.extend(worked_example_pairs(rng))
    pairs.extend(formula_pairs(rng, per_formula=14))
    # Dedup
    seen: set[str] = set()
    unique: list[dict] = []
    for p in pairs:
        key = re.sub(r"\s+", " ", (p.get("input") or "").lower())[:160]
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    OUT_SYN.write_text(json.dumps({"pairs": unique}, ensure_ascii=False, indent=2), encoding="utf-8")
    doubts = doubt_pairs()
    OUT_DOUBT.write_text(json.dumps({"pairs": doubts}, ensure_ascii=False, indent=2), encoding="utf-8")

    # Keep a separate NL file for curation (subset of gold NL)
    nl_only = [p for p in unique if str(p.get("source", "")).startswith("nl_")]
    OUT_NL.write_text(json.dumps({"pairs": nl_only}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"synthetic gold pairs: {len(unique)} -> {OUT_SYN}")
    print(f"doubt pairs: {len(doubts)} -> {OUT_DOUBT}")
    print(f"nl pairs: {len(nl_only)} -> {OUT_NL}")


if __name__ == "__main__":
    main()
