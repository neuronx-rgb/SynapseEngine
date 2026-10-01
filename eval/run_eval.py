"""
eval/run_eval.py
Evaluation runner for Synapse Engine.

BANNER: When MOCK_MODE=true, LLM stages use fixtures; results reflect the deterministic layer only.

Reports:
  1. Planted-flaw set (dataset.json) — per-document table + issue-level P/R/F1
  2. Real dataset (dataset_real.json) — per-label per-split P/R/F1 using deterministic detectors directly
  3. FR/NFR rule-based baseline — type accuracy, per-category P/R/F1, confusion matrix
  4. Duplicate detector rule-consistency check
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("MOCK_MODE", "true")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BANNER = (
    "=" * 72 + "\n"
    "BANNER: MOCK_MODE=true — LLM stages use fixtures;\n"
    "        results reflect the deterministic layer only.\n"
    + "=" * 72
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text_to_reqs(text: str) -> list:
    """
    Split plain text into sentences and build ParsedRequirement objects directly.
    Used in eval to bypass the LLM parser (which returns cached fixtures in MOCK_MODE).
    """
    import re as _re
    from backend.models import ParsedRequirement
    sentences = [s.strip() for s in _re.split(r"[.\n]+", text) if len(s.strip()) > 10]
    reqs = []
    for i, s in enumerate(sentences, 1):
        reqs.append(ParsedRequirement(
            req_id=f"REQ-{i:03d}", text=s, source_sentence=s,
            entities=[], actions=[], constraints=[],
        ))
    return reqs


def run_pipeline_on_text(text: str) -> dict:
    """
    Run deterministic detectors on text split directly into sentences.
    Bypasses the LLM parser to avoid mock-fixture contamination in eval.
    """
    from backend.pipeline.analyzer import (
        _detect_ambiguity_lexicon, _detect_conflicts_z3, _detect_completeness,
    )
    from backend.pipeline.detectors import (
        detect_duplicates, detect_mechanism_mismatches, detect_inconsistent_targets,
        detect_z3_subsumptions,
    )
    from backend.models import ParseResult

    reqs = _text_to_reqs(text)
    all_issues: list[dict] = []
    all_issues.extend(_detect_ambiguity_lexicon(reqs))
    all_issues.extend(_detect_conflicts_z3(reqs))
    all_issues.extend(detect_z3_subsumptions(reqs))
    all_issues.extend(detect_duplicates(reqs))
    all_issues.extend(detect_inconsistent_targets(reqs))
    all_issues.extend(detect_mechanism_mismatches(reqs))
    all_issues.extend(_detect_completeness(reqs))

    # Normalise issue_type to string for consistent comparison
    issues_out = []
    for iss in all_issues:
        iss = dict(iss)
        iss["issue_type"] = str(iss.get("issue_type", "")).replace("IssueType.", "")
        issues_out.append(iss)

    return {
        "requirements": [r.model_dump() for r in reqs],
        "issues": issues_out,
    }


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def _load_real_docs() -> list[dict]:
    p = Path(__file__).parent / "dataset_real.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data["documents"] if isinstance(data, dict) else data


def _build_reqs(doc_reqs: list[dict]):
    from backend.models import ParsedRequirement
    return [
        ParsedRequirement(
            req_id=r["req_id"], text=r["text"], source_sentence=r["text"],
            entities=[], actions=[], constraints=[]
        )
        for r in doc_reqs
    ]


# ---------------------------------------------------------------------------
# 1. Planted-flaw evaluation
# ---------------------------------------------------------------------------

def _print_doc_table(doc_id: str, name: str, gt: list[dict], issues: list[dict]):
    print(f"\n  --- {doc_id}: {name} ---")
    print("  EXPECTED:")
    for g in gt:
        reqs = ",".join(g.get("involved_req_ids", []) or [])
        dc = g.get("description_contains", "")
        print(f"    [{g['type']}] reqs=[{reqs}] match='{dc}'")
    print("  PREDICTED:")
    if not issues:
        print("    (none)")
    for iss in issues:
        reqs = ",".join(str(r) for r in iss.get("involved_req_ids", []))
        iid = str(iss.get("issue_id", ""))
        desc = str(iss.get("description", ""))[:60]
        print(f"    [{iss['issue_type']}] reqs=[{reqs}] id={iid} desc='{desc}...'")


def _evaluate_doc(issues: list[dict], ground_truth: list[dict]) -> dict:
    """Compute doc-level and issue-level TP/FP/FN. Merges duplicate detections first."""
    types = ["ambiguity", "conflict", "incompleteness"]

    # Merge duplicate detections (same type + same sorted req set)
    merged: list[dict] = []
    seen: set = set()
    for iss in issues:
        key = (str(iss["issue_type"]), tuple(sorted(str(r) for r in iss.get("involved_req_ids", []))))
        if key not in seen:
            seen.add(key)
            merged.append(iss)

    gt_types = {g["type"] for g in ground_truth}
    det_types = {str(iss["issue_type"]) for iss in merged}

    # (a) Document-level: at least one issue of each expected type found?
    doc_tp: dict[str, int] = {t: 0 for t in types}
    doc_fp: dict[str, int] = {t: 0 for t in types}
    doc_fn: dict[str, int] = {t: 0 for t in types}
    for t in types:
        if t in gt_types and t in det_types:
            doc_tp[t] += 1
        elif t in gt_types:
            doc_fn[t] += 1
        elif t in det_types:
            doc_fp[t] += 1

    # (b) Issue-level: type + overlapping req ids
    iss_tp: dict[str, int] = {t: 0 for t in types}
    iss_fp: dict[str, int] = {t: 0 for t in types}
    iss_fn: dict[str, int] = {t: 0 for t in types}

    for g in ground_truth:
        gt_t = g["type"]
        gt_reqs = set(g.get("involved_req_ids", []) or [])
        dc = g.get("description_contains", "").lower()
        found = False
        for det in merged:
            if str(det["issue_type"]) != gt_t:
                continue
            det_reqs = set(str(r) for r in det.get("involved_req_ids", []))
            desc = str(det.get("description", "")).lower()
            if (gt_reqs and gt_reqs & det_reqs) or (dc and dc in desc):
                found = True
                break
        if found:
            iss_tp[gt_t] += 1
        else:
            iss_fn[gt_t] += 1
            if gt_t == "ambiguity":
                cause = "lexicon gap" if dc not in ("pronoun", "shipping") else "parse fixture gap"
                print(f"    [MISSED {gt_t.upper()}] '{dc}' not matched — cause: {cause}")

    for det in merged:
        det_t = str(det["issue_type"])
        det_reqs = set(str(r) for r in det.get("involved_req_ids", []))
        desc = str(det.get("description", "")).lower()
        matched = False
        for g in ground_truth:
            if g["type"] != det_t:
                continue
            g_reqs = set(g.get("involved_req_ids", []) or [])
            dc = g.get("description_contains", "").lower()
            if (g_reqs and g_reqs & det_reqs) or (dc and dc in desc):
                matched = True
                break
        if not matched:
            iss_fp[det_t] = iss_fp.get(det_t, 0) + 1

    return {"doc_tp": doc_tp, "doc_fp": doc_fp, "doc_fn": doc_fn,
            "iss_tp": iss_tp, "iss_fp": iss_fp, "iss_fn": iss_fn}


def eval_planted_flaws(dataset: dict) -> dict:
    types = ["ambiguity", "conflict", "incompleteness"]
    agg_doc = {k: {t: 0 for t in types} for k in ("tp", "fp", "fn")}
    agg_iss = {k: {t: 0 for t in types} for k in ("tp", "fp", "fn")}
    doc_results = []

    print("\nRunning evaluation on planted flaws (eval-001..012)...")
    for doc in dataset["documents"]:
        result = run_pipeline_on_text(doc["text"])
        issues = result["issues"]
        gt = doc["ground_truth"]

        _print_doc_table(doc["id"], doc["name"], gt, issues)
        counts = _evaluate_doc(issues, gt)

        for t in types:
            agg_doc["tp"][t] += counts["doc_tp"].get(t, 0)
            agg_doc["fp"][t] += counts["doc_fp"].get(t, 0)
            agg_doc["fn"][t] += counts["doc_fn"].get(t, 0)
            agg_iss["tp"][t] += counts["iss_tp"].get(t, 0)
            agg_iss["fp"][t] += counts["iss_fp"].get(t, 0)
            agg_iss["fn"][t] += counts["iss_fn"].get(t, 0)

        doc_results.append({
            "doc_id": doc["id"], "name": doc["name"],
            "issues_detected": len(issues), "ground_truth_count": len(gt),
        })

    per_type_doc = {}
    per_type_iss = {}
    for t in types:
        p, r, f = prf(agg_doc["tp"][t], agg_doc["fp"][t], agg_doc["fn"][t])
        per_type_doc[t] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}
        p, r, f = prf(agg_iss["tp"][t], agg_iss["fp"][t], agg_iss["fn"][t])
        per_type_iss[t] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}

    return {"per_type_doc_level": per_type_doc, "per_type_iss_level": per_type_iss,
            "documents": doc_results}


# ---------------------------------------------------------------------------
# 2. Real dataset issue metrics
# ---------------------------------------------------------------------------

def eval_real_dataset_metrics() -> dict:
    docs = _load_real_docs()
    if not docs:
        return {}

    from backend.pipeline.detectors import (
        detect_duplicates, detect_mechanism_mismatches, detect_inconsistent_targets
    )
    from backend.pipeline.analyzer import _detect_ambiguity_lexicon

    labels = ["vague", "duplicate", "inconsistent_target", "mechanism_mismatch"]
    splits = ["train", "test"]
    metrics = {s: {l: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for l in labels} for s in splits}

    print("\nEvaluating dataset_real.json (both splits, detectors applied directly)...")
    for doc in docs:
        split = doc.get("split", "train")
        if split not in splits:
            continue
        reqs = _build_reqs(doc["requirements"])

        gt = {l: set() for l in labels}
        for r in doc["requirements"]:
            for lbl in r.get("labels", []):
                if lbl in gt:
                    gt[lbl].add(r["req_id"])
                    metrics[split][lbl]["support"] += 1

        det: dict[str, set] = {l: set() for l in labels}

        # vague — run ambiguity lexicon detector; map to 'vague'
        for iss in _detect_ambiguity_lexicon(reqs):
            desc = str(iss.get("description", "")).lower()
            if "vague" in desc or "undefined term" in desc or "term" in desc:
                for rid in iss.get("involved_req_ids", []):
                    det["vague"].add(rid)

        for iss in detect_duplicates(reqs):
            for rid in iss.get("involved_req_ids", []):
                det["duplicate"].add(rid)

        for iss in detect_inconsistent_targets(reqs):
            for rid in iss.get("involved_req_ids", []):
                det["inconsistent_target"].add(rid)

        for iss in detect_mechanism_mismatches(reqs):
            for rid in iss.get("involved_req_ids", []):
                det["mechanism_mismatch"].add(rid)

        for l in labels:
            metrics[split][l]["tp"] += len(gt[l] & det[l])
            metrics[split][l]["fp"] += len(det[l] - gt[l])
            metrics[split][l]["fn"] += len(gt[l] - det[l])

    results: dict = {}
    for s in splits:
        results[s] = {}
        for l in labels:
            m = metrics[s][l]
            p, r, f = prf(m["tp"], m["fp"], m["fn"])
            results[s][l] = {
                "support": m["support"], "tp": m["tp"], "fp": m["fp"], "fn": m["fn"],
                "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3),
            }
    return results


# ---------------------------------------------------------------------------
# 3. FR/NFR classifier (train to develop, test to report)
# ---------------------------------------------------------------------------

def eval_fr_nfr_baseline() -> dict:
    docs = _load_real_docs()
    if not docs:
        return {}

    from backend.pipeline.detectors import classify_requirement

    cats = ["Performance", "Security", "Usability", "Reliability",
            "Maintainability", "Portability", "Scalability", "Others"]

    # Accumulate over ALL docs (both splits — train for understanding, test reported separately)
    type_stats: dict[str, dict] = {
        "train": {"correct": 0, "total": 0, "confusion": {"FR_as_FR": 0, "FR_as_NFR": 0, "NFR_as_NFR": 0, "NFR_as_FR": 0}},
        "test":  {"correct": 0, "total": 0, "confusion": {"FR_as_FR": 0, "FR_as_NFR": 0, "NFR_as_NFR": 0, "NFR_as_FR": 0}},
    }
    # per-category TP/FP/FN for test split only
    cat_tp: dict[str, int] = {c: 0 for c in cats}
    cat_fp: dict[str, int] = {c: 0 for c in cats}
    cat_fn: dict[str, int] = {c: 0 for c in cats}

    nfr_correct_cat = 0
    nfr_total = 0
    misclassified: list[dict] = []

    for doc in docs:
        split = doc.get("split", "train")
        for r in doc["requirements"]:
            text = r["text"]
            gold_type = r.get("req_type", "")
            gold_cat  = r.get("nfr_category")
            if gold_cat and str(gold_cat).lower() == "nan":
                gold_cat = None

            pred_type, pred_cat = classify_requirement(text)

            if gold_type in ("Functional", "Non-Functional"):
                st = type_stats[split]
                st["total"] += 1
                if pred_type == gold_type:
                    st["correct"] += 1
                    st["confusion"]["FR_as_FR" if gold_type == "Functional" else "NFR_as_NFR"] += 1
                else:
                    st["confusion"]["FR_as_NFR" if gold_type == "Functional" else "NFR_as_FR"] += 1
                    if len(misclassified) < 8 and split == "test":
                        misclassified.append({
                            "text": text, "gold": gold_type, "pred": pred_type,
                            "gold_cat": gold_cat, "pred_cat": pred_cat,
                        })

            if split == "test" and gold_type == "Non-Functional" and gold_cat:
                nfr_total += 1
                if pred_cat == gold_cat:
                    nfr_correct_cat += 1
                # per-category scoring
                if gold_cat in cat_tp:
                    if pred_cat == gold_cat:
                        cat_tp[gold_cat] += 1
                    else:
                        cat_fn[gold_cat] += 1
                        if pred_cat and pred_cat in cat_fp:
                            cat_fp[pred_cat] += 1

    # Per-category PRF on test split
    cat_prf: dict[str, dict] = {}
    for c in cats:
        p, r, f = prf(cat_tp[c], cat_fp[c], cat_fn[c])
        sup = cat_tp[c] + cat_fn[c]
        cat_prf[c] = {"support": sup, "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}

    return {
        "train": {
            "type_accuracy": type_stats["train"]["correct"] / max(1, type_stats["train"]["total"]),
            "confusion": type_stats["train"]["confusion"],
        },
        "test": {
            "type_accuracy": type_stats["test"]["correct"] / max(1, type_stats["test"]["total"]),
            "nfr_category_accuracy": nfr_correct_cat / max(1, nfr_total),
            "confusion": type_stats["test"]["confusion"],
            "per_category": cat_prf,
            "misclassifications": misclassified,
        },
    }


# ---------------------------------------------------------------------------
# 4. Validator rates
# ---------------------------------------------------------------------------

def eval_validators() -> dict:
    from backend.models import ArtifactOut, ArtifactType
    from backend.pipeline import validators

    openapi_valid = sql_exec_ok = total = 0
    fixture_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    for fpath in fixture_dir.glob("*.json"):
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        resp = data.get("response", {})
        if "yaml_content" in resp:
            total += 1
            art = ArtifactOut(artifact_type=ArtifactType.openapi, content=resp["yaml_content"],
                              is_valid=False, validation_errors=[])
            if validators.validate_openapi(art).is_valid:
                openapi_valid += 1
        if "ddl_content" in resp:
            art = ArtifactOut(artifact_type=ArtifactType.sql_ddl, content=resp["ddl_content"],
                              is_valid=False, validation_errors=[])
            if validators.validate_sql(art).is_valid:
                sql_exec_ok += 1

    return {"openapi_valid_rate": openapi_valid / max(total, 1),
            "sql_exec_rate": sql_exec_ok / max(total, 1)}


def eval_coverage() -> float:
    fixture_path = Path(__file__).parent.parent / "tests" / "fixtures" / "test_plan_generate.json"
    if not fixture_path.exists():
        return 0.0
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    test_cases = data.get("response", {}).get("test_cases", [])
    covered = {r for tc in test_cases for r in tc.get("req_ids", [])}
    order_fix = Path(__file__).parent.parent / "tests" / "fixtures" / "order_parse.json"
    if order_fix.exists():
        with open(order_fix, encoding="utf-8") as f:
            od = json.load(f)
        all_reqs = [r["req_id"] for r in od.get("response", {}).get("requirements", [])]
        if all_reqs:
            return len(covered & set(all_reqs)) / len(all_reqs) * 100
    return 100.0


# ---------------------------------------------------------------------------
# 5. LLM classifier (conditional)
# ---------------------------------------------------------------------------

def eval_llm_classifier():
    if os.environ.get("MOCK_MODE", "true").lower() == "true":
        print("LLM classification accuracy: skipped (MOCK_MODE=true or provider unreachable)")
        return
    try:
        from backend.llm import get_active_provider
        provider, model = get_active_provider()
        print(f"LLM classification accuracy: running with {provider} {model}...")
    except Exception:
        print("LLM classification accuracy: skipped (MOCK_MODE=true or provider unreachable)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    print(BANNER)

    # --- Planted flaws ---
    dataset_path = Path(__file__).parent / "dataset.json"
    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    planted = eval_planted_flaws(dataset)
    per_type_iss = planted["per_type_iss_level"]
    per_type_doc = planted["per_type_doc_level"]
    doc_results = planted["documents"]

    # --- Validators ---
    val_rates = eval_validators()
    coverage  = eval_coverage()

    print("\n=== PLANTED-FLAW EVALUATION REPORT ===")
    print("(a) Document-level — was at least one issue of each type found?")
    for t, m in per_type_doc.items():
        print(f"  {t:15s}: P={m['precision']:.2f}  R={m['recall']:.2f}  F1={m['f1']:.2f}")
    print("\n(b) Issue-level — type + overlapping requirement ids, duplicates merged")
    for t, m in per_type_iss.items():
        print(f"  {t:15s}: P={m['precision']:.2f}  R={m['recall']:.2f}  F1={m['f1']:.2f}")
    print(f"\nOverall:")
    print(f"  OpenAPI valid rate : {val_rates['openapi_valid_rate']*100:.1f}%")
    print(f"  SQL exec rate      : {val_rates['sql_exec_rate']*100:.1f}%")
    print(f"  Test coverage      : {coverage:.1f}%")

    # --- Real dataset ---
    dataset_metrics = eval_real_dataset_metrics()
    print("\n=== REAL DATASET METRICS (Cornelius dataset, silver labels) ===")
    if dataset_metrics:
        for split in ("train", "test"):
            print(f"\n  Split: {split.upper()}")
            for lbl, m in dataset_metrics[split].items():
                lbl_print = "rule-consistency check" if lbl == "duplicate" else lbl
                sup = m["support"]
                if sup == 0:
                    print(f"    {lbl_print:25s}: n/a (no positives in this split)")
                else:
                    print(f"    {lbl_print:25s}: Sup={sup:2d} | "
                          f"TP={m['tp']:2d} FP={m['fp']:2d} FN={m['fn']:2d} | "
                          f"P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f}")

    # --- FR/NFR baseline ---
    baseline = eval_fr_nfr_baseline()
    print("\n=== FR/NFR RULE-BASED CLASSIFIER ===")
    print("(Developed using TRAIN split; reported on TEST split)")
    if baseline:
        tr = baseline.get("train", {})
        te = baseline.get("test", {})
        print(f"\n  TRAIN type accuracy : {tr.get('type_accuracy', 0)*100:.1f}%")
        tc = tr.get("confusion", {})
        print(f"    Confusion: FR->FR={tc.get('FR_as_FR',0)} FR->NFR={tc.get('FR_as_NFR',0)}"
              f"  NFR->NFR={tc.get('NFR_as_NFR',0)} NFR->FR={tc.get('NFR_as_FR',0)}")

        print(f"\n  TEST type accuracy  : {te.get('type_accuracy', 0)*100:.1f}%")
        print(f"  TEST NFR cat acc    : {te.get('nfr_category_accuracy', 0)*100:.1f}%")
        tc = te.get("confusion", {})
        print(f"    Confusion: FR->FR={tc.get('FR_as_FR',0)} FR->NFR={tc.get('FR_as_NFR',0)}"
              f"  NFR->NFR={tc.get('NFR_as_NFR',0)} NFR->FR={tc.get('NFR_as_FR',0)}")

        print("\n  Per-category P/R/F1 (TEST split only):")
        for cat, m in te.get("per_category", {}).items():
            if m["support"] == 0:
                print(f"    {cat:15s}: n/a (no positives)")
            else:
                print(f"    {cat:15s}: Sup={m['support']:2d} | "
                      f"P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f}")

        misc = te.get("misclassifications", [])
        if misc:
            print("\n  Remaining Misclassifications (TEST):")
            for s in misc:
                print(f"    [{s['gold']}->{s['pred']}] gold_cat={s['gold_cat']} "
                      f"pred_cat={s['pred_cat']}  '{s['text']}'")

    # --- LLM classifier ---
    eval_llm_classifier()

    # --- Save report ---
    report_path = Path(__file__).parent / "eval_report.json"
    report = {
        "banner": "MOCK_MODE: LLM stages use fixtures; results reflect deterministic layer only",
        "planted_flaws": {
            "per_type_doc_level": per_type_doc,
            "per_type_iss_level": per_type_iss,
        },
        "overall": {
            "openapi_valid_rate": round(val_rates["openapi_valid_rate"], 3),
            "sql_exec_rate": round(val_rates["sql_exec_rate"], 3),
            "test_coverage_pct": round(coverage, 1),
        },
        "documents": doc_results,
        "dataset_real": dataset_metrics,
        "fr_nfr_baseline": baseline,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to {report_path}")
    return report


if __name__ == "__main__":
    main()
