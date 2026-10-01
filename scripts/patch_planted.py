import os

with open('eval/run_eval.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We want to replace check_ground_truth and main loop with a more detailed one
# that prints the table and calculates doc-level and issue-level stats.

new_check = """
def check_ground_truth(detected_issues: list[dict], ground_truth: list[dict]) -> dict:
    # This function is now just a helper or we inline it.
    pass
    
def print_planted_flaw_table(doc_id, name, gt, issues):
    print(f"\\n  === {doc_id}: {name} ===")
    print(f"  EXPECTED:")
    for g in gt:
        reqs = ",".join(g.get("involved_req_ids", []))
        print(f"    - [{g['type']}] Reqs: {reqs} | Match: {g.get('description_contains', '')}")
    print(f"  PREDICTED:")
    if not issues:
        print("    (none)")
    for iss in issues:
        reqs = ",".join(iss.get("involved_req_ids", []))
        rule = iss.get("issue_id", "").split("-")[1] if "-" in iss.get("issue_id", "") else "unknown"
        print(f"    - [{iss['issue_type']}] Reqs: {reqs} | Detector: {rule} | Desc: {iss.get('description', '')[:60]}...")

def evaluate_planted_flaws(detected_issues: list[dict], ground_truth: list[dict]):
    # document-level: did we find at least one issue of the expected type?
    doc_tp = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}
    doc_fp = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}
    doc_fn = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}
    
    # issue-level: type + overlapping req ids
    iss_tp = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}
    iss_fp = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}
    iss_fn = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}

    # Merge duplicates across detectors before scoring
    merged_issues = []
    seen = set()
    for iss in detected_issues:
        reqs = tuple(sorted(iss.get("involved_req_ids", [])))
        key = (iss["issue_type"], reqs)
        if key not in seen:
            seen.add(key)
            merged_issues.append(iss)

    gt_types = {g["type"] for g in ground_truth}
    det_types = {iss["issue_type"] for iss in merged_issues}
    
    for t in ["ambiguity", "conflict", "incompleteness"]:
        if t in gt_types and t in det_types: doc_tp[t] += 1
        elif t in gt_types and t not in det_types: doc_fn[t] += 1
        elif t not in gt_types and t in det_types: doc_fp[t] += 1

    # Issue level overlapping reqs
    for gt in ground_truth:
        gt_t = gt["type"]
        gt_reqs = set(gt.get("involved_req_ids", []))
        dc = gt.get("description_contains", "").lower()
        
        found = False
        for det in merged_issues:
            if det["issue_type"] != gt_t: continue
            det_reqs = set(det.get("involved_req_ids", []))
            desc = det.get("description", "").lower()
            
            # overlap reqs or description matches
            if (gt_reqs and gt_reqs & det_reqs) or (dc and dc in desc):
                found = True
                break
        
        if found: iss_tp[gt_t] += 1
        else: iss_fn[gt_t] += 1
        
        if gt_t == "ambiguity" and not found:
            print(f"    [MISSED AMBIGUITY] Expected: {dc} in {gt_reqs}. Cause: Lexicon missing term or parse fixture gap.")
            
    # FP for issue level: any merged issue not matching a GT
    for det in merged_issues:
        det_t = det["issue_type"]
        det_reqs = set(det.get("involved_req_ids", []))
        desc = det.get("description", "").lower()
        
        matched_gt = False
        for gt in ground_truth:
            if gt["type"] != det_t: continue
            gt_reqs = set(gt.get("involved_req_ids", []))
            dc = gt.get("description_contains", "").lower()
            if (gt_reqs and gt_reqs & det_reqs) or (dc and dc in desc):
                matched_gt = True
                break
        if not matched_gt:
            iss_fp[det_t] += 1
            
    return {"doc_tp": doc_tp, "doc_fp": doc_fp, "doc_fn": doc_fn, 
            "iss_tp": iss_tp, "iss_fp": iss_fp, "iss_fn": iss_fn}
"""

replacement_main = """
def main():
    print("=========================================================================")
    print("BANNER: LLM stages use fixtures; results reflect the deterministic layer only")
    print("=========================================================================\\n")

    dataset_path = Path(__file__).parent / "dataset.json"
    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    agg_doc = {"tp": {"ambiguity": 0, "conflict": 0, "incompleteness": 0},
               "fp": {"ambiguity": 0, "conflict": 0, "incompleteness": 0},
               "fn": {"ambiguity": 0, "conflict": 0, "incompleteness": 0}}
               
    agg_iss = {"tp": {"ambiguity": 0, "conflict": 0, "incompleteness": 0},
               "fp": {"ambiguity": 0, "conflict": 0, "incompleteness": 0},
               "fn": {"ambiguity": 0, "conflict": 0, "incompleteness": 0}}

    doc_results = []
    print("Running evaluation on planted flaws...")

    for doc in dataset["documents"]:
        result = run_pipeline_on_text(doc["text"])
        issues = result["issues"]
        gt = doc["ground_truth"]
        
        print_planted_flaw_table(doc["id"], doc["name"], gt, issues)
        
        counts = evaluate_planted_flaws(issues, gt)

        for t in ["ambiguity", "conflict", "incompleteness"]:
            agg_doc["tp"][t] += counts["doc_tp"].get(t, 0)
            agg_doc["fp"][t] += counts["doc_fp"].get(t, 0)
            agg_doc["fn"][t] += counts["doc_fn"].get(t, 0)
            
            agg_iss["tp"][t] += counts["iss_tp"].get(t, 0)
            agg_iss["fp"][t] += counts["iss_fp"].get(t, 0)
            agg_iss["fn"][t] += counts["iss_fn"].get(t, 0)

        doc_results.append({
            "doc_id": doc["id"],
            "name": doc["name"],
            "issues_detected": len(issues),
            "ground_truth_count": len(gt),
        })

    # Per-type metrics (Issue-level)
    per_type = {}
    for t in ["ambiguity", "conflict", "incompleteness"]:
        p, r, f = prf(agg_iss["tp"][t], agg_iss["fp"][t], agg_iss["fn"][t])
        per_type[t] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}
"""

import re
# Replace check_ground_truth
content = re.sub(r'def check_ground_truth.*?return {"tp": tp, "fp": fp, "fn": fn}', new_check, content, flags=re.DOTALL)

# Replace main up to Validator rates
content = re.sub(r'def main\(\):.*?# Validator rates', replacement_main + '\n    # Validator rates', content, flags=re.DOTALL)

with open('eval/run_eval.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched run_eval.py")
