"""
backend/pipeline/analyzer.py
Three detectors:
  a) Ambiguity: lexicon/regex + LLM context pass
  b) Conflict: Z3 SMT on numeric constraints + LLM semantic pass
  c) Completeness: entity checklist

Each Issue: id, type, severity, involved_req_ids, description, suggested_question, status
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from backend.llm import generate_json
from backend.models import (
    IssueOut,
    IssueStatus,
    IssueSeverity,
    IssueType,
    LLMIssue,
    LLMIssueList,
    ParseResult,
    ParsedRequirement,
)
from backend.pipeline.detectors import (
    detect_duplicates,
    detect_mechanism_mismatches,
    detect_inconsistent_targets,
    detect_z3_subsumptions,
)

# ---------------------------------------------------------------------------
# (a) Ambiguity — Lexicon / Regex pass
# ---------------------------------------------------------------------------

VAGUE_TERMS = [
    r"\bfast(ly)?\b", r"\bquickly?\b", r"\bsecure(ly)?\b", r"\bscalabl(e|y)\b",
    r"\buser.?friendly\b", r"\bappropriate(ly)?\b", r"\bas needed\b",
    r"\betc\.?\b", r"\bTBD\b", r"\bshould\b", r"\bmay\b",
    r"\band/or\b", r"\bmust not be unavailable\b",
    r"\bunreasonable\b", r"\breasonable\b", r"\bsoon\b", r"\btimely\b",
    r"\badequate(ly)?\b", r"\bsufficient(ly)?\b", r"\befficient(ly)?\b",
    r"\bflexible\b", r"\brobust\b", r"\bintuitive(ly)?\b",
]
_VAGUE_RE = re.compile("|".join(VAGUE_TERMS), re.IGNORECASE)

MODAL_WEAK = re.compile(r"\b(should|may|could|might|would)\b", re.IGNORECASE)
AND_OR = re.compile(r"\band/or\b", re.IGNORECASE)
DOUBLE_NEG = re.compile(
    r"\b(must not be unavailable|cannot be not|not without|never not)\b",
    re.IGNORECASE,
)


def _detect_ambiguity_lexicon(requirements: List[ParsedRequirement]) -> List[dict]:
    issues = []
    issue_counter = [0]

    def next_id() -> str:
        issue_counter[0] += 1
        return f"ISS-{issue_counter[0]:03d}"

    for req in requirements:
        text = req.text
        found_vague = _VAGUE_RE.search(text)
        found_double_neg = DOUBLE_NEG.search(text)
        found_and_or = AND_OR.search(text)

        if found_vague:
            term = found_vague.group()
            issues.append({
                "issue_id": next_id(),
                "issue_type": IssueType.ambiguity,
                "severity": IssueSeverity.blocking,
                "involved_req_ids": [req.req_id],
                "description": f"Vague/undefined term '{term}' in: {req.text[:80]}",
                "suggested_question": (
                    f"In requirement {req.req_id}, what does '{term}' mean specifically? "
                    "Please provide a measurable or concrete definition."
                ),
                "status": IssueStatus.open,
            })
        if found_double_neg:
            issues.append({
                "issue_id": next_id(),
                "issue_type": IssueType.ambiguity,
                "severity": IssueSeverity.blocking,
                "involved_req_ids": [req.req_id],
                "description": f"Double negation makes intent unclear: '{found_double_neg.group()}' in {req.req_id}",
                "suggested_question": (
                    f"In requirement {req.req_id}, please rephrase using a positive statement. "
                    "What should the system DO rather than NOT NOT do?"
                ),
                "status": IssueStatus.open,
            })
        if found_and_or and not found_vague:
            issues.append({
                "issue_id": next_id(),
                "issue_type": IssueType.ambiguity,
                "severity": IssueSeverity.warning,
                "involved_req_ids": [req.req_id],
                "description": f"'and/or' is ambiguous: is it both OR either? In {req.req_id}",
                "suggested_question": (
                    f"In requirement {req.req_id}, does 'and/or' mean BOTH must be true, "
                    "or just one of them? Please clarify."
                ),
                "status": IssueStatus.open,
            })
    return issues


# ---------------------------------------------------------------------------
# (b) Conflict — Z3 SMT pass
# ---------------------------------------------------------------------------

def _detect_conflicts_z3(requirements: List[ParsedRequirement]) -> List[dict]:
    """
    Group constraints by (subject, attribute) and use Z3 to detect unsat pairs.
    """
    issues = []
    issue_counter = [0]

    def next_id() -> str:
        issue_counter[0] += 1
        return f"ISS-Z-{issue_counter[0]:03d}"

    try:
        import z3
    except ImportError:
        return []

    # Group by (subject, attribute)
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for req in requirements:
        for c in req.constraints:
            key = (c.subject.lower(), c.attribute.lower())
            groups[key].append((req.req_id, c))

    for (subject, attribute), items in groups.items():
        if len(items) < 2:
            continue

        # Try pairs for contradiction
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                req_id_i, c_i = items[i]
                req_id_j, c_j = items[j]

                try:
                    val_i = float(c_i.value)
                    val_j = float(c_j.value)
                except (TypeError, ValueError):
                    # Non-numeric: compare equality constraints
                    if c_i.op == "==" and c_j.op == "==" and c_i.value != c_j.value:
                        issues.append({
                            "issue_id": next_id(),
                            "issue_type": IssueType.conflict,
                            "severity": IssueSeverity.blocking,
                            "involved_req_ids": [req_id_i, req_id_j],
                            "description": (
                                f"Conflicting values for {subject}.{attribute}: "
                                f"{req_id_i} requires '{c_i.value}' but {req_id_j} requires '{c_j.value}'"
                            ),
                            "suggested_question": (
                                f"Requirements {req_id_i} and {req_id_j} set conflicting values "
                                f"for {subject}.{attribute}. Which value should take precedence, "
                                "or should the system handle both cases?"
                            ),
                            "status": IssueStatus.open,
                        })
                    continue

                x = z3.Real(f"{subject}_{attribute}")
                s = z3.Solver()

                op_map = {
                    "==": lambda a, b: a == b,
                    "!=": lambda a, b: a != b,
                    "<":  lambda a, b: a < b,
                    "<=": lambda a, b: a <= b,
                    ">":  lambda a, b: a > b,
                    ">=": lambda a, b: a >= b,
                }
                try:
                    cond_i = op_map[c_i.op](x, val_i)
                    cond_j = op_map[c_j.op](x, val_j)
                    s.add(cond_i, cond_j)
                    result = s.check()
                    if result == z3.unsat:
                        issues.append({
                            "issue_id": next_id(),
                            "issue_type": IssueType.conflict,
                            "severity": IssueSeverity.blocking,
                            "involved_req_ids": [req_id_i, req_id_j],
                            "description": (
                                f"Z3 detected contradiction on {subject}.{attribute}: "
                                f"{req_id_i} says {c_i.op} {val_i}, "
                                f"{req_id_j} says {c_j.op} {val_j} — unsatisfiable simultaneously."
                            ),
                            "suggested_question": (
                                f"Requirements {req_id_i} and {req_id_j} impose contradictory "
                                f"constraints on {subject}.{attribute}. Please clarify which rule "
                                "takes precedence or provide an exception condition."
                            ),
                            "status": IssueStatus.open,
                        })
                except Exception:
                    pass

    return issues


# ---------------------------------------------------------------------------
# (b) Conflict — LLM semantic pass
# ---------------------------------------------------------------------------

CONFLICT_LLM_PROMPT = """
You are a requirements analyst. Review the following requirements and detect SEMANTIC
conflicts that logic/math alone cannot catch. Focus on:
- Business rule contradictions (e.g., "email must be globally unique" vs "family members share email")
- Mutually exclusive states
- Permission conflicts

