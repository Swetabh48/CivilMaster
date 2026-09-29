"""Phase 3 scaffold: build clean SFT rows from topic solvers (no OCR noise).

Usage:
  python training/scripts/build_solver_sft.py

Writes training/datasets/solver_gold_sft.jsonl — question → explanation pairs
grounded in computed steps. Does NOT retrain; use with your GPU/Colab recipe later.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.pipeline import _narrate_from_solver  # noqa: E402
from app.pipeline.parse_nl import try_parse_problem  # noqa: E402
from app.solvers import solve_topic  # noqa: E402

SEEDS = [
    "A simply supported beam of span 6 m carries a UDL of 20 kN/m over the entire span. Find max BM and SF.",
    "A simply supported beam AB of span 5 m carries point loads of 20 kN at 1 m and 30 kN at 3 m from A.",
    "A cantilever of length 3 m carries a UDL of 10 kN/m. Find maximum shear force and bending moment.",
    "Design a lap joint for a tensile force of 145 kN using M16 bolts of grade 4.6. Plates are 12 mm thick and 120 mm wide of E250 steel.",
    "Design a singly reinforced rectangular beam 230 mm x 450 mm effective depth for a factored moment of 120 kNm using M20 and Fe415.",
    "A rectangular beam 200 mm wide and 400 mm deep is subjected to a bending moment of 50 kNm. Find the maximum bending stress.",
    "A soil sample has a bulk density of 1.9 g/cc and water content 12%. G = 2.7. Find void ratio and degree of saturation.",
    "A simply supported beam of span 4 m carries a UDL of 15 kN/m. Find reactions and maximum bending moment.",
    "A cantilever 2.5 m long carries a UDL of 8 kN/m. Find max SF and BM.",
    "Design a lap joint for 200 kN using M20 bolts grade 4.6. Plates 16 mm thick and 150 mm wide, E250.",
]


def main() -> None:
    out = ROOT / "training" / "datasets" / "solver_gold_sft.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for q in SEEDS:
            spec = try_parse_problem(q)
            if not spec:
                continue
            result = solve_topic(spec)
            if result.get("status") != "verified":
                continue
            row = {
                "instruction": "Solve this civil engineering problem with formulas, substitutions, and final answers.",
                "input": q,
                "output": _narrate_from_solver(q, result),
                "source": "topic_solver",
                "topic": spec.get("topic"),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    print(f"Wrote {n} rows → {out}")


if __name__ == "__main__":
    main()
