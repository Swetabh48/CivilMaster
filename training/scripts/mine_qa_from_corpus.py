"""Mine Example/Solution style Q&A from corpus text for SFT."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import fitz

CORPUS = ROOT / "data" / "corpus"
OUT = ROOT / "training" / "datasets" / "mined_qa.json"
SEED = ROOT / "training" / "datasets" / "seed_qa.json"

EXAMPLE_RE = re.compile(
    r"(?:Example|Ex\.|Q\.|Problem)\s*[\d.:)]+\s*(.{40,800}?)(?:Solution|Sol\.|Ans\.|Answer)\s*[:.]?\s*(.{40,1200}?)(?=(?:Example|Ex\.|Q\.|Problem)\s*[\d.:)]|$)",
    re.I | re.S,
)


def pdf_text(path: Path, max_pages: int = 40) -> str:
    try:
        doc = fitz.open(path)
        parts = []
        for i in range(min(len(doc), max_pages)):
            parts.append(doc.load_page(i).get_text("text"))
        doc.close()
        return "\n".join(parts)
    except Exception:
        return ""


def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:1500]


def main() -> None:
    pairs: list[dict] = []
    if SEED.exists():
        pairs.extend(json.loads(SEED.read_text(encoding="utf-8")).get("pairs", []))

    files = list(CORPUS.rglob("*.txt")) + list(CORPUS.rglob("*.pdf"))
    # Prefer notes/labs/worked over huge books: sort by size ascending, take many small/medium
    files = sorted(files, key=lambda p: p.stat().st_size)[:250]

    seen: set[str] = set()
    for path in files:
        if path.suffix.lower() == ".pdf":
            if path.stat().st_size > 8_000_000:
                continue
            text = pdf_text(path)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
        for m in EXAMPLE_RE.finditer(text):
            q, a = clean(m.group(1)), clean(m.group(2))
            key = q.lower()[:120]
            if key in seen or len(q) < 40 or len(a) < 40:
                continue
            # Keep civil-ish numeric content
            if not re.search(r"\d", q) or not re.search(r"\d", a):
                continue
            seen.add(key)
            pairs.append(
                {
                    "instruction": "Solve this B.Tech Civil Engineering problem with correct formulas.",
                    "input": q,
                    "output": a,
                    "source": path.name,
                }
            )
            if len(pairs) >= 400:
                break
        if len(pairs) >= 400:
            break

    OUT.write_text(json.dumps({"pairs": pairs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(pairs)} pairs -> {OUT}")


if __name__ == "__main__":
    main()