Requirements:
{reqs_json}

Return ONLY valid JSON with this structure:
{{
  "issues": [
    {{
      "issue_id": "ISS-L-001",
      "issue_type": "conflict",
      "severity": "blocking",
      "involved_req_ids": ["REQ-001", "REQ-002"],
      "description": "...",
      "suggested_question": "..."
    }}
  ]
}}
If no semantic conflicts found, return {{"issues": []}}.
Keep your response compact. Maximum 3 issues.
"""


def _detect_conflicts_llm(requirements: List[ParsedRequirement]) -> List[dict]:
    reqs_simple = [
        {"id": r.req_id, "text": r.text} for r in requirements
    ]
    prompt = CONFLICT_LLM_PROMPT.format(reqs_json=json.dumps(reqs_simple, indent=2))
    result = generate_json(prompt, LLMIssueList)
    return [i.model_dump() for i in result.issues]


# ---------------------------------------------------------------------------
# (c) Completeness — checklist
# ---------------------------------------------------------------------------

COMPLETENESS_CHECKLIST = [
    # (area, presence_pattern, trigger_pattern)
    ("auth", r"\b(login|auth|authenticat|token|session|permission|role|access)\b", r"\b(users?|accounts?|admins?|customers?|patients?|students?|portals?)\b"),
    ("validation_limits", r"\b(validat|limit|max|min|length|size|format|constraint)\b", r"\b(inputs?|forms?|uploads?|passwords?|amounts?|prices?|dates?|emails?)\b"),
    ("error_cases", r"\b(error|fail|exception|invalid|reject|not found|404|500)\b", r"\b(apis?|endpoints?|requests?|transactions?|payments?|submits?|process)\b"),
    ("delete_retention", r"\b(delet|remov|retain|archive|purge|expir)\b", r"\b(data|records?|accounts?|history|logs?|files?|images?)\b"),
    ("boundary", r"\b(boundary|edge case|overflow|zero|empty|null)\b", r"\b(calculate|compute|aggregate|sum|average|discount|tax)\b"),
]

def _detect_completeness(requirements: List[ParsedRequirement]) -> List[dict]:
    """Check each entity group for missing specification areas based on triggers."""
    issues = []
    issue_counter = [0]

    def next_id() -> str:
        issue_counter[0] += 1
        return f"ISS-C-{issue_counter[0]:03d}"

    all_text = " ".join(r.text for r in requirements).lower()
    
    # We want to associate the issue with the specific requirement that triggered it
    for area, presence_pat, trigger_pat in COMPLETENESS_CHECKLIST:
        if not re.search(presence_pat, all_text, re.IGNORECASE):
            # Find which requirements activated the trigger
            triggered_reqs = []
            for r in requirements:
                if re.search(trigger_pat, r.text, re.IGNORECASE):
                    triggered_reqs.append(r.req_id)
            
            if triggered_reqs:
                questions = {
                    "auth": "Are there authentication and authorization requirements? Who can access what?",
                    "validation_limits": "What are the validation rules and limits for inputs? (length, format, range)",
                    "error_cases": "What should happen on errors, invalid input, or system failure?",
                    "delete_retention": "What are the data deletion and retention policies?",
                    "boundary": "Are boundary/edge cases specified? (empty inputs, maximum values, etc.)",
                }
                issues.append({
                    "issue_id": next_id(),
                    "issue_type": IssueType.incompleteness,
                    "severity": IssueSeverity.warning,
                    "involved_req_ids": triggered_reqs[:3],  # Cap to top 3 relevant
                    "description": f"Missing '{area}' requirements for mentioned entities.",
                    "suggested_question": questions.get(area, f"Please specify requirements for {area}."),
                    "status": IssueStatus.open,
                })

    return issues


# ---------------------------------------------------------------------------
# (a) Ambiguity — LLM context pass
# ---------------------------------------------------------------------------

AMBIGUITY_LLM_PROMPT = """
You are a requirements analyst. Review the following requirements for CONTEXT-DEPENDENT
ambiguity that simple pattern matching misses. Look for:
- Unclear pronoun references ("it", "they", "this" without clear antecedent)
- Scope ambiguity with "and/or"
- Negation that is hard to interpret ("users cannot not log in weekly")
- Terms that mean different things in different contexts

