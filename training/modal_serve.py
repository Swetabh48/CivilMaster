"""Serve CivilMaster FastAPI on Modal (public HTTPS).

Run:
  modal deploy training/modal_serve.py
"""

from __future__ import annotations

from pathlib import Path

import modal

APP_NAME = "civilmaster-api"
ROOT = Path(__file__).resolve().parents[1]

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install_from_requirements(str(ROOT / "backend" / "requirements.txt"))
    .env({"PYTHONPATH": "/root"})
    .add_local_dir(str(ROOT / "backend" / "app"), remote_path="/root/app")
)

app = modal.App(APP_NAME, image=image)

volume = modal.Volume.from_name("civilmaster-data", create_if_missing=True)


@app.function(
    volumes={"/data": volume},
    timeout=600,
    memory=2048,
)
@modal.asgi_app()
def fastapi_app():
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite:////data/civilmaster.db")
    os.environ.setdefault("UPLOAD_DIR", "/data/uploads")
    os.environ.setdefault("CORPUS_DIR", "/data/corpus")
    os.environ.setdefault("OCR_ENABLED", "false")
    os.environ.setdefault(
        "SECRET_KEY",
        os.environ.get("SECRET_KEY", "civilmaster-modal-change-me-32chars!!"),
    )
    os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
    os.environ.setdefault("CORS_ORIGINS", "https://civilmaster.vercel.app,http://localhost:3000")

    from app.main import app as web_app

    return web_app
