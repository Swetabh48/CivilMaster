# Train CivilMaster (best recipe)

## Dataset

Rebuild anytime:

```bash
python training/scripts/build_gold_dataset.py
python training/scripts/mine_qa_from_corpus.py
python training/scripts/curate_dataset.py
```

Sources curated together: seed, gold registry/NL, mined corpus, doubt Q&A, approved feedback.
Theory/doubt pairs are kept even without digits (previously dropped by mistake).

## Modal T4 (recommended)

```bash
modal run training/modal_train.py
```

Recipe: Qwen2.5-3B QLoRA **r=32**, **α=64**, **3 epochs**, cosine LR, seq 2048, grad accum 16.
Adapter lands in `training/adapters/civilmaster-lora/`.

## Colab T4 (recommended right now)

Modal GPUs need a billing card; Colab free T4 works.

Open: https://colab.research.google.com/github/Swetabh48/CivilMaster/blob/main/training/CivilMaster_train.ipynb  
Or one cell:

```python
!wget -q -O pack.zip https://files.catbox.moe/6wd84q.zip
!unzip -o pack.zip
!python train_colab.py
```

Then download `civilmaster-lora.zip` → `training/adapters/civilmaster-lora/`

## After training

Set `LORA_ADAPTER_PATH` and restart API. Numbers still come from the formula engine; the adapter improves explanations / doubt chat.
