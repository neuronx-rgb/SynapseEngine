"""
eval/run_eval.py
Evaluation runner for Synapse Engine.
Runs all documents in dataset.json through the pipeline and computes:
- Per-type precision/recall/F1 (ambiguity, conflict, incompleteness)
- OpenAPI validity rate
- SQL execution rate
- Requirement test coverage
Saves eval_report.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Ensure MOCK_MODE
os.environ.setdefault("MOCK_MODE", "true")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def run_pipeline_on_text(text: str) -> dict:
    """Run parse + analyze pipeline on given text. Returns issues list."""
    from backend.pipeline.parser import parse_requirements
    from backend.pipeline.analyzer import analyze

    parse_result = parse_requirements(text)
    issues = analyze(parse_result)
    return {
        "requirements": [r.model_dump() for r in parse_result.requirements],
        "issues": [i.model_dump() for i in issues],
    }


def check_ground_truth(detected_issues: list[dict], ground_truth: list[dict]) -> dict:
    """
    Compute TP, FP, FN for each issue type.
    Ground truth entry matches if:
    - type matches
    - description_contains (if present) appears in any detected issue description
    """
    tp = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}
    fp = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}
    fn = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}

    detected_by_type = {}
    for iss in detected_issues:
        t = iss["issue_type"]
        if t not in detected_by_type:
            detected_by_type[t] = []
        detected_by_type[t].append(iss)

    for gt in ground_truth:
        gt_type = gt["type"]
        dc = gt.get("description_contains", "").lower()
        found = False
        for det in detected_by_type.get(gt_type, []):
            desc = det.get("description", "").lower()
            if not dc or dc in desc:
                found = True
                break
        if found:
            tp[gt_type] = tp.get(gt_type, 0) + 1
        else:
            fn[gt_type] = fn.get(gt_type, 0) + 1

    # FP: detected issues that don't match any ground truth
    for t, issues_list in detected_by_type.items():
        gt_for_type = [g for g in ground_truth if g["type"] == t]
        extra = max(0, len(issues_list) - len(gt_for_type))
        fp[t] = fp.get(t, 0) + extra

    return {"tp": tp, "fp": fp, "fn": fn}


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def eval_validators():
    """Test OpenAPI validity and SQL execution rates on fixtures."""
    from backend.models import ArtifactOut, ArtifactType
    from backend.pipeline import validators

    openapi_valid = 0
    sql_exec_ok = 0
    total = 0

    fixture_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    for fpath in fixture_dir.glob("*.json"):
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        resp = data.get("response", {})

        if "yaml_content" in resp:
            total += 1
            art = ArtifactOut(
                artifact_type=ArtifactType.openapi,
                content=resp["yaml_content"],
                is_valid=False,
                validation_errors=[],
            )
            art = validators.validate_openapi(art)
            if art.is_valid:
                openapi_valid += 1

        if "ddl_content" in resp:
            art = ArtifactOut(
                artifact_type=ArtifactType.sql_ddl,
                content=resp["ddl_content"],
                is_valid=False,
                validation_errors=[],
            )
            art = validators.validate_sql(art)
            if art.is_valid:
                sql_exec_ok += 1

    return {
        "openapi_valid_rate": openapi_valid / max(total, 1),
        "sql_exec_rate": sql_exec_ok / max(total, 1),
    }


def eval_coverage():
    """Check test coverage rate from test plan fixture."""
    fixture_path = Path(__file__).parent.parent / "tests" / "fixtures" / "test_plan_generate.json"
    if not fixture_path.exists():
        return 0.0
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    resp = data.get("response", {})
    test_cases = resp.get("test_cases", [])
    covered_reqs = set()
    for tc in test_cases:
        for r in tc.get("req_ids", []):
            covered_reqs.add(r)

    # Compare to expected requirements from order fixture
    order_fixture = Path(__file__).parent.parent / "tests" / "fixtures" / "order_parse.json"
    if order_fixture.exists():
        with open(order_fixture, encoding="utf-8") as f:
            od = json.load(f)
        all_reqs = [r["req_id"] for r in od.get("response", {}).get("requirements", [])]
        if all_reqs:
            return len(covered_reqs & set(all_reqs)) / len(all_reqs) * 100
    return 100.0


def main():
    dataset_path = Path(__file__).parent / "dataset.json"
    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    agg_tp = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}
    agg_fp = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}
    agg_fn = {"ambiguity": 0, "conflict": 0, "incompleteness": 0}

    doc_results = []
    print("Running evaluation...")

    for doc in dataset["documents"]:
        print(f"  Processing {doc['id']}: {doc['name']}")
        result = run_pipeline_on_text(doc["text"])
        issues = result["issues"]
        gt = doc["ground_truth"]
        counts = check_ground_truth(issues, gt)

        for t in ["ambiguity", "conflict", "incompleteness"]:
            agg_tp[t] += counts["tp"].get(t, 0)
            agg_fp[t] += counts["fp"].get(t, 0)
            agg_fn[t] += counts["fn"].get(t, 0)

        doc_results.append({
            "doc_id": doc["id"],
            "name": doc["name"],
            "issues_detected": len(issues),
            "ground_truth_count": len(gt),
        })

    # Per-type metrics
    per_type = {}
    for t in ["ambiguity", "conflict", "incompleteness"]:
        p, r, f = prf(agg_tp[t], agg_fp[t], agg_fn[t])
        per_type[t] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}

    # Validator rates
    val_rates = eval_validators()
    coverage = eval_coverage()

    report = {
        "per_type": per_type,
        "overall": {
            "openapi_valid_rate": round(val_rates["openapi_valid_rate"], 3),
            "sql_exec_rate": round(val_rates["sql_exec_rate"], 3),
            "test_coverage_pct": round(coverage, 1),
        },
        "documents": doc_results,
        "totals": {"tp": agg_tp, "fp": agg_fp, "fn": agg_fn},
    }

    # Save report
    report_path = Path(__file__).parent / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n=== EVALUATION REPORT ===")
    print(f"Per-type metrics:")
    for t, m in per_type.items():
        print(f"  {t:20s}: P={m['precision']:.2f}  R={m['recall']:.2f}  F1={m['f1']:.2f}")
    print(f"\nOverall:")
    print(f"  OpenAPI valid rate:  {val_rates['openapi_valid_rate']*100:.1f}%")
    print(f"  SQL exec rate:       {val_rates['sql_exec_rate']*100:.1f}%")
    print(f"  Test coverage:       {coverage:.1f}%")
    print(f"\nReport saved to {report_path}")

    return report


if __name__ == "__main__":
    main()
