$ErrorActionPreference = "Continue"

Write-Host ">>> Step 1: Installing PyTorch (CUDA 12.1)..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir

Write-Host ">>> Step 2: Installing ML Stack (transformers, peft, trl, bitsandbytes)..."
pip install transformers peft trl datasets bitsandbytes accelerate huggingface_hub --no-cache-dir

Write-Host ">>> Step 3: Starting QLoRA Fine-tuning..."
python scripts/finetune_qwen.py

Write-Host ">>> Done! Check models/synapse-qwen-finetuned/adapter for the saved weights."
