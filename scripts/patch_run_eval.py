import os

with open('eval/run_eval.py', 'r', encoding='utf-8') as f:
    content = f.read()

from scripts.eval_extension import new_code

if 'eval_real_dataset_metrics' not in content:
    main_idx = content.find('def main():')
    new_content = content[:main_idx] + new_code + content[main_idx:]
    
    main_mod = """
    # Add new dataset metrics
    dataset_metrics = eval_real_dataset_metrics()
    baseline_metrics = eval_fr_nfr_baseline()
    dup_metrics = eval_duplicate_detector()
    eval_llm_classifier()
    
    report['dataset_real'] = {
        'per_label': dataset_metrics,
        'fr_nfr_baseline': baseline_metrics,
        'duplicate_detector': dup_metrics
    }
    
    print("\\n=== REAL DATASET METRICS ===")
    if dataset_metrics:
        for lbl, m in dataset_metrics.items():
            print(f"  {lbl:20s}: P={m['precision']:.2f}  R={m['recall']:.2f}  F1={m['f1']:.2f}")
    if baseline_metrics:
        print(f"\\n  FR/NFR Baseline Type Acc: {baseline_metrics.get('type_accuracy', 0)*100:.1f}%")
        print(f"  FR/NFR Baseline Cat Acc:  {baseline_metrics.get('nfr_category_accuracy', 0)*100:.1f}%")
    if dup_metrics:
        print(f"\\n  Duplicate Detector: P={dup_metrics.get('precision', 0):.2f}  R={dup_metrics.get('recall', 0):.2f}  F1={dup_metrics.get('f1', 0):.2f}")
        
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
"""
    ret_idx = new_content.rfind('return report')
    new_content = new_content[:ret_idx] + main_mod + new_content[ret_idx:]
    
    with open('eval/run_eval.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Updated run_eval.py successfully.')
else:
    print('Already updated.')
