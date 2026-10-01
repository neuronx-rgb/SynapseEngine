"""
backend/pipeline/detectors.py
Deterministic detectors (no LLM required):
  - Duplicate detection (normalized text)
  - Mechanism mismatch rules for security statements
  - Z3 subsumption / inconsistent-target detection (extends existing Z3 logic)
  - Inconsistent target detector (same metric, different values in one project)
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import List

from backend.models import (
    IssueOut,
    IssueStatus,
    IssueSeverity,
    IssueType,
    ParsedRequirement,
)


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip punctuation/extra spaces, NFD normalize."""
    text = unicodedata.normalize("NFD", text.lower())
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# 1. Duplicate detector
# ---------------------------------------------------------------------------

def detect_duplicates(requirements: List[ParsedRequirement]) -> List[dict]:
    """
    Flag pairs of requirements whose normalized descriptions are identical.
    Returns list of issue dicts (conflict/warning).
    """
    issues = []
    seen: dict[str, str] = {}  # normalized_text -> first req_id

    for req in requirements:
        norm = _normalize(req.text)
        if norm in seen:
            issues.append({
                "issue_id": f"DUP-{len(issues)+1:03d}",
                "issue_type": IssueType.conflict,
                "severity": IssueSeverity.warning,
                "involved_req_ids": [seen[norm], req.req_id],
                "description": (
                    f"Duplicate requirement: {req.req_id} has identical normalized text "
                    f"as {seen[norm]}: '{req.text[:80]}'"
                ),
                "suggested_question": (
                    f"Requirements {seen[norm]} and {req.req_id} appear identical. "
                    "Are they truly the same? If so, please remove the duplicate."
                ),
                "status": IssueStatus.open,
            })
        else:
            seen[norm] = req.req_id

    return issues


# ---------------------------------------------------------------------------
# 2. Mechanism mismatch detector
# ---------------------------------------------------------------------------

# (mechanism_verb_pattern, wrong_technology_pattern, explanation)
MISMATCH_RULES: List[tuple[str, str, str]] = [
    (
        r"\bencrypt\w*\b",
        r"\b(RBAC|OAuth|JWT|OpenID)\b",
        "Encryption is a data-security mechanism; RBAC/OAuth/JWT are authorization/authentication protocols — not encryption algorithms.",
    ),
    (
        r"\bauthenticat\w*\b",
        r"\b(AES|RSA|3DES|Blowfish)\b",
        "Authentication protocols should use mechanisms like OAuth, JWT, or MFA — not symmetric/asymmetric encryption ciphers.",
    ),
    (
        r"\baccess\s+control\b",
        r"\b(AES|RSA|SSL[-/]?TLS|TLS)\b",
        "Access control uses RBAC, ABAC, or ACL mechanisms — not encryption algorithms or transport-layer security.",
    ),
    (
        r"\bauthori[sz]e?\w*\b",
        r"\b(MD5|SHA-?\d*|bcrypt|scrypt)\b",
        "Authorization logic should not be conflated with hashing algorithms (MD5/SHA/bcrypt are for password storage, not authorization).",
    ),
]

_COMPILED_RULES = [
    (re.compile(verb, re.I), re.compile(tech, re.I), explanation)
    for verb, tech, explanation in MISMATCH_RULES
]


def detect_mechanism_mismatches(requirements: List[ParsedRequirement]) -> List[dict]:
    """
    Flag security statements that mix incompatible mechanisms.
    Returns list of issue dicts (ambiguity/blocking).
    """
    issues = []

    for req in requirements:
        text = req.text
        for verb_re, tech_re, explanation in _COMPILED_RULES:
            v_match = verb_re.search(text)
            t_match = tech_re.search(text)
            if v_match and t_match:
                issues.append({
                    "issue_id": f"MM-{len(issues)+1:03d}",
                    "issue_type": IssueType.ambiguity,
                    "severity": IssueSeverity.blocking,
                    "involved_req_ids": [req.req_id],
                    "description": (
                        f"Mechanism mismatch in {req.req_id}: "
                        f"'{v_match.group()}' combined with '{t_match.group()}'. "
                        f"{explanation}"
                    ),
                    "suggested_question": (
                        f"In {req.req_id}, did you mean to use '{t_match.group()}' for "
                        f"{v_match.group()}? Please specify the correct security mechanism "
                        "(e.g., use AES-256 for encryption, OAuth 2.0 for authorization)."
                    ),
                    "status": IssueStatus.open,
                })

    return issues


