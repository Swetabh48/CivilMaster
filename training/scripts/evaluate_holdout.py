"""Evaluate holdout set: checks that gold numeric answers appear in model/registry output."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.formulas.registry import solve_with_registry  # noqa: E402


NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", re.I)


def extract_numbers(text: str) -> list[float]:
    vals = []
    for m in NUM_RE.findall(text.replace(",", "")):
        try:
            vals.append(float(m))
        except ValueError:
            continue
    return vals


def close(a: float, b: float, tol: float = 0.05) -> bool:
    if b == 0:
        return abs(a) < tol
    return abs(a - b) / max(abs(b), 1e-9) <= tol


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--holdout",
        type=Path,
        default=Path("training/datasets/civilmaster_sft_holdout.jsonl"),
    )
    args = parser.parse_args()

    # If no holdout yet, evaluate seed cases directly
    cases: list[tuple[str, str]] = []
    if args.holdout.exists():
        for line in args.holdout.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            user = next(m["content"] for m in obj["messages"] if m["role"] == "user")
            assistant = next(m["content"] for m in obj["messages"] if m["role"] == "assistant")
            cases.append((user, assistant))

    if not cases:
        seed = json.loads(
            (Path("training/datasets/seed_qa.json")).read_text(encoding="utf-8")
        )
        for p in seed["pairs"]:
            cases.append((p["input"], p["output"]))

    hits = 0
    for question, gold in cases:
        sol = solve_with_registry(question)
        pred_nums = [a["value"] for a in sol.get("final_answers") or []]
        gold_nums = extract_numbers(gold)
        matched = False
        for g in gold_nums:
            if any(close(p, g) for p in pred_nums):
                matched = True
                break
        hits += int(matched)
        status = "OK" if matched else "MISS"
        print(f"[{status}] pred={pred_nums} gold_nums={gold_nums[:5]}")

    total = len(cases) or 1
    print(f"Numeric match rate: {hits}/{len(cases)} = {hits/total:.1%}")


if __name__ == "__main__":
    main()
