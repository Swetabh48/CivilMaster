# CivilMaster

B.Tech Civil assignment helper that actually checks the formulas instead of guessing.

Most chatbots freely invent stress/strain numbers. This one runs a formula registry first, pulls relevant notes from your own PDFs, then (optionally) writes the steps in plain language. If the LLM is offline, you still get the numerical solution.

## What it does

- Solve typed or uploaded problems (SoM, RCC, steel, geotech basics)
- Show step-by-step work with the formula used and units
- Draw simple SVG diagrams when it makes sense
- Search an indexed corpus of your textbooks / labs / PYQs
- Collect feedback so wrong answers can be fixed and used for later fine-tuning

## Stack

| Part | Tech |
|------|------|
| API | FastAPI |
| UI | Next.js |
| DB | SQLite locally, Postgres + pgvector via Docker |
| Optional narration | Ollama / local LoRA adapter |

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

Register with the email in `ADMIN_EMAIL` (default `admin@example.com`) to get admin rights. Password needs 12+ chars with upper, lower, digit, and a symbol.

### Optional extras

```bash
# local LLM for explanations
ollama pull qwen2.5:7b
ollama serve

# Postgres instead of SQLite
docker compose up -d db
```

Drop PDFs under `data/corpus/` (semester folders help), then Admin → ingest. Scanned books:

```bash
python scripts/ocr_reingest.py
```

## Training (optional)

QLoRA scripts live in `training/`. Free Colab T4 path is documented in `training/CLOUD_TRAIN.md`. Put the adapter at:

```
training/adapters/civilmaster-lora/
```

The formula engine stays the source of truth for numbers either way.

## Feedback loop

1. Mark a solution correct / wrong on the solve page
2. Admin approves useful corrections
3. Export / curate into `training/datasets/civilmaster_sft.jsonl`
4. Retrain when you have enough clean pairs

## Repo layout

```
backend/     FastAPI app, formulas, RAG, OCR
frontend/    Next.js UI
training/    datasets + QLoRA / Colab helpers
scripts/     ingest + OCR utilities
data/        local DB, uploads, corpus (not tracked)
```

## Notes

- Keep `.env` out of git — copy from `.env.example`
- Large PDFs and model weights are gitignored on purpose
- This is a study tool, not a substitute for IS codes / faculty solutions
