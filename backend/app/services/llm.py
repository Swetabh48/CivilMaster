from __future__ import annotations

import logging
import threading
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_lora_lock = threading.Lock()
_lora_bundle: dict[str, Any] | None = None


def _build_prompt(
    problem_text: str,
    registry_solution: dict,
    rag_hits: list[dict],
) -> str:
    context = "\n\n".join(
        f"[{h['source_name']}] {h['content'][:500]}" for h in rag_hits[:3]
    )
    answers = registry_solution.get("final_answers") or []
    steps = registry_solution.get("steps") or []
    return f"""You are CivilMaster, a B.Tech Civil Engineering tutor.
Write a clear step-by-step solution narrative. Use ONLY the formulas and numerical results provided.
Do not invent new numbers. Cite formula expressions given.

Problem:
{problem_text[:3000]}

Retrieved reference excerpts:
{context or "(none)"}

Verified calculation steps (JSON-like):
{steps}

Final answers:
{answers}

Write the solution as numbered steps for a student notebook.
"""


def _load_lora_bundle() -> dict[str, Any] | None:
    """Lazy-load CivilMaster QLoRA adapter when torch+peft+CUDA are available."""
    global _lora_bundle
    if _lora_bundle is not None:
        return _lora_bundle if _lora_bundle.get("ok") else None

    with _lora_lock:
        if _lora_bundle is not None:
            return _lora_bundle if _lora_bundle.get("ok") else None

        settings = get_settings()
        adapter = settings.resolved_lora_adapter_path()
        if adapter is None:
            _lora_bundle = {"ok": False, "reason": "adapter missing"}
            return None

        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except Exception as exc:  # noqa: BLE001
            logger.info("LoRA deps unavailable (%s); using Ollama/registry narrative", exc)
            _lora_bundle = {"ok": False, "reason": str(exc)}
            return None

        if not torch.cuda.is_available():
            logger.info("CUDA not available; skipping local LoRA (use Ollama)")
            _lora_bundle = {"ok": False, "reason": "no cuda"}
            return None

        try:
            import json

            cfg = json.loads((adapter / "adapter_config.json").read_text(encoding="utf-8"))
            base_name = cfg.get("base_model_name_or_path") or "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
            bnb = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            tokenizer = AutoTokenizer.from_pretrained(str(adapter), trust_remote_code=True)
            base = AutoModelForCausalLM.from_pretrained(
                base_name,
                quantization_config=bnb,
                device_map="auto",
                trust_remote_code=True,
            )
            model = PeftModel.from_pretrained(base, str(adapter))
            model.eval()
            _lora_bundle = {"ok": True, "model": model, "tokenizer": tokenizer}
            logger.info("Loaded CivilMaster LoRA from %s", adapter)
            return _lora_bundle
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load LoRA adapter: %s", exc)
            _lora_bundle = {"ok": False, "reason": str(exc)}
            return None


def _generate_with_lora(prompt: str) -> str | None:
    bundle = _load_lora_bundle()
    if not bundle:
        return None
    try:
        import torch

        tokenizer = bundle["tokenizer"]
        model = bundle["model"]
        messages = [{"role": "user", "content": prompt}]
        if hasattr(tokenizer, "apply_chat_template"):
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            text = prompt
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                temperature=None,
                top_p=None,
            )
        gen = out[0][inputs["input_ids"].shape[-1] :]
        return tokenizer.decode(gen, skip_special_tokens=True).strip() or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("LoRA generate failed: %s", exc)
        return None


