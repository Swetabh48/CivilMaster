# CivilMaster training

## Continuous improvement loop (safe)

1. Students mark solutions correct/wrong and may paste a faculty key.
2. Admin reviews pending items in the web **Admin** page (Approve auto-appends `training/datasets/approved_feedback.jsonl`).
3. Export / curate from Admin buttons, or:

```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/admin/training-export?persist=true" -o training/datasets/approved_feedback.json
python training/scripts/curate_dataset.py
```

4. Evaluate formula correctness on holdout/seed:

```bash
python training/scripts/evaluate_holdout.py
```

5. On a CUDA GPU (or free Colab T4 — see `CLOUD_TRAIN.md`), QLoRA fine-tune:

```bash
pip install -r training/requirements-train.txt
python training/scripts/train_qlora.py --data training/datasets/civilmaster_sft.jsonl
# default base model matches Colab: unsloth/Qwen2.5-3B-Instruct-bnb-4bit
```

Promote the LoRA adapter only if evaluation beats the RAG + formula-registry baseline.

Do **not** train online on every raw student upload — that poisons the model.
