$ErrorActionPreference = "Stop"

Write-Host "Waiting for PyTorch and ML dependencies to install..."
# We assume the background pip task is running. We will just wait.

# Just to be sure it's installed, we'll try to import it. If it fails, it will stop.
python -c "import torch; import peft; import trl"

Write-Host "Starting Fine-tuning process..."
python scripts/finetune_qwen.py

Write-Host "Fine-tuning complete! The adapter is saved in models/synapse-qwen-finetuned/adapter"