async def _generate_with_ollama(prompt: str) -> str | None:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
            )
            if resp.status_code != 200:
                logger.warning("Ollama error %s: %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            return data.get("response")
    except Exception as exc:  # noqa: BLE001
        logger.info("Ollama unavailable: %s", exc)
        return None


async def generate_explanation(
    problem_text: str,
    registry_solution: dict,
    rag_hits: list[dict],
) -> str | None:
    """Narrate steps via CivilMaster LoRA (CUDA) then Ollama. None if both unavailable."""
    prompt = _build_prompt(problem_text, registry_solution, rag_hits)
    lora_text = _generate_with_lora(prompt)
    if lora_text:
        return lora_text
    return await _generate_with_ollama(prompt)


async def answer_solution_question(
    question: str,
    *,
    problem_text: str,
    solution: dict,
) -> str:
    """Short doubt-clearing reply grounded in the saved solution (no new numbers)."""
    answers = solution.get("final_answers") or []
    steps = solution.get("steps") or []
    explanation = solution.get("explanation") or narrative_from_registry(problem_text, solution)
    formulas = []
    for step in steps:
        if step.get("expression"):
            formulas.append(f"- {step.get('name')}: `{step.get('expression')}`")
    ground_block = "\n".join(formulas) if formulas else "(see write-up)"
    prompt = f"""You are CivilMaster, a helpful B.Tech Civil tutor.
A student has a doubt about the worked solution below.
Rules:
1) Answer in 3–8 short sentences.
2) Use ONLY formulas and numbers from the verified solution below.
3) Do NOT invent new numeric results. If asked for a new calculation, say the verified answer and explain the formula.
4) If the doubt is conceptual (why this formula), explain briefly using civil theory consistent with the solution.
5) If something is not in the solution, say what is missing — do not guess.

Student question:
{question[:1500]}

Problem:
{problem_text[:2500]}

Verified formulas used:
{ground_block}

Solution write-up:
{explanation[:3500]}

Verified steps:
{steps}

Final answers:
{answers}
"""
    lora_text = _generate_with_lora(prompt)
    if lora_text:
        return lora_text
    ollama = await _generate_with_ollama(prompt)
    if ollama:
        return ollama
    # Deterministic fallback from registry facts
    q_lower = question.lower()
    lines = [
        "Here's what this solution already shows:",
        "",
    ]
    if answers:
        lines.append("Final results:")
        for a in answers:
            lines.append(f"- {a.get('label')}: {a.get('value')} {a.get('unit')}")
        lines.append("")
    if steps:
        lines.append("Key steps:")
        for i, step in enumerate(steps[:6], start=1):
            lines.append(
                f"{i}. {step.get('name')}: {step.get('expression')} → "
                f"{step.get('value')} {step.get('unit')}"
            )
        lines.append("")
    if any(w in q_lower for w in ("why", "how come", "difference", "instead")):
        lines.append(
            "The numbers above come from the formula engine using the data in your question. "
            "If you're unsure why a formula was chosen, check the step name — it matches the "
            "problem keywords (beam, axial, RCC, soil, etc.)."
        )
    else:
        lines.append(
            "If your doubt is about something not listed above, paste the exact line "
            "you're stuck on and ask again."
        )
    return "\n".join(lines)


def narrative_from_registry(problem_text: str, solution: dict) -> str:
    lines = ["## Worked solution", ""]
    lines.append("**Given:**")
    for k, v in (solution.get("variables_extracted") or {}).items():
        lines.append(f"- {k} = {v}")
    lines.append("")
    for i, step in enumerate(solution.get("steps") or [], start=1):
        lines.append(f"**Step {i}: {step['name']}**")
        lines.append(f"- Formula: `{step['expression']}`")
        inputs = ", ".join(f"{k}={v}" for k, v in (step.get("inputs") or {}).items())
        lines.append(f"- Substitution: {inputs}")
        lines.append(f"- Result: **{step['value']} {step['unit']}**")
        if step.get("notes"):
            lines.append(f"- Note: {step['notes']}")
        lines.append("")
    if solution.get("final_answers"):
        lines.append("**Final answers:**")
        for ans in solution["final_answers"]:
            lines.append(f"- {ans['label']}: {ans['value']} {ans['unit']}")
    if not solution.get("steps"):
        lines.append("**Status: not solved**")
        lines.append(
            "No formula matched with clear inputs from this wording. "
            "CivilMaster will not invent an answer or diagram. "
            "Paste values as `L = 6 m`, `w = 20 kN/m`, `P = 145 kN`, or wait for the "
            "natural-language solvers (beams / IS 800 / IS 456) in the next pipeline phase."
        )
        excerpt = (problem_text or "").strip().replace("\n", " ")
        if excerpt:
            lines.append("")
            lines.append(f"Question focus: {excerpt[:280]}")
    return "\n".join(lines)
