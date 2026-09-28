"""Clean and split uploaded assignment sheets into solvable problems."""

from __future__ import annotations

import re
from typing import Any


_BOILERPLATE_PATTERNS = [
    r"(?is)laboratory engagement plan.*?(?=assignment\s*no\.?\s*\d|$)",
    r"(?is)students are advised to submit.*?(?=assignment\s*no\.?\s*\d|reference:|$)",
    r"(?is)reference:\s*(?:is\s*\d|sp\s*\d).{0,2000}?(?=assignment\s*no\.?\s*\d|$)",
    r"(?is)dr\.\s*[\w\s\.]+,?\s*associate\s*professor[^\n]*",
    r"(?is)ce-?\s*\d{4,6}\s*:\s*steel structures[^\n]*",
    r"(?is)department of civil engineering\s*",
    r"(?is)b\.?\s*tech\.?\s*civil engineering,?\s*vi semester[^\n]*",
    r"(?is)session:\s*\d{4}-\d{2}",
    r"(?is)make-up turn.*?(?=assignment\s*no\.?\s*\d|$)",
    r"(?is)compilation of submission.*?(?=assignment\s*no\.?\s*\d|$)",
    r"(?m)^---\s*PAGE\s*\d+\s*---\s*$",
    r"(?is)civilmaster\s*",
    r"(?is)b\.?tech civil\s*[|·\-].*?worked solution\s*",
    r"(?is)could not match a stored formula.*$",
]

_DETAILING_HINTS = (
    "draw the",
    "detailing",
    "detail a",
    "detail the",
    "sectional details",
    "front view",
    "top view",
    "elevation",
    "symbolic representation",
    "scheme of symbols",
    "using autocad",
    "dimension them",
)

_NUMERICAL_HINTS = (
    "find",
    "calculate",
    "compute",
    "design",
    "determine",
    "force of",
    "kn",
    "mpa",
    "n/mm",
    "udl",
    "axial",
    "bending moment",
    "shear",
)


