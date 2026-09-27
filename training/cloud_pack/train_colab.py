#!/usr/bin/env python3
"""CivilMaster QLoRA on Colab T4 — stronger recipe for better adapters."""
import json, os, subprocess, sys
from pathlib import Path

subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "unsloth"])
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "datasets", "trl", "transformers", "accelerate", "bitsandbytes"])

from unsloth import FastLanguageModel
import torch
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

assert torch.cuda.is_available(), "Enable T4 GPU: Runtime > Change runtime type > T4"
print("GPU:", torch.cuda.get_device_name(0))

data_path = Path("civilmaster_sft.jsonl")
if not data_path.exists():
    data_path = Path("/content/civilmaster_sft.jsonl")
rows = [json.loads(l) for l in data_path.read_text(encoding="utf-8").splitlines() if l.strip()]
print("pairs:", len(rows))

max_seq_length = 2048
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-3B-Instruct-bnb-4bit",
    max_seq_length=max_seq_length,
    dtype=None,
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=64,
    lora_dropout=0.05,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

def to_text(ex):
    return tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)

ds = Dataset.from_list([{"text": to_text(r)} for r in rows])
# Small holdout slice from the pack itself for sanity logging
n = len(ds)
split = max(1, int(0.08 * n))
train_ds = ds.select(range(split, n)) if n > 20 else ds
print("train_rows:", len(train_ds))

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_ds,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        warmup_ratio=0.06,
        num_train_epochs=3,
        learning_rate=1.5e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=3407,
        output_dir="civilmaster_lora_out",
        report_to="none",
        save_strategy="epoch",
        max_grad_norm=1.0,
    ),
)
trainer.train()
out = Path("civilmaster-lora")
out.mkdir(exist_ok=True)
model.save_pretrained(str(out))
tokenizer.save_pretrained(str(out))
print("SAVED", out.resolve())
FastLanguageModel.for_inference(model)
prompt = tokenizer.apply_chat_template(
    [
        {"role": "system", "content": "You are CivilMaster, a B.Tech Civil Engineering tutor."},
        {
            "role": "user",
            "content": "A steel bar carries axial load P = 100000 N on area A = 500 mm2. Find axial stress. Show the formula.",
        },
    ],
    tokenize=False,
    add_generation_prompt=True,
)
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
ids = model.generate(**inputs, max_new_tokens=220, temperature=0.05, do_sample=True)
print(tokenizer.decode(ids[0], skip_special_tokens=True))
subprocess.check_call(["zip", "-r", "civilmaster-lora.zip", "civilmaster-lora"])
print("ZIP_READY civilmaster-lora.zip")