# ---------------------------------------------------------------------------
# 3. Inconsistent target detector (same metric, different values)
# ---------------------------------------------------------------------------

# (metric_label, regex_pattern with one capture group for the numeric value)
METRIC_PATTERNS: List[tuple[str, re.Pattern]] = [
    ("page_load_seconds",    re.compile(r"(?:page\s+load|load\s+time).*?(\d+(?:\.\d+)?)\s*(?:s|sec|second)", re.I)),
    ("response_time_seconds",re.compile(r"response\s+time.*?(\d+(?:\.\d+)?)\s*(?:ms|millisecond|s|sec)", re.I)),
    ("concurrent_users",     re.compile(r"(\d[\d,]*)\s*concurrent\s+(?:users?|session)", re.I)),
    ("uptime_percent",       re.compile(r"uptime.*?(\d+(?:\.\d+)?)\s*%", re.I)),
    ("availability_percent", re.compile(r"availability.*?(\d+(?:\.\d+)?)\s*%", re.I)),
    ("backup_interval_hours",re.compile(r"backup.*?(?:every|interval).*?(\d+(?:\.\d+)?)\s*(?:h|hour|hr)", re.I)),
    ("password_length",      re.compile(r"password.*?(?:min|minimum|at\s+least).*?(\d+)\s*char", re.I)),
    ("session_timeout_min",  re.compile(r"session.*?timeout.*?(\d+(?:\.\d+)?)\s*(?:min|minute)", re.I)),
]


def detect_inconsistent_targets(requirements: List[ParsedRequirement]) -> List[dict]:
    """
    Find cases where the same metric appears with different numeric values
    across requirements in the same document. Returns warning-level issues.
    """
    issues = []

    # metric -> list of (req_id, value_str)
    metric_hits: dict[str, list] = defaultdict(list)

    for req in requirements:
        for metric_label, pattern in METRIC_PATTERNS:
            m = pattern.search(req.text)
            if m:
                val = m.group(1).replace(",", "")
                metric_hits[metric_label].append((req.req_id, val))

    for metric, hits in metric_hits.items():
        if len(hits) < 2:
            continue
        values = [h[1] for h in hits]
        unique_vals = set(values)
        if len(unique_vals) > 1:
            req_ids = [h[0] for h in hits]
            val_map = ", ".join(f"{rid}={val}" for rid, val in hits)
            issues.append({
                "issue_id": f"IT-{len(issues)+1:03d}",
                "issue_type": IssueType.conflict,
                "severity": IssueSeverity.warning,
                "involved_req_ids": req_ids,
                "description": (
                    f"Inconsistent target for '{metric}': different values found — {val_map}. "
                    "Which value is the intended specification?"
                ),
                "suggested_question": (
                    f"Requirements {', '.join(req_ids)} specify different values for {metric}. "
                    f"Values found: {', '.join(sorted(unique_vals))}. "
                    "Please confirm the correct target value."
                ),
                "status": IssueStatus.open,
            })

    return issues


# ---------------------------------------------------------------------------
# 4. Z3 subsumption / redundant threshold detector
# ---------------------------------------------------------------------------

