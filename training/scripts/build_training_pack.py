"""Generate synthetic civil Q&A from the formula registry for SFT volume."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.formulas.registry import FORMULAS, evaluate_formula  # noqa: E402

OUT = ROOT / "training" / "datasets" / "synthetic_qa.json"
MINED = ROOT / "training" / "datasets" / "mined_qa.json"

RNG = random.Random(42)

TEMPLATES = {
    "som.axial_stress": "A member carries axial load P = {P} N on area A = {A} mm2. Find axial stress.",
    "som.hooke_elongation": "A rod has L = {L} mm, A = {A} mm2, E = {E} N/mm2 and load P = {P} N. Find elongation.",
    "som.ss_beam_max_moment": "Simply supported beam span L = {L} mm with UDL w = {w} N/mm. Find max bending moment.",
    "som.ss_beam_max_shear": "Simply supported beam span L = {L} mm with UDL w = {w} N/mm. Find max shear force.",
    "som.rect_moment_inertia": "Rectangular section b = {b} mm, d = {d} mm. Find I about NA.",
    "rcc.mulim_singly": "RCC LSM Fe415: fck = {fck} N/mm2, b = {b} mm, d = {d} mm. Find Mu,lim.",
    "rcc.modular_ratio": "Working stress method: σcbc = {sigma_cbc} N/mm2. Find modular ratio m.",
    "geotech.water_content": "Soil: Ww = {Ww} N, Ws = {Ws} N. Find water content.",
    "geotech.void_ratio": "Soil: Vv = {Vv} m3, Vs = {Vs} m3. Find void ratio.",
    "steel.slenderness": "Steel column: L = {L} mm, r = {r} mm. Find slenderness ratio.",
}

RANGES = {
    "P": (20000, 200000),
    "A": (200, 2000),
    "L": (1000, 6000),
    "E": (200000, 210000),
    "w": (2, 20),
    "b": (150, 300),
    "d": (250, 550),
    "fck": (20, 40),
    "sigma_cbc": (5, 10),
    "Ww": (5, 40),
    "Ws": (40, 120),
    "Vv": (0.2, 0.8),
    "Vs": (0.3, 0.9),
    "r": (30, 80),
}


def sample_inputs(keys: list[str]) -> dict[str, float]:
    vals = {}
    for k in keys:
        lo, hi = RANGES.get(k, (1, 10))
        if isinstance(lo, float) or isinstance(hi, float) or k in {"Vv", "Vs", "w"}:
            vals[k] = round(RNG.uniform(float(lo), float(hi)), 3)
        else:
            vals[k] = float(RNG.randint(int(lo), int(hi)))
    return vals


def main() -> None:
    pairs = []
    if MINED.exists():
        pairs.extend(json.loads(MINED.read_text(encoding="utf-8")).get("pairs", []))

    for fid, tmpl in TEMPLATES.items():
        f = FORMULAS[fid]
        for _ in range(25):
            inputs = sample_inputs(f.required_keys)
            try:
                res = evaluate_formula(fid, inputs)
            except Exception:
                continue
            q = tmpl.format(**inputs)
            a = (
                f"Formula: {res.expression} (`{fid}`).\n"
                f"Substitution: {', '.join(f'{k}={v}' for k,v in res.inputs.items())}.\n"
                f"Result: {round(res.value, 6)} {res.unit}."
            )
            pairs.append(
                {
                    "instruction": "Solve this B.Tech Civil Engineering problem with correct formulas.",
                    "input": q,
                    "output": a,
                    "source": "synthetic_registry",
                }
            )

    OUT.write_text(json.dumps({"pairs": pairs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(pairs)} pairs -> {OUT}")


if __name__ == "__main__":
    main()
