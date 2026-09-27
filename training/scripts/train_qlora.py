"""
QLoRA fine-tune script for CivilMaster on Qwen2.5-Instruct.

Requires a CUDA GPU (recommended 16GB+). Install extras:
  pip install -r training/requirements-train.txt

Usage:
  python training/scripts/curate_dataset.py
  python training/scripts/train_qlora.py --data training/datasets/civilmaster_sft.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="unsloth/Qwen2.5-3B-Instruct-bnb-4bit",
        help="Base HF model id (matches Colab CivilMaster adapter)",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("training/datasets/civilmaster_sft.jsonl"),
    )
    parser.add_argument("--out", type=Path, default=Path("training/adapters/civilmaster-lora"))
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1.5e-4)
    parser.add_argument("--max-seq-len", type=int, default=2048)
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"Dataset not found: {args.data}. Run curate_dataset.py first.")

    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            TrainingArguments,
        )
        from trl import SFTTrainer
    except ImportError as exc:
        raise SystemExit(
            "Training dependencies missing. Install training/requirements-train.txt "
            f"on a GPU machine. ({exc})"
        ) from exc

    if not torch.cuda.is_available():
        print("WARNING: CUDA not available — QLoRA will be extremely slow or fail.")

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)
    lora = LoraConfig(
        r=32,
        lora_alpha=64,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)

    ds = load_dataset("json", data_files=str(args.data), split="train")

    def formatting(example: dict) -> str:
        messages = example["messages"]
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)

    args.out.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(args.out),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=8,
        learning_rate=args.lr,
        logging_steps=5,
        save_strategy="epoch",
        bf16=torch.cuda.is_available(),
        report_to=[],
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        formatting_func=formatting,
        args=training_args,
        max_seq_length=args.max_seq_len,
    )
    trainer.train()
    trainer.model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"Saved LoRA adapter to {args.out}")
    print("Promote only after evaluating on the holdout set for formula correctness.")


if __name__ == "__main__":
    main()