Requirements:
{reqs_json}

Return ONLY valid JSON:
{{
  "issues": [
    {{
      "issue_id": "ISS-A-001",
      "issue_type": "ambiguity",
      "severity": "blocking",
      "involved_req_ids": ["REQ-001"],
      "description": "...",
      "suggested_question": "..."
    }}
  ]
}}
If no issues, return {{"issues": []}}.
Keep compact. Maximum 5 issues.
"""


def _detect_ambiguity_llm(requirements: List[ParsedRequirement]) -> List[dict]:
    reqs_simple = [{"id": r.req_id, "text": r.text} for r in requirements]
    prompt = AMBIGUITY_LLM_PROMPT.format(reqs_json=json.dumps(reqs_simple, indent=2))
    result = generate_json(prompt, LLMIssueList)
    return [i.model_dump() for i in result.issues]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _dedup_issues(issues: List[dict]) -> List[dict]:
    """Remove near-duplicate issues (same type + same req_ids)."""
    seen: set = set()
    out = []
    for iss in issues:
        key = (iss["issue_type"], frozenset(iss.get("involved_req_ids", [])), iss.get("description", "")[:60])
        if key not in seen:
            seen.add(key)
            out.append(iss)
    return out


def analyze(parse_result: ParseResult) -> List[IssueOut]:
    """
    Run all three detectors. Returns deduplicated list of IssueOut.
    """
    requirements = parse_result.requirements
    all_issues: List[dict] = []

    # (a) Ambiguity
    all_issues.extend(_detect_ambiguity_lexicon(requirements))
    all_issues.extend(_detect_ambiguity_llm(requirements))

    # (b) Conflict — Z3 hard contradictions (blocking)
    all_issues.extend(_detect_conflicts_z3(requirements))
    # (b) Conflict — Z3 subsumptions / inconsistent targets (warning)
    all_issues.extend(detect_z3_subsumptions(requirements))
    # (b) Conflict — LLM semantic pass
    all_issues.extend(_detect_conflicts_llm(requirements))

    # (b) Conflict — deterministic duplicate detection (warning)
    all_issues.extend(detect_duplicates(requirements))
    # (b) Conflict — inconsistent metric targets (warning)
    all_issues.extend(detect_inconsistent_targets(requirements))

    # (a) Ambiguity — mechanism mismatch for security statements (blocking)
    all_issues.extend(detect_mechanism_mismatches(requirements))

    # (c) Completeness
    all_issues.extend(_detect_completeness(requirements))

    all_issues = _dedup_issues(all_issues)

    # Re-number consistently
    result = []
    for i, iss in enumerate(all_issues, start=1):
        iss = dict(iss)
        iss["issue_id"] = f"ISS-{i:03d}"
        if isinstance(iss.get("issue_type"), str):
            iss["issue_type"] = IssueType(iss["issue_type"])
        if isinstance(iss.get("severity"), str):
            iss["severity"] = IssueSeverity(iss["severity"])
        if isinstance(iss.get("status"), str):
            iss["status"] = IssueStatus(iss["status"])
        elif "status" not in iss or iss["status"] is None:
            iss["status"] = IssueStatus.open
        result.append(IssueOut(**iss))

    return result
