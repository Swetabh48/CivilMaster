# CivilMaster

B.Tech Civil assignment solver with a verified formula engine — not a free-form guesser.

Problems are matched to textbook / IS-code formulas, numbers are computed in a registry, then steps and diagrams are shown. Optional retrieval over your own semester PDFs, and optional local narration for explanations. If narration is offline, the numerical solution still works.

## Live demo

- App: https://civilmaster-five.vercel.app
- API: https://swetabh48--civilmaster-api-fastapi-app.modal.run/health

Register with `admin@example.com` (see `.env.example`) for admin on a fresh DB.

**Features**

- Solve typed or uploaded problems (SoM, RCC, steel, geotech basics)
- Step-by-step work with formula, substitution, and units
- SVG diagrams + PDF / Word / DXF exports
- Indexed corpus search over textbooks / labs / PYQs
- Feedback collection for corrections and later fine-tuning

## Stack

| Part | Tech |
|------|------|
| API | FastAPI |
| UI | Next.js |
| DB | SQLite locally; Postgres + pgvector via Docker |
| Optional narration | Ollama or local LoRA adapter |

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
cd ..
copy .env.example .env        # or cp on Unix
uvicorn app.main:app --reload --app-dir backend --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

Admin email is `ADMIN_EMAIL` in `.env` (default `admin@example.com`). Passwords need 12+ chars with upper, lower, digit, and a symbol.

### Optional

```bash
ollama pull qwen2.5:7b
ollama serve

docker compose up -d db
```

Put PDFs under `data/corpus/`, then Admin → ingest. For scanned books:

```bash
python scripts/ocr_reingest.py
```

## Training (optional)

See `training/CLOUD_TRAIN.md`. Adapter path:

```
training/adapters/civilmaster-lora/
```

The formula engine remains the source of truth for numbers.

## Feedback loop

1. Mark a solution correct / wrong on the solve page
2. Admin approves useful corrections
3. Curate into `training/datasets/civilmaster_sft.jsonl`
4. Retrain when you have enough clean pairs

## Layout

```
backend/     FastAPI, formulas, retrieval, OCR, exports
frontend/    Next.js UI
training/    datasets + fine-tune / Colab helpers
scripts/     ingest + OCR utilities
data/        local DB, uploads, corpus (not tracked)
```

## Notes

- Keep `.env` out of git — copy from `.env.example`
- Large PDFs and model weights are intentionally not tracked
- Study aid only — always cross-check IS codes and faculty solutions