def detect_z3_subsumptions(requirements: List[ParsedRequirement]) -> List[dict]:
    """
    Extend Z3 logic to also flag:
    (b) Subsumed/redundant thresholds (e.g., 'within 2s' subsumes 'within 10s' — warning)
    (c) Inconsistent same-metric constraints (warning, not necessarily unsat)

    Complements (not replaces) the existing _detect_conflicts_z3 in analyzer.py.
    """
    issues = []
    issue_counter = [0]

    def next_id() -> str:
        issue_counter[0] += 1
        return f"ISS-SUB-{issue_counter[0]:03d}"

    try:
        import z3
    except ImportError:
        return []

    groups: dict[tuple, list] = defaultdict(list)
    for req in requirements:
        for c in req.constraints:
            key = (c.subject.lower(), c.attribute.lower())
            groups[key].append((req.req_id, c))

    for (subject, attribute), items in groups.items():
        if len(items) < 2:
            continue

        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                req_id_i, c_i = items[i]
                req_id_j, c_j = items[j]

                try:
                    val_i = float(c_i.value)
                    val_j = float(c_j.value)
                except (TypeError, ValueError):
                    continue

                # Check subsumption: one constraint makes the other redundant
                # e.g., x <= 2 subsumes x <= 10 (stricter includes looser)
                x = z3.Real(f"{subject}_{attribute}")
                s_sub = z3.Solver()

                op_map = {
                    "==": lambda a, b: a == b,
                    "!=": lambda a, b: a != b,
                    "<":  lambda a, b: a < b,
                    "<=": lambda a, b: a <= b,
                    ">":  lambda a, b: a > b,
                    ">=": lambda a, b: a >= b,
                }

                try:
                    ci_expr = op_map[c_i.op](x, val_i)
                    cj_expr = op_map[c_j.op](x, val_j)

                    # Test if ci_expr => cj_expr (ci subsumes cj)
                    s_sub.add(z3.And(ci_expr, z3.Not(cj_expr)))
                    if s_sub.check() == z3.unsat:
                        # ci is strictly stronger — cj is redundant
                        issues.append({
                            "issue_id": next_id(),
                            "issue_type": IssueType.conflict,
                            "severity": IssueSeverity.warning,
                            "involved_req_ids": [req_id_i, req_id_j],
                            "description": (
                                f"Redundant threshold on {subject}.{attribute}: "
                                f"{req_id_i} ({c_i.op} {val_i}) is stricter than "
                                f"{req_id_j} ({c_j.op} {val_j}) — the latter is subsumed."
                            ),
                            "suggested_question": (
                                f"Requirements {req_id_i} and {req_id_j} both constrain "
                                f"{subject}.{attribute}, but {req_id_i} is stricter. "
                                "Is the looser constraint intentionally redundant, or should it be removed?"
                            ),
                            "status": IssueStatus.open,
                        })
                    else:
                        # Different values for same metric without contradiction — inconsistent target
                        if c_i.op == c_j.op and val_i != val_j:
                            issues.append({
                                "issue_id": next_id(),
                                "issue_type": IssueType.conflict,
                                "severity": IssueSeverity.warning,
                                "involved_req_ids": [req_id_i, req_id_j],
                                "description": (
                                    f"Inconsistent target for {subject}.{attribute}: "
                                    f"{req_id_i} specifies {c_i.op} {val_i}, "
                                    f"but {req_id_j} specifies {c_j.op} {val_j}. "
                                    "Which is the intended value?"
                                ),
                                "suggested_question": (
                                    f"Requirements {req_id_i} and {req_id_j} specify "
                                    f"different values ({val_i} vs {val_j}) for "
                                    f"{subject}.{attribute}. Please confirm the correct target."
                                ),
                                "status": IssueStatus.open,
                            })
                except Exception:
                    continue

    return issues


# ---------------------------------------------------------------------------
# FR/NFR rule-based classifier (offline, no LLM)
# Rules developed on TRAIN split; evaluated on TEST split only.
# ---------------------------------------------------------------------------

