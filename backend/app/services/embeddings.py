from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.models.corpus import EMBEDDING_DIM

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()
_model_failed = False


def _hash_embed(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic fallback embedding when sentence-transformers is unavailable."""
    vec = np.zeros(dim, dtype=np.float32)
    tokens = text.lower().split()
    if not tokens:
        return vec.tolist()
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(0, min(len(digest), 16)):
            idx = (digest[i] * (i + 1) + len(tok)) % dim
            vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tolist()


def get_embedding_model() -> Any | None:
    global _model, _model_failed
    if _model_failed:
        return None
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None or _model_failed:
            return _model
        try:
            from sentence_transformers import SentenceTransformer

            settings = get_settings()
            _model = SentenceTransformer(settings.embedding_model)
            logger.info("Loaded embedding model %s", settings.embedding_model)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Embedding model unavailable, using hash fallback: %s", exc)
            _model_failed = True
            _model = None
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    if model is None:
        return [_hash_embed(t) for t in texts]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
