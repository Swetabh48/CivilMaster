"""Curate high-quality CivilMaster QLoRA JSONL (train + holdout)."""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path


def load_pairs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "pairs" in data:
        return list(data["pairs"])
    if isinstance(data, list):
        return data
    raise ValueError(f"Unrecognized dataset format: {path}")


def quality_rank(p: dict) -> int:
    q = (p.get("quality") or "").lower()
    src = (p.get("source") or "").lower()
    if q == "gold" or src.startswith("registry:") or src.startswith("canonical"):
        return 0
    if "doubt" in src:
        return 1
    if q == "mined" or "mined" in src:
        return 2
    return 3


def looks_good(p: dict) -> bool:
    user = (p.get("input") or p.get("question") or "").strip()
    ans = (p.get("output") or p.get("answer") or "").strip()
    if len(user) < 28 or len(ans) < 40:
        return False
    src = (p.get("source") or "").lower()
    instruction = (p.get("instruction") or "").lower()
    is_theory = (
        "doubt" in src
        or "theory" in src
        or "doubt" in instruction
        or "student" in instruction
    )
    # Numeric drills must contain digits; theory/doubt Q&A may be conceptual.
    if not is_theory and not re.search(r"\d", user):
        return False
    # Drop garbage / truncated OCR junk
    if ans.count("?") > 4:
        return False
    if re.search(r"(lorem ipsum|asdf|xxx+|TODO)", ans, re.I):
        return False
    return True


def to_chat(pair: dict) -> dict:
    user_content = pair.get("input") or pair.get("question") or ""
    assistant = pair.get("output") or pair.get("answer") or ""
    instruction = pair.get("instruction") or "Solve this civil engineering problem correctly."
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are CivilMaster, a B.Tech Civil Engineering tutor. "
                    "Always use correct textbook / IS-code formulas, show clear steps, "
                    "and never invent numbers that are not justified by the given data."
                ),
            },
            {"role": "user", "content": f"{instruction}\n\n{user_content}"},
            {"role": "assistant", "content": assistant},
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Curate CivilMaster QLoRA dataset")
    base = Path(__file__).resolve().parents[1] / "datasets"
    parser.add_argument("--seed", type=Path, default=base / "seed_qa.json")
    parser.add_argument("--synthetic", type=Path, default=base / "synthetic_qa.json")
    parser.add_argument("--nl-synthetic", type=Path, default=base / "nl_synthetic_qa.json")
    parser.add_argument("--mined", type=Path, default=base / "mined_qa.json")
    parser.add_argument("--doubt", type=Path, default=base / "doubt_qa.json")
    parser.add_argument("--approved", type=Path, default=base / "approved_feedback.json")
    parser.add_argument("--approved-jsonl", type=Path, default=base / "approved_feedback.jsonl")
    parser.add_argument("--out", type=Path, default=base / "civilmaster_sft.jsonl")
    parser.add_argument("--holdout-ratio", type=float, default=0.10)
    parser.add_argument("--seed-rng", type=int, default=3407)
    parser.add_argument("--max-train", type=int, default=1200)
    args = parser.parse_args()

    pairs: list[dict] = []
    for path in (
        args.seed,
        args.synthetic,
        args.nl_synthetic,
        args.mined,
        args.doubt,
        args.approved,
    ):
        loaded = load_pairs(path)
        # Tag quality if missing
        for p in loaded:
            if not p.get("quality"):
                src = (p.get("source") or "").lower()
                if "registry" in src or "canonical" in src or "gold" in src:
                    p["quality"] = "gold"
                elif "doubt" in src:
                    p["quality"] = "gold"
                elif "mined" in src:
                    p["quality"] = "mined"
                else:
                    p["quality"] = "synth"
        pairs.extend(loaded)
    if args.approved_jsonl.exists():
        for line in args.approved_jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                row.setdefault("quality", "gold")
                pairs.append(row)

    pairs = [p for p in pairs if looks_good(p)]
    pairs.sort(key=quality_rank)

    seen: set[str] = set()
    unique: list[dict] = []
    for p in pairs:
        key = re.sub(r"\s+", " ", (p.get("input") or "").strip().lower())[:180]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(p)

    # Cap lower-quality rows so gold/doubt dominate
    goldish = [p for p in unique if quality_rank(p) <= 1]
    rest = [p for p in unique if quality_rank(p) > 1]
    rng = random.Random(args.seed_rng)
    rng.shuffle(rest)
    # Keep up to ~40% non-gold after gold fills
    budget_rest = max(0, args.max_train - len(goldish))
    budget_rest = min(budget_rest, max(80, int(0.45 * len(goldish)))) if goldish else budget_rest
    unique = goldish + rest[:budget_rest]
    rng.shuffle(unique)

    n_hold = max(1, int(len(unique) * args.holdout_ratio)) if len(unique) > 8 else 0
    holdout = unique[:n_hold]
    train = unique[n_hold:] if n_hold else unique

    # Prefer gold earlier in the file (mild curriculum)
    train.sort(key=quality_rank)
    if len(train) > args.max_train:
        train = train[: args.max_train]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for p in train:
            f.write(json.dumps(to_chat(p), ensure_ascii=False) + "\n")

    hold_path = args.out.with_name(args.out.stem + "_holdout.jsonl")
    with hold_path.open("w", encoding="utf-8") as f:
        for p in holdout:
            f.write(json.dumps(to_chat(p), ensure_ascii=False) + "\n")

    gold = sum(1 for p in train if quality_rank(p) <= 1)
    print(f"Wrote {len(train)} train rows ({gold} gold/doubt) -> {args.out}")
    print(f"Wrote {len(holdout)} holdout rows -> {hold_path}")


if __name__ == "__main__":
    main()
