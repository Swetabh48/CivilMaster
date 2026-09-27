from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{(ROOT_DIR / 'data' / 'civilmaster.db').as_posix()}"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = str(ROOT_DIR / "data" / "uploads")
    corpus_dir: str = str(ROOT_DIR / "data" / "corpus")
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    lora_adapter_path: str = str(ROOT_DIR / "training" / "adapters" / "civilmaster-lora")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_upload_mb: int = 20
    admin_email: str = "admin@example.com"
    algorithm: str = "HS256"
    # OCR for scanned PDFs (RapidOCR / pytesseract optional)
    ocr_enabled: bool = True
    ocr_max_pages: int = 12
    ocr_min_native_chars: int = 200
    feedback_export_path: str = str(
        ROOT_DIR / "training" / "datasets" / "approved_feedback.jsonl"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # Always allow local next.js during development
        for local in ("http://localhost:3000", "http://127.0.0.1:3000"):
            if local not in origins:
                origins.append(local)
        return origins

    def resolved_upload_dir(self) -> Path:
        p = Path(self.upload_dir)
        return p if p.is_absolute() else ROOT_DIR / p

    def resolved_corpus_dir(self) -> Path:
        p = Path(self.corpus_dir)
        return p if p.is_absolute() else ROOT_DIR / p

    def resolved_lora_adapter_path(self) -> Path | None:
        raw = (self.lora_adapter_path or "").strip()
        if not raw:
            return None
        p = Path(raw)
        p = p if p.is_absolute() else ROOT_DIR / p
        cfg = p / "adapter_config.json"
        return p if cfg.is_file() else None

    def resolved_feedback_export_path(self) -> Path:
        p = Path(self.feedback_export_path)
        return p if p.is_absolute() else ROOT_DIR / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
