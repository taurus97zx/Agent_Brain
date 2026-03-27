#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepSeek 联通缴费场景微调脚本（LoRA + HF + PEFT）

注意：
- 实际训练建议在单独的“训练项目目录”中使用本脚本（而不是直接在 Agent_Brain 根目录运行）
- 运行前需准备好 JSONL 格式的数据文件（示例字段：instruction / output）
"""

import os
from typing import Dict

import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model


# ======================
# 基础配置（按需修改）
# ======================

# 1. 基础模型（替换为你实际使用的 DeepSeek 开源模型名称）
BASE_MODEL = os.environ.get(
    "DEESEEK_BASE_MODEL", "deepseek-ai/deepseek-llm-7b-chat"
)

# 2. 训练数据路径（JSONL，每行一个样本）
#   示例字段：
#   {"instruction": "帮我给 13800000000 充 50 元话费", "output": "客服标准回复..."}
DATA_PATH = os.environ.get("UNICOM_SFT_DATA", "unicom_billing_sft.jsonl")

# 3. 输出目录（保存 LoRA 适配器和 tokenizer）
OUTPUT_DIR = os.environ.get("UNICOM_SFT_OUTPUT", "deepseek-unicom-lora")

# 4. 最大长度 / 训练轮数等（按显存和数据量调整）
MAX_SEQ_LEN = int(os.environ.get("UNICOM_SFT_MAX_SEQ_LEN", "1024"))
NUM_EPOCHS = float(os.environ.get("UNICOM_SFT_EPOCHS", "3"))
LEARNING_RATE = float(os.environ.get("UNICOM_SFT_LR", "2e-4"))
BATCH_SIZE = int(os.environ.get("UNICOM_SFT_BATCH_SIZE", "2"))
GRAD_ACCUM_STEPS = int(os.environ.get("UNICOM_SFT_GRAD_ACCUM", "8"))


def format_example(example: Dict) -> Dict:
    """
    把 instruction / output 拼成聊天式文本：
    - instruction：用户的自然语言问题
    - output：联通客服标准回答
    """
    instruction = (example.get("instruction") or "").strip()
    output = (example.get("output") or "").strip()

    prompt = (
        "你是中国联通的智能客服，负责话费充值、账单查询、余额查询等业务，"
        "必须保证账务信息严谨、礼貌、专业，遇到风险场景要提醒用户注意安全。\n\n"
        f"用户：{instruction}\n"
        "客服："
    )
    full_text = prompt + output
    return {"text": full_text}


def main() -> None:
    # 1. 加载 tokenizer 和基础模型
    print(f"[INFO] 加载基础模型：{BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 统一用手动 device，而不是 device_map="auto"（避免 offload 报错）
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype="auto",
    )
    model.to(device)

    # 2. 配置 LoRA
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 3. 加载并格式化数据集
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"找不到训练数据文件：{DATA_PATH}，请先准备 JSONL 数据或设置 UNICOM_SFT_DATA 环境变量。"
        )

    raw_ds = load_dataset("json", data_files={"train": DATA_PATH})
    ds = raw_ds["train"].map(format_example)

    def tokenize_fn(batch: Dict) -> Dict:
        return tokenizer(
            batch["text"],
            max_length=MAX_SEQ_LEN,
            truncation=True,
            padding="max_length",
        )

    tokenized_ds = ds.map(
        tokenize_fn,
        batched=True,
        remove_columns=ds.column_names,
    )

    # 简单处理：labels = input_ids（对整段计算 loss）
    def add_labels(batch: Dict) -> Dict:
        batch["labels"] = batch["input_ids"].copy()
        return batch

    tokenized_ds = tokenized_ds.map(add_labels, batched=True)

    # 4. 训练参数
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM_STEPS,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        logging_steps=10,
        save_steps=200,
        save_total_limit=2,
        bf16=False,
        fp16=False,
        optim="adamw_torch",
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_ds,
    )

    # 5. 开始训练
    print("[INFO] 开始训练 DeepSeek LoRA（联通缴费场景）...")
    trainer.train()

    # 6. 保存 LoRA 适配器和 tokenizer
    print(f"[INFO] 训练完成，保存到：{OUTPUT_DIR}")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)


if __name__ == "__main__":
    main()

