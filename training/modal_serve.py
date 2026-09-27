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
    .apt_install("libgl1", "libglib2.0-0", "libcairo2", "libpango-1.0-0", "libgdk-pixbuf-2.0-0")
    .pip_install_from_requirements(str(ROOT / "backend" / "requirements.txt"))
    .pip_install("cairosvg==2.7.1")
    .env({"PYTHONPATH": "/root"})
    .add_local_dir(str(ROOT / "backend" / "app"), remote_path="/root/app")
)

app = modal.App(APP_NAME, image=image)

volume = modal.Volume.from_name("civilmaster-data", create_if_missing=True)
lora_vol = modal.Volume.from_name("civilmaster-lora-vol", create_if_missing=True)


@app.function(
    volumes={"/data": volume, "/lora": lora_vol},
    timeout=600,
    memory=4096,
)
@modal.asgi_app()
def fastapi_app():
    import os
    from pathlib import Path as P

    os.environ.setdefault("DATABASE_URL", "sqlite:////data/civilmaster.db")
    os.environ.setdefault("UPLOAD_DIR", "/data/uploads")
    os.environ.setdefault("CORPUS_DIR", "/data/corpus")
    os.environ.setdefault("OCR_ENABLED", "false")
    os.environ.setdefault(
        "SECRET_KEY",
        os.environ.get("SECRET_KEY", "civilmaster-modal-change-me-32chars!!"),
    )
    os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
    os.environ.setdefault(
        "CORS_ORIGINS",
        "https://civilmaster-five.vercel.app,https://civilmaster.vercel.app,http://localhost:3000",
    )
    # Prefer adapter trained into the shared LoRA volume
    adapter = P("/lora/civilmaster-lora")
    if adapter.is_dir() and any(adapter.iterdir()):
        os.environ["LORA_ADAPTER_PATH"] = str(adapter)
    else:
        os.environ.setdefault("LORA_ADAPTER_PATH", "")

    from app.main import app as web_app

    return web_app
