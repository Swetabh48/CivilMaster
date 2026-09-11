import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.database import Base, using_sqlite

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmbeddingType(TypeDecorator):
    """Store embeddings as pgvector on Postgres, JSON text on SQLite."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(EMBEDDING_DIM))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        if isinstance(value, str):
            return json.loads(value)
        return list(value)


class CorpusChunk(Base):
    __tablename__ = "corpus_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_path: Mapped[str] = mapped_column(String(1024), index=True)
    source_name: Mapped[str] = mapped_column(String(512))
    semester: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(EmbeddingType(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# silence unused import warnings in some tooling
_ = get_settings
_ = using_sqlite
