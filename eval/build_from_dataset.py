import os
import re
import json
import pandas as pd
from pathlib import Path
from collections import defaultdict
import random

ROOT = Path(__file__).parent.parent
EXCEL_PATH = ROOT / "datasets" / "Cornelius_FR_NFR_Curated_Mendeley_Dataset_2025.xlsx"
OUT_JSON = Path(__file__).parent / "dataset_real.json"
OUT_PROJECTS = Path(__file__).parent / "test_projects.txt"

SAMPLE_N = 15
RANDOM_STATE = 42
random.seed(RANDOM_STATE)

_VAGUE_RE = re.compile(r'\b(user.?friendly|intuitive|easy\s+to)\b', re.IGNORECASE)
_MISMATCH_RULES = [
    (re.compile(r'\bencrypt', re.IGNORECASE), re.compile(r'\b(RBAC|OAuth|JWT)\b', re.IGNORECASE)),
    (re.compile(r'\bauthenticat', re.IGNORECASE), re.compile(r'\b(AES|RSA|SSL)\b', re.IGNORECASE)),
    (re.compile(r'\baccess\s+control\b', re.IGNORECASE), re.compile(r'\b(AES|RSA|SSL-TLS|SSL/TLS)\b', re.IGNORECASE)),
]
_METRIC_TEMPLATES: list[tuple[str, re.Pattern[str]]] = [
    ("page_load",        re.compile(r'page\s+load[^.]*?(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)\b', re.IGNORECASE)),
    ("concurrent_users", re.compile(r'concurrent\s+users?[^.]*?(\d+(?:\.\d+)?)', re.IGNORECASE)),
    ("uptime",           re.compile(r'uptime[^.]*?(\d+(?:\.\d+)?)\s*%', re.IGNORECASE)),
    ("backup_interval",  re.compile(r'backup[^.]*?(\d+(?:\.\d+)?)\s*(?:h|hours?|min|minutes?)\b', re.IGNORECASE)),
]

def _is_vague(text: str) -> bool: return bool(_VAGUE_RE.search(text))
def _is_mechanism_mismatch(text: str) -> bool:
    return any(t.search(text) and f.search(text) for t, f in _MISMATCH_RULES)
def _normalise(text: str) -> str: return text.lower().strip()

def build_dataset():
    df = pd.read_excel(EXCEL_PATH, sheet_name="Complete_Dataset")
    projects = df.groupby("Project_Name")
    
    docs = []
    project_labels = defaultdict(set)
    
    for proj_name, group in projects:
        group = group.copy()
        descriptions = group["Description"].fillna("").tolist()
        
        # Pre-calculate to ensure we sample interesting rows
        vague_idx = [i for i, t in enumerate(descriptions) if _is_vague(t)]
        mismatch_idx = [i for i, t in enumerate(descriptions) if _is_mechanism_mismatch(t)]
        
        norm_texts = [_normalise(t) for t in descriptions]
        norm_count = defaultdict(int)
        for nt in norm_texts: norm_count[nt] += 1
        dup_idx = [i for i, nt in enumerate(norm_texts) if norm_count[nt] > 1]
        
        row_metric_nums = [{} for _ in range(len(descriptions))]
        for i, text in enumerate(descriptions):
            for m_name, pat in _METRIC_TEMPLATES:
                matches = pat.findall(text)
                if matches: row_metric_nums[i][m_name] = [float(x) for x in matches]
                
        metric_all = defaultdict(set)
        for r_dict in row_metric_nums:
            for m, nums in r_dict.items(): metric_all[m].update(nums)
            
        inconsistent_m = {m for m, vals in metric_all.items() if len(vals) >= 2}
        inc_idx = [i for i, r_dict in enumerate(row_metric_nums) if any(m in inconsistent_m for m in r_dict)]
        
        interesting = set(vague_idx + mismatch_idx + dup_idx + inc_idx)
        
        all_idx = list(range(len(descriptions)))
        random.Random(RANDOM_STATE).shuffle(all_idx)
        
        # prioritize interesting
        sample_idx = [i for i in all_idx if i in interesting]
        # pad with rest
        for i in all_idx:
            if i not in sample_idx:
                sample_idx.append(i)
        
        sample_idx = sample_idx[:SAMPLE_N]
        sample_idx.sort()
        
        # Now label the sample!
        sampled_rows = group.iloc[sample_idx].copy()
        s_desc = sampled_rows["Description"].fillna("").tolist()
        
        s_labels = [[] for _ in range(len(s_desc))]
        
        for i, t in enumerate(s_desc):
            if _is_vague(t): s_labels[i].append("vague")
            if _is_mechanism_mismatch(t): s_labels[i].append("mechanism_mismatch")
            
        s_norm = [_normalise(t) for t in s_desc]
        sn_count = defaultdict(int)
        for nt in s_norm: sn_count[nt] += 1
        for i, nt in enumerate(s_norm):
            if sn_count[nt] > 1: s_labels[i].append("duplicate")
            
        s_metrics = [{} for _ in range(len(s_desc))]
        for i, text in enumerate(s_desc):
            for m_name, pat in _METRIC_TEMPLATES:
                matches = pat.findall(text)
                if matches: s_metrics[i][m_name] = [float(x) for x in matches]
                
        sm_all = defaultdict(set)
        for r_dict in s_metrics:
            for m, nums in r_dict.items(): sm_all[m].update(nums)
        s_inc_m = {m for m, vals in sm_all.items() if len(vals) >= 2}
        
        for i, r_dict in enumerate(s_metrics):
            if any(m in s_inc_m for m in r_dict):
                s_labels[i].append("inconsistent_target")
                
        reqs = []
        for i, (_, row) in enumerate(sampled_rows.iterrows()):
            r_dict = {
                "req_id": str(row["Requirement_ID"]),
                "text": str(row["Description"]),
                "req_type": str(row["Requirement_Type"]),
                "nfr_category": str(row["NFR_Category"]) if pd.notna(row["NFR_Category"]) else None,
                "labels": s_labels[i]
            }
            reqs.append(r_dict)
            project_labels[proj_name].update(s_labels[i])
            
        docs.append({"project": proj_name, "requirements": reqs})
        
    # We want 3 test projects covering all 4 labels if possible.
    # Let's find a combination of 3 projects that has all 4 labels.
    all_projects = list(project_labels.keys())
    test_projects = []
    
    # Simple deterministic search for 3 projects that maximize label coverage
    best_combo = None
    best_coverage = 0
    for i in range(len(all_projects)):
        for j in range(i+1, len(all_projects)):
            for k in range(j+1, len(all_projects)):
                combo = [all_projects[i], all_projects[j], all_projects[k]]
                cov = len(project_labels[combo[0]] | project_labels[combo[1]] | project_labels[combo[2]])
                if cov > best_coverage or (cov == best_coverage and best_combo is None):
                    best_coverage = cov
                    best_combo = combo
                    
    test_projects = set(best_combo)
    
    # Save test projects
    with open(OUT_PROJECTS, "w", encoding="utf-8") as f:
        for tp in test_projects:
            f.write(f"{tp}\n")
            
    # Assign splits
    final_docs = []
    for i, d in enumerate(docs):
        d["doc_id"] = f"{d['project'].replace(' ', '_')}"
        d["split"] = "test" if d["project"] in test_projects else "train"
        final_docs.append(d)
        
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"documents": final_docs}, f, indent=2)

if __name__ == "__main__":
    build_dataset()
    print("Done building dataset")
