"""Run CivilMaster eval cases against the topic-solver pipeline."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.pipeline import solve_problem  # noqa: E402


def _load_cases(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    docs = [d for d in yaml.safe_load_all(raw) if d]
    return docs


def _find_answer(answers: list[dict], contains: str) -> dict | None:
    c = (contains or "").lower().strip()
    if not c:
        return None
    for a in answers:
        lab = str(a.get("label") or "").lower()
        if c == "m" or c == "bm":
            if "moment" in lab or lab.startswith("m_max") or lab.startswith("mmax") or lab == "ma":
                return a
            continue
        if c == "v" or c == "sf":
            if "shear" in lab or lab.startswith("v_max") or lab.startswith("vmax") or lab == "va":
                return a
            continue
        if c == "n":
            if "bolt" in lab or "number" in lab or lab.startswith("n_"):
                return a
            continue
        if c in lab:
            return a
        if c in ("σ", "sigma") and ("stress" in lab or "sigma" in lab or "σ" in lab):
            return a
    return None


def _to_kN(value: float, unit: str) -> float:
    u = (unit or "").lower()
    if u in ("kn",):
        return value
    if u in ("n",):
        return value / 1000.0
    return value


def _to_kNm(value: float, unit: str) -> float:
    u = (unit or "").replace("·", "").replace("-", "").lower()
    if "knm" in u or u == "knm":
        return value
    if "nmm" in u or u in ("nmm", "n·mm"):
        return value / 1e6
    if u == "nm":
        return value / 1000.0
    return value


async def _run_one(case: dict) -> dict:
    q = case["question"]
    sol = await solve_problem(None, q)
    expect = case.get("expect") or {}
    answers = sol.get("final_answers") or []
    ok = True
    notes: list[str] = []

    want_status = expect.get("status")
    if want_status and sol.get("status") != want_status and sol.get("method") == "unsolved":
        ok = False
        notes.append(f"status={sol.get('status')} method={sol.get('method')} (want {want_status})")
    elif want_status == "verified" and not answers:
        ok = False
        notes.append("no answers")

    for exp in expect.get("answers") or []:
        a = _find_answer(answers, exp.get("label_contains") or "")
        if a is None:
            ok = False
            notes.append(f"missing answer matching {exp.get('label_contains')}")
            continue
        val = float(a["value"])
        unit = str(a.get("unit") or "")
        if "value_kNm" in exp:
            got = _to_kNm(val, unit)
            want = float(exp["value_kNm"])
            tol = want * float(exp.get("tol_pct", 2)) / 100.0
            if abs(got - want) > max(tol, 1e-6):
                ok = False
                notes.append(f"{a['label']}: {got} kNm vs {want}")
        if "value_kN" in exp:
            got = _to_kN(val, unit)
            want = float(exp["value_kN"])
            tol = want * float(exp.get("tol_pct", 2)) / 100.0
            if abs(got - want) > max(tol, 1e-6):
                ok = False
                notes.append(f"{a['label']}: {got} kN vs {want}")
        if "value_N_per_mm2" in exp:
            want = float(exp["value_N_per_mm2"])
            tol = want * float(exp.get("tol_pct", 2)) / 100.0
            if abs(val - want) > max(tol, 1e-6):
                ok = False
                notes.append(f"{a['label']}: {val} vs {want} N/mm2")
        if "value" in exp:
            want = float(exp["value"])
            tol = abs(want) * float(exp.get("tol_pct", 5)) / 100.0
            if abs(val - want) > max(tol, 1e-6):
                ok = False
                notes.append(f"{a['label']}: {val} vs {want}")
        if "value_min" in exp and val < float(exp["value_min"]):
            ok = False
            notes.append(f"{a['label']}: {val} < min {exp['value_min']}")
        if "value_mm2_min" in exp and val < float(exp["value_mm2_min"]):
            ok = False
            notes.append(f"{a['label']}: {val} < min {exp['value_mm2_min']}")
        if "value_mm2_max" in exp and val > float(exp["value_mm2_max"]):
            ok = False
            notes.append(f"{a['label']}: {val} > max {exp['value_mm2_max']}")

    if expect.get("require_diagram") and not sol.get("diagram_svg"):
        ok = False
        notes.append("missing diagram")

    return {
        "id": case.get("id"),
        "ok": ok,
        "notes": notes,
        "answers": answers,
        "status": sol.get("status") or sol.get("method"),
        "has_diagram": bool(sol.get("diagram_svg")),
    }


async def main() -> None:
    cases_path = Path(__file__).parent / "cases" / "audit_baseline.yaml"
    cases = _load_cases(cases_path)
    results = [await _run_one(c) for c in cases]
    passed = sum(1 for r in results if r["ok"])
    print(f"Eval: {passed}/{len(results)} passed\n")
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"[{mark}] {r['id']}  status={r['status']}  diagram={r['has_diagram']}")
        for a in r["answers"][:6]:
            print(f"       {a.get('label')}: {a.get('value')} {a.get('unit')}")
        for n in r["notes"]:
            print(f"       ! {n}")
    report = Path(__file__).parent / "baseline_report.md"
    lines = [
        "# Eval baseline report",
        "",
        f"**Score: {passed}/{len(results)}**",
        "",
    ]
    for r in results:
        lines.append(f"- {'✅' if r['ok'] else '❌'} `{r['id']}` — {r['status']}")
        for n in r["notes"]:
            lines.append(f"  - {n}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {report}")
    raise SystemExit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
