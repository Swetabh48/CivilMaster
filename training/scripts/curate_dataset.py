"""Curate training JSONL from seed dataset + approved admin export file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_pairs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "pairs" in data:
        return list(data["pairs"])
    if isinstance(data, list):
        return data
    raise ValueError(f"Unrecognized dataset format: {path}")


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
                    "Always use correct IS-code / textbook formulas and show steps."
                ),
            },
            {"role": "user", "content": f"{instruction}\n\n{user_content}"},
            {"role": "assistant", "content": assistant},
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Curate CivilMaster QLoRA dataset")
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "seed_qa.json",
    )
    parser.add_argument(
        "--approved",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "approved_feedback.json",
        help="JSON export from /api/admin/training-export (or auto-written on approve)",
    )
    parser.add_argument(
        "--approved-jsonl",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "approved_feedback.jsonl",
    )
    parser.add_argument(
        "--synthetic",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "synthetic_qa.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "civilmaster_sft.jsonl",
    )
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    args = parser.parse_args()

    pairs: list[dict] = []
    if args.seed.exists():
        pairs.extend(load_pairs(args.seed))
    if args.synthetic.exists():
        pairs.extend(load_pairs(args.synthetic))
    if args.approved and args.approved.exists():
        pairs.extend(load_pairs(args.approved))
    if args.approved_jsonl and args.approved_jsonl.exists():
        for line in args.approved_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                pairs.append(json.loads(line))

    # Deduplicate by input text
    seen: set[str] = set()
    unique: list[dict] = []
    for p in pairs:
        key = (p.get("input") or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    n_hold = max(1, int(len(unique) * args.holdout_ratio)) if len(unique) > 5 else 0
    holdout = unique[:n_hold]
    train = unique[n_hold:] if n_hold else unique

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for p in train:
            f.write(json.dumps(to_chat(p), ensure_ascii=False) + "\n")

    hold_path = args.out.with_name(args.out.stem + "_holdout.jsonl")
    with hold_path.open("w", encoding="utf-8") as f:
        for p in holdout:
            f.write(json.dumps(to_chat(p), ensure_ascii=False) + "\n")

    print(f"Wrote {len(train)} train rows -> {args.out}")
    print(f"Wrote {len(holdout)} holdout rows -> {hold_path}")


if __name__ == "__main__":
    main()
