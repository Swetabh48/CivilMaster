# Train CivilMaster (optional)

## Dataset

```bash
python training/scripts/build_gold_dataset.py
python training/scripts/mine_qa_from_corpus.py
python training/scripts/curate_dataset.py
```

Sources: seed, registry/NL drills, mined corpus Q&A, doubt Q&A, approved feedback.

Pack for Colab: `training/cloud_pack/` (`civilmaster_sft.jsonl` + `train_colab.py`).

## Colab T4

Open [`CivilMaster_train.ipynb`](CivilMaster_train.ipynb) (Runtime → T4 GPU), or:

```python
# Upload training/cloud_pack/civilmaster_train_pack.zip first, or clone the repo
!unzip -o civilmaster_train_pack.zip
!python train_colab.py
```

Download `civilmaster-lora.zip` into `training/adapters/civilmaster-lora/`.

Recipe: Qwen2.5-3B QLoRA **r=32**, **α=64**, **3 epochs**, cosine LR, seq 2048.

## Modal (needs GPU billing)

```bash
modal run training/modal_train.py
```

## After training

Set `LORA_ADAPTER_PATH` (or place files under `training/adapters/civilmaster-lora/`) and restart the API. Numbers still come from the formula engine; the adapter improves explanations / doubt chat.
