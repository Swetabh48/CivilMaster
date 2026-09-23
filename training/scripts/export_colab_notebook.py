"""Build a self-contained Colab notebook with CivilMaster SFT data embedded."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JSONL = ROOT / "training" / "datasets" / "civilmaster_sft.jsonl"
SYN = ROOT / "training" / "datasets" / "synthetic_qa.json"
OUT = ROOT / "training" / "CivilMaster_Colab_QLoRA.ipynb"

pairs = []
if SYN.exists():
    pairs = json.loads(SYN.read_text(encoding="utf-8"))["pairs"]
elif JSONL.exists():
    for line in JSONL.read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        msgs = obj["messages"]
        user = next(m["content"] for m in msgs if m["role"] == "user")
        asst = next(m["content"] for m in msgs if m["role"] == "assistant")
        # split instruction/input roughly
        if "\n\n" in user:
            instr, inp = user.split("\n\n", 1)
        else:
            instr, inp = "Solve correctly.", user
        pairs.append({"instruction": instr, "input": inp, "output": asst})

# Cap size for notebook embed (~ keep all ~269)
data_literal = json.dumps({"pairs": pairs}, ensure_ascii=False)

cells = []

def md(source: str):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)})

def code(source: str):
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)})

md("""# CivilMaster — Free GPU QLoRA (Google Colab T4)

1. **Runtime → Change runtime type → T4 GPU**
2. **Runtime → Run all**
3. Download the `civilmaster-lora` folder when training finishes

Uses open-source **Unsloth + Qwen2.5-3B-Instruct (4-bit QLoRA)** on Colab's free T4.
""")

code("""# 1) Confirm free GPU
!nvidia-smi
""")

code("""# 2) Install Unsloth (Colab)
!pip install -q unsloth
!pip install -q datasets trl transformers accelerate bitsandbytes
""")

code(f"""# 3) Embedded CivilMaster training set
import json
DATASET_JSON = json.loads(r'''{data_literal}''')
print('pairs:', len(DATASET_JSON['pairs']))
""")

code("""# 4) Load Qwen2.5-3B 4-bit + LoRA (fits free T4)
from unsloth import FastLanguageModel
import torch

max_seq_length = 2048
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = 'unsloth/Qwen2.5-3B-Instruct-bnb-4bit',
    max_seq_length = max_seq_length,
    dtype = None,
    load_in_4bit = True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'],
    lora_alpha = 32,
    lora_dropout = 0,
    bias = 'none',
    use_gradient_checkpointing = 'unsloth',
    random_state = 3407,
)
print('Model ready on', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')
""")

code("""# 5) Train QLoRA
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

def to_text(ex):
    messages = [
        {'role':'system','content':'You are CivilMaster, a B.Tech Civil Engineering tutor. Always use correct formulas and show steps.'},
        {'role':'user','content': f\"{ex.get('instruction','Solve correctly.')}\\n\\n{ex.get('input','')}\"},
        {'role':'assistant','content': ex.get('output','')},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)

ds = Dataset.from_list([{'text': to_text(p)} for p in DATASET_JSON['pairs']])

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = ds,
    dataset_text_field = 'text',
    max_seq_length = max_seq_length,
    packing = False,
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        num_train_epochs = 2,
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 5,
        optim = 'adamw_8bit',
        weight_decay = 0.01,
        lr_scheduler_type = 'linear',
        seed = 3407,
        output_dir = 'civilmaster_lora_out',
        report_to = 'none',
        save_strategy = 'epoch',
    ),
)
trainer.train()
""")

code("""# 6) Save adapter + smoke test
from pathlib import Path
out = Path('civilmaster-lora')
out.mkdir(exist_ok=True)
model.save_pretrained(str(out))
tokenizer.save_pretrained(str(out))
print('Saved', out.resolve())

FastLanguageModel.for_inference(model)
prompt = tokenizer.apply_chat_template([
    {'role':'system','content':'You are CivilMaster, a B.Tech Civil Engineering tutor.'},
    {'role':'user','content':'A steel bar carries axial load P = 100000 N on area A = 500 mm2. Find axial stress.'},
], tokenize=False, add_generation_prompt=True)
inputs = tokenizer(prompt, return_tensors='pt').to(model.device)
ids = model.generate(**inputs, max_new_tokens=200, temperature=0.1, do_sample=True)
print(tokenizer.decode(ids[0], skip_special_tokens=True))
""")

code("""# 7) Zip adapter for download
!zip -r civilmaster-lora.zip civilmaster-lora
from google.colab import files
files.download('civilmaster-lora.zip')
""")

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
        "colab": {"provenance": [], "gpuType": "T4"},
    },
    "cells": cells,
}
OUT.write_text(json.dumps(nb), encoding="utf-8")
print(f"Wrote {OUT} with {len(pairs)} pairs")