def strip_boilerplate(text: str) -> str:
    t = text or ""
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # Drop obvious table debris from lab plans
    t = re.sub(
        r"(?is)lab turn/?\s*class\s*turn no\s*drawing\s*assignment\s*no\s*contents",
        "",
        t,
    )
    for pat in _BOILERPLATE_PATTERNS:
        t = re.sub(pat, "\n", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _kind_for(q: str) -> str:
    lower = q.lower()
    detail_score = sum(1 for h in _DETAILING_HINTS if h in lower)
    num_score = sum(1 for h in _NUMERICAL_HINTS if h in lower)
    has_numbers = bool(re.search(r"\d", q))
    # Design problems with loads / forces are numerical even if they also say "detail"
    if re.search(r"(?i)(design|calculate|analyse|analyze|find).{0,40}(force|load|kn|mpa|span)", lower):
        return "numerical"
    if "design and detail" in lower and has_numbers and num_score >= 1:
        return "numerical"
    if detail_score >= 2 and "design and detail" not in lower:
        return "detailing"
    if re.match(r"(?is)^\s*\d{0,2}[\.\)]?\s*draw\b", lower) and "design" not in lower:
        return "detailing"
    if "draw" in lower and "design" not in lower and num_score == 0:
        return "detailing"
    if num_score >= 1 and has_numbers:
        return "numerical"
    if detail_score >= 1:
        return "detailing"
    return "numerical" if has_numbers else "detailing"


def _short_question(text: str, kind: str, limit: int = 900) -> str:
    """Keep PDF question boxes readable — drop long section catalogues."""
    t = (text or "").strip()
    t = re.sub(r"(?is)ce-?\s*\d{4,6}\s*:\s*steel structures[^\n]*\n?", "", t)
    t = re.sub(r"(?is)dr\.\s*[\w\s\.]+,?\s*associate\s*professor[^\n]*\n?", "", t)
    t = re.sub(r"(?m)^---\s*PAGE\s*\d+\s*---\s*$", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if len(t) <= limit:
        return t
    # Prefer keeping the numbered stem (1. Draw / Design …)
    m = re.search(r"(?m)^\s*\d{1,2}[\.\)\-]\s*.+", t)
    if m:
        start = m.start()
        stem = t[start : start + limit]
        if len(stem) >= min(200, limit // 2):
            if start + limit < len(t):
                stem = stem.rstrip() + "\n… (see assignment sheet for full list)"
            return stem
    if kind == "detailing":
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        kept: list[str] = []
        for ln in lines:
            kept.append(ln)
            if sum(len(x) for x in kept) > limit - 40:
                break
        out = "\n".join(kept)
        if len(out) > limit:
            out = out[: limit - 30].rstrip() + "\n… (see assignment sheet)"
        return out
    return t[: limit - 20].rstrip() + "\n…"


def split_problems(text: str) -> list[dict[str, Any]]:
    """Split cleaned text into Assignment / numbered questions."""
    cleaned = strip_boilerplate(text)
    if not cleaned:
        return []

    # Numbered Q: "1. Draw" / "1.Analyse" — not decimals like "3.6m" or "4.6 are"
    q_split = r"(?m)(?=^\s*\d{1,2}(?:\.|\))\s*[A-Za-z(\"'])"

    # Split by ASSIGNMENT NO. N
    chunks = re.split(r"(?is)(?=assignment\s*no\.?\s*\d+)", cleaned)
    chunks = [c.strip() for c in chunks if c.strip()]
    if len(chunks) <= 1:
        # Single blob — try numbered list 1. 2. 3.
        parts = re.split(q_split, cleaned)
        parts = [p.strip() for p in parts if p.strip() and len(p.strip()) > 40]
        if len(parts) >= 2:
            out = []
            for i, p in enumerate(parts, start=1):
                kind = _kind_for(p)
                out.append(
                    {
                        "id": f"Q{i}",
                        "title": f"Question {i}",
                        "text": _short_question(p, kind),
                        "kind": kind,
                    }
                )
            return out
        return [
            {
                "id": "Q1",
                "title": "Question",
                "text": _short_question(cleaned, _kind_for(cleaned)),
                "kind": _kind_for(cleaned),
            }
        ]

    problems: list[dict[str, Any]] = []
    for chunk in chunks:
        m = re.search(r"(?is)assignment\s*no\.?\s*(\d+)\s*(.*?)(?=\n|$)", chunk)
        if not m:
            # Skip preamble / leftover syllabus without a numbered assignment
            continue
        asg = m.group(1)
        title = (m.group(2).strip() if m.group(2) else f"Assignment {asg}")[:120]
        body = chunk
        # Sub-split numbered questions inside assignment
        subs = re.split(q_split, body)
        subs = [s.strip() for s in subs if s.strip()]
        # First piece may be header only
        numbered = []
        header = ""
        for s in subs:
            if re.match(r"^\s*\d{1,2}(?:\.|\))\s*[A-Za-z(\"']", s):
                numbered.append(s)
            elif not numbered:
                header = s
        if not numbered:
            kind = _kind_for(body)
            problems.append(
                {
                    "id": f"A{asg}",
                    "title": f"Assignment {asg}: {title}",
                    "text": _short_question(body, kind),
                    "kind": kind,
                }
            )
            continue
        # Un-numbered lead question sitting in the header (common on A8 etc.)
        lead = header
        lead = re.sub(r"(?is)assignment\s*no\.?\s*\d+[^\n]*", "", lead)
        lead = re.sub(r"(?is)note:\s*[^\n]+", "", lead)
        lead = lead.strip()
        if len(lead) > 80 and re.search(r"(?i)\b(draw|design|detail|analyse|analyze)\b", lead):
            numbered = [lead] + numbered
        for j, s in enumerate(numbered, start=1):
            text_q = s
            if j == 1 and header and s is not lead:
                note = re.search(r"(?is)note:\s*[^\n]{10,180}", header)
                if note:
                    text_q = note.group(0).strip() + "\n\n" + s
            kind = _kind_for(text_q)
            problems.append(
                {
                    "id": f"A{asg}-Q{j}",
                    "title": f"Assignment {asg} · Q{j}",
                    "text": _short_question(text_q, kind, 700 if kind == "detailing" else 1800),
                    "kind": kind,
                }
            )
    return problems[:24]


def is_assignment_pack(text: str) -> bool:
    t = (text or "").lower()
    if len(t) > 2500 and ("assignment no" in t or t.count("\n") > 40):
        return True
    if len(split_problems(text)) >= 2:
        return True
    return False


def detailing_guidance(question: str) -> str:
    q = question.lower()
    lines = [
        "This is a **drawing / detailing** task (CAD), not a single formula calculation.",
        "",
        "What to submit:",
        "1. Use AutoCAD (or similar) — plan / elevation / section as asked.",
        "2. Show all dimensions, member designations, and IS-code symbols.",
        "3. Label bolt grades, weld types, and plate thicknesses where given.",
        "",
    ]
    if "weld" in q:
        lines.append("Follow IS 813 weld symbols and IS 800 for weld design checks.")
    if "bolt" in q or "bolted" in q:
        lines.append("Show bolt pitch, edge distance, and gauge per IS 800.")
    if "truss" in q:
        lines.append("Draw centre-line diagram + typical joint detail with member sizes.")
    if "gantry" in q or "crane" in q:
        lines.append("Show gantry layout, wheel spacing, and girder cross-section.")
    if "plate girder" in q:
        lines.append("Detail web, flanges, stiffeners, and splices with dimensions.")
    lines.append("")
    lines.append(
        "CivilMaster can still check **numerical design** parts if you paste one clear "
        "problem with numbers (e.g. design a lap joint for 145 kN with M16 bolts)."
    )
    return "\n".join(lines)
