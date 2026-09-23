# CivilMaster — Free Colab T4 QLoRA (Unsloth + Qwen2.5)
# Runtime → Change runtime type → GPU (T4) → Run all

from pathlib import Path
import json, os, subprocess, sys

print("GPU check:")
subprocess.run(["nvidia-smi"], check=False)

# Install Unsloth stack for Colab
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "unsloth"])
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "datasets", "trl", "transformers", "accelerate", "bitsandbytes"])

from unsloth import FastLanguageModel
import torch
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# ============ PASTE DATASET BELOW (auto-filled by export script) ============
# DATASET_JSON = {...}
# ============================================================================

assert "DATASET_JSON" in globals() or "DATASET_JSON" in dir(), "DATASET_JSON missing"

pairs = DATASET_JSON["pairs"] if isinstance(DATASET_JSON, dict) else DATASET_JSON
print(f"Training pairs: {len(pairs)}")

max_seq_length = 2048
model_name = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"  # fits free Colab T4 reliably

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=max_seq_length,
    dtype=None,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

def to_text(ex):
    messages = [
        {"role": "system", "content": "You are CivilMaster, a B.Tech Civil Engineering tutor. Always use correct formulas and show steps."},
        {"role": "user", "content": f"{ex.get('instruction','Solve correctly.')}\n\n{ex.get('input','')}"},
        {"role": "assistant", "content": ex.get("output", "")},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)

rows = [{"text": to_text(p)} for p in pairs]
ds = Dataset.from_list(rows)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=ds,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        num_train_epochs=2,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="civilmaster_lora_out",
        report_to="none",
        save_strategy="epoch",
    ),
)

trainer.train()
out = Path("civilmaster-lora")
out.mkdir(exist_ok=True)
model.save_pretrained(str(out))
tokenizer.save_pretrained(str(out))
print("Saved LoRA adapter to", out.resolve())

# Quick smoke generation
FastLanguageModel.for_inference(model)
prompt = tokenizer.apply_chat_template(
    [
        {"role": "system", "content": "You are CivilMaster, a B.Tech Civil Engineering tutor."},
        {"role": "user", "content": "A steel bar carries axial load P = 100000 N on area A = 500 mm2. Find axial stress."},
    ],
    tokenize=False,
    add_generation_prompt=True,
)
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
out_ids = model.generate(**inputs, max_new_tokens=256, temperature=0.2, do_sample=True)
print(tokenizer.decode(out_ids[0], skip_special_tokens=True))
