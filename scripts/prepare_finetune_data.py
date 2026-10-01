import os
import json
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split

def prepare_dataset():
    print("Loading dataset...")
    df = pd.read_excel('datasets/Cornelius_FR_NFR_Curated_Mendeley_Dataset_2025.xlsx', sheet_name='Complete_Dataset')
    
    # We will format this into a standard ChatML style JSONL
    # System: You are a requirements engineer. Classify the given software requirement.
    # User: <Requirement Description>
    # Assistant: {"Requirement_Type": "...", "NFR_Category": "..."}
    
    dataset = []
    for _, row in df.iterrows():
        description = str(row.get('Description', '')).strip()
        req_type = str(row.get('Requirement_Type', '')).strip()
        nfr_cat = str(row.get('NFR_Category', 'None')).strip()
        
        if pd.isna(row.get('NFR_Category')):
            nfr_cat = "None"
            
        if not description or description.lower() == 'nan':
            continue
            
        system_msg = "You are an expert requirements engineer for the Synapse Engine. Classify the following software requirement as Functional or Non-Functional, and provide its category if applicable."
        
        user_msg = description
        
        # We output valid JSON for the assistant so the model learns structured outputs
        assistant_msg = json.dumps({
            "Requirement_Type": req_type,
            "NFR_Category": nfr_cat if req_type == "Non-Functional" else None
        })
        
        # Create OpenAI/ChatML style message array
        conversation = {
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg}
            ]
        }
        dataset.append(conversation)
        
    print(f"Generated {len(dataset)} examples.")
    
    # Split into train/val
    train_data, val_data = train_test_split(dataset, test_size=0.1, random_state=42)
    
    os.makedirs('data/finetune', exist_ok=True)
    
    train_path = 'data/finetune/train.jsonl'
    val_path = 'data/finetune/val.jsonl'
    
    with open(train_path, 'w', encoding='utf-8') as f:
        for item in train_data:
            f.write(json.dumps(item) + '\n')
            
    with open(val_path, 'w', encoding='utf-8') as f:
        for item in val_data:
            f.write(json.dumps(item) + '\n')
            
    print(f"Saved {len(train_data)} to {train_path}")
    print(f"Saved {len(val_data)} to {val_path}")

if __name__ == "__main__":
    prepare_dataset()
