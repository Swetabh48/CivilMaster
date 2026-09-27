"""Mine Example/Solution Q&A from corpus text + OCR sidecars for SFT."""

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
    r"(?:Example|Ex\.|Q\.|Problem|Question)\s*[\d.:)]+\s*(.{40,1200}?)"
    r"(?:Solution|Sol\.|Ans\.|Answer)\s*[:.]?\s*(.{40,1800}?)"
    r"(?=(?:Example|Ex\.|Q\.|Problem|Question)\s*[\d.:)]|$)",
    re.I | re.S,
)


def pdf_text(path: Path, max_pages: int = 60) -> str:
    side = path.with_name(path.name + ".ocr.txt")
    if side.is_file() and side.stat().st_size > 80:
        return side.read_text(encoding="utf-8", errors="ignore")
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
    return s[:1800]


def quality_ok(q: str, a: str) -> bool:
    if len(q) < 45 or len(a) < 45:
        return False
    if not re.search(r"\d", q) or not re.search(r"\d", a):
        return False
    # Prefer answers that look like worked math / formulas
    if not re.search(r"(=|/|\*|×|sigma|σ|moment|stress|force|kN|N/mm|MPa|mm)", a, re.I):
        return False
    # Drop obvious TOC / syllabus junk
    junk = ("semester", "course outcome", "engagement plan", "copyright", "www.")
    low = (q + " " + a).lower()
    if sum(1 for j in junk if j in low) >= 2:
        return False
    return True


def main() -> None:
    pairs: list[dict] = []
    if SEED.exists():
        pairs.extend(json.loads(SEED.read_text(encoding="utf-8")).get("pairs", []))

    files = list(CORPUS.rglob("*.txt")) + list(CORPUS.rglob("*.pdf"))
    # Prefer smaller worked notes; also keep OCR sidecars' PDFs
    files = sorted(files, key=lambda p: p.stat().st_size)

    seen: set[str] = set()
    for path in files:
        if path.suffix.lower() == ".pdf":
            if path.stat().st_size > 15_000_000 and not path.with_name(path.name + ".ocr.txt").is_file():
                continue
            text = pdf_text(path)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
        if len(text) < 80:
            continue
        for m in EXAMPLE_RE.finditer(text):
            q, a = clean(m.group(1)), clean(m.group(2))
            key = q.lower()[:140]
            if key in seen or not quality_ok(q, a):
                continue
            seen.add(key)
            pairs.append(
                {
                    "instruction": "Solve this B.Tech Civil Engineering problem with correct formulas.",
                    "input": q,
                    "output": a,
                    "source": path.name,
                    "quality": "mined",
                }
            )
            if len(pairs) >= 800:
                break
        if len(pairs) >= 800:
            break

    OUT.write_text(json.dumps({"pairs": pairs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(pairs)} pairs -> {OUT}")


if __name__ == "__main__":
    main()
