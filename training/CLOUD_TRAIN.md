# Train CivilMaster on free Google Colab T4

Modal GPUs now require a payment card on this account, so training uses **Google Colab free T4** (open-source Unsloth + Qwen2.5-3B QLoRA).

## One-click steps

1. Open [Google Colab](https://colab.research.google.com/)
2. **File → Upload notebook**
3. Select:
   `training/CivilMaster_Colab_QLoRA.ipynb`
4. **Runtime → Change runtime type → T4 GPU → Save**
5. **Runtime → Run all**
6. When finished, download `civilmaster-lora.zip`
7. Unzip into:
   `training/adapters/civilmaster-lora/`

## What gets trained

- Base: `unsloth/Qwen2.5-3B-Instruct-bnb-4bit` (open weights)
- Method: QLoRA (r=16)
- Data: civil formula Q&A pairs (mined + synthetic + approved feedback)
- Holdout eval: `python training/scripts/evaluate_holdout.py`

## After download — wiring

1. Confirm files exist:
   - `training/adapters/civilmaster-lora/adapter_config.json`
   - `training/adapters/civilmaster-lora/adapter_model.safetensors`
2. Set in `.env`:
   ```
   LORA_ADAPTER_PATH=./training/adapters/civilmaster-lora
   ```
3. Runtime priority in the API (`/health` → `llm_backend`):
   - **lora** — CUDA + peft/transformers/bitsandbytes available
   - **ollama** — `OLLAMA_BASE_URL` reachable (optional: `docker compose --profile llm up ollama`)
   - **registry** — formula engine narrative (always correct numbers)

Docker Compose mounts `./training/adapters` at `/adapters` and sets `LORA_ADAPTER_PATH=/adapters/civilmaster-lora`.

## Continuous improvement loop

1. Students mark solutions correct/wrong (+ optional faculty key) on the solve page
2. Admin **Approve** on `/admin` → row appended to `training/datasets/approved_feedback.jsonl`
3. Admin **Export / Curate for retrain** (or CLI):
   ```
   python training/scripts/curate_dataset.py
   ```
4. Re-run Colab / `train_qlora.py` and replace the adapter folder

## OCR for scanned PDFs

```
pip install rapidocr-onnxruntime
python scripts/ocr_reingest.py --limit 50
```

Writes `*.pdf.ocr.txt` sidecars and re-indexes unindexed files.
