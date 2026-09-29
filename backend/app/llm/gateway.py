"""LLM gateway — hosted OpenAI-compatible API, then Ollama, then None.

Used for future parse/narrate enrichment. Solvers never call the LLM for arithmetic.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def complete_json(
    system: str,
    user: str,
    *,
    schema_hint: str | None = None,
) -> dict[str, Any] | None:
    """Ask the configured LLM for JSON. Returns None if no backend works."""
    text = await complete_text(system, user + (f"\n\nRespond with JSON only. {schema_hint or ''}"))
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        logger.warning("LLM JSON parse failed")
    return None


async def complete_text(system: str, user: str) -> str | None:
    settings = get_settings()
    # Hosted OpenAI-compatible
    api_key = getattr(settings, "llm_api_key", None) or ""
    base = getattr(settings, "llm_base_url", None) or ""
    model = getattr(settings, "llm_model", None) or ""
    if api_key and base and model:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    f"{base.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.1,
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.info("Hosted LLM failed: %s", exc)

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": f"{system}\n\n{user}",
                    "stream": False,
                },
            )
            if r.status_code == 200:
                return r.json().get("response")
    except Exception as exc:
        logger.info("Ollama unavailable: %s", exc)
    return None