# Order matters: more specific patterns first to avoid false category assignment.
# Each entry: (category_label, compiled_regex)
NFR_CATEGORY_RULES: List[tuple[str, re.Pattern]] = [
    # Reliability — errors, failures, recovery (must come before Usability/Portability)
    ("Reliability",
     re.compile(
         r"\b(uptime|availability|failover|backup|recover\w*|fault\s+toleran|redundan|disaster"
         r"|handle\s+errors?|gracefully|error\s+recovery|failure\s+recovery|mean\s+time"
         r"|mttr|mtbf)\b",
         re.I,
     )),
    # Performance — numeric thresholds, timing, throughput
    ("Performance",
     re.compile(
         r"\b(load\s+time|page\s+load|latency|response\s+time|respond\s+within|throughput"
         r"|millisecond|tps|queries\s+per\s+second|req/s)\b"
         r"|\b\d+\s*(?:ms|sec(?:ond)?s?|minute|hour)\b"
         r"|\b\d+(?:\.\d+)?\s*%(?!\s*(?:of|for|in))",
         re.I,
     )),
    # Security — encryption, auth, access control, audit trails, logs
    ("Security",
     re.compile(
         r"\b(encrypt\w*|authenticat\w*|access\s+control|audit\s+trail|audit\s+log"
         r"|security\s+event|log\s+all|authoriz\w*|password|RBAC|OAuth|JWT|firewall"
         r"|SSL|TLS|XSS|CSRF|sql\s+injection|penetration|vulnerability)\b",
         re.I,
     )),
    # Usability — UX, clarity, actionable messages
    ("Usability",
     re.compile(
         r"\b(user.?friendly|intuitive|easy\s+to\s+use|easy\s+to\s+navigate|accessible"
         r"|WCAG|screen\s+reader|clear\s+and\s+actionable|clear\s+error|error\s+message"
         r"|help\s+documentation|tool\s+tip|onboarding)\b",
         re.I,
     )),
    # Maintainability — diagnostics, modular design, configuration, updates
    ("Maintainability",
     re.compile(
         r"\b(maintain\w*|modular|document\w*|diagnostic\w*|configuration|configurable"
         r"|refactor|technical\s+debt|code\s+review|update\s+mechanism|patch|hotfix)\b",
         re.I,
     )),
    # Portability — operating systems, platforms, browsers, devices
    ("Portability",
     re.compile(
         r"\b(portable|cross.?platform|multiple\s+(?:operating\s+systems?|platforms?|browsers?|devices?)"
         r"|operating\s+system|Android|iOS|Windows|Linux|macOS|Docker|container|deploy\w*)\b",
         re.I,
     )),
    # Scalability — concurrency, elastic scaling
    ("Scalability",
     re.compile(
         r"\b(concurrent\s+users?|scalab\w*|load\s+balanc|horizontal\s+scal|vertical\s+scal"
         r"|elastic|auto.?scal|peak\s+load)\b",
         re.I,
     )),
    # Others — audit trails, logs (catch-all for remaining NFR signals)
    ("Others",
     re.compile(
         r"\b(audit\s+trail|audit\s+log|activity\s+log|event\s+log|system\s+log|logging"
         r"|traceability|compliance|regulatory|SLA|service\s+level\s+agreement)\b",
         re.I,
     )),
]

# Functional signals — positive indicators of functional requirements
FR_SIGNALS = re.compile(
    r"\b(shall\s+be\s+able\s+to|shall\s+allow\s+users?\s+to|shall\s+support\s+\w"
    r"|shall\s+provide\s+functionality|shall\s+enable|shall\s+generate|shall\s+process"
    r"|shall\s+calculate|shall\s+display|shall\s+notify|shall\s+send|shall\s+receive"
    r"|shall\s+store|shall\s+retrieve|shall\s+update|shall\s+delete|shall\s+validate)\b",
    re.I,
)


def classify_requirement(text: str) -> tuple[str, str | None]:
    """
    Rule-based FR/NFR classifier.
    Returns (Requirement_Type, NFR_Category_or_None).
    NFR patterns are checked first; functional signals are a fallback.
    """
    # 1. Check NFR category patterns first (in priority order)
    for category, pattern in NFR_CATEGORY_RULES:
        if pattern.search(text):
            return "Non-Functional", category

    # 2. Functional signals → definitively functional
    if FR_SIGNALS.search(text):
        return "Functional", None

    # 3. Default to Functional
    return "Functional", None
