import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

def finetune():
    model_id = "Qwen/Qwen2.5-3B-Instruct" # Base model mapping to qwen3:4b size class
    output_dir = "models/synapse-qwen-finetuned"
    
    print(f"Loading tokenizer for {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    
    # QLoRA config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16
    )
    
    print("Loading model in 4-bit...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    model.config.use_cache = False
    
    model = prepare_model_for_kbit_training(model)
    
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    print("Loading dataset...")
    # Load the JSONL files we prepared
    dataset = load_dataset("json", data_files={
        "train": "data/finetune/train.jsonl",
        "test": "data/finetune/val.jsonl"
    })
    
    # Map the messages to the model's chat template
    def format_chat_template(example):
        example["text"] = tokenizer.apply_chat_template(example["messages"], tokenize=False)
        return example
        
    dataset = dataset.map(format_chat_template)
    
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        optim="paged_adamw_8bit",
        save_steps=100,
        logging_steps=10,
        learning_rate=2e-4,
        fp16=True, 
        bf16=False, 
        max_grad_norm=0.3,
        max_steps=200, 
        warmup_steps=10,
        lr_scheduler_type="cosine",
        report_to="none",
        gradient_checkpointing=True
    )
    
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        peft_config=peft_config,
        processing_class=tokenizer,
        args=training_args,
    )
    
    print("Starting training...")
    trainer.train()
    
    print("Saving adapter...")
    trainer.model.save_pretrained(f"{output_dir}/adapter")
    tokenizer.save_pretrained(f"{output_dir}/adapter")
    print("Training complete! Adapter saved.")

if __name__ == "__main__":
    finetune()
