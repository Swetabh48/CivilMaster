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


def narrative_from_registry(problem_text: str, solution: dict) -> str:
    lines = ["## Solution (verified formula engine)", ""]
    lines.append("**Given / extracted variables:**")
    for k, v in (solution.get("variables_extracted") or {}).items():
        lines.append(f"- {k} = {v}")
    lines.append("")
    for i, step in enumerate(solution.get("steps") or [], start=1):
        lines.append(f"**Step {i}: {step['name']}**")
        lines.append(f"- Formula: `{step['expression']}` (`{step['formula_id']}`)")
        inputs = ", ".join(f"{k}={v}" for k, v in (step.get("inputs") or {}).items())
        lines.append(f"- Substitution: {inputs}")
        lines.append(f"- Result: **{step['value']} {step['unit']}**")
        if step.get("notes"):
            lines.append(f"- Note: {step['notes']}")
        ver = step.get("verification") or {}
        if ver:
            lines.append(f"- Verification: {'passed' if ver.get('ok') else 'failed'}")
        lines.append("")
    if solution.get("final_answers"):
        lines.append("**Final answers:**")
        for ans in solution["final_answers"]:
            lines.append(f"- {ans['label']}: {ans['value']} {ans['unit']}")
    if not solution.get("steps"):
        lines.append(
            "No registered formula matched with sufficient inputs. "
            "Add clearer values (e.g. `P = 50 kN`, `A = 500 mm2`) or expand the corpus."
        )
        lines.append("")
        lines.append(f"Problem excerpt: {problem_text[:500]}")
    return "\n".join(lines)
