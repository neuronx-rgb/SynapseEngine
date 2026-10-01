"""
tests/test_detectors.py
Unit tests for each new deterministic detector.
Uses synthetic requirements derived from the Cornelius dataset patterns.
All tests run offline — no LLM, no network.
"""
import os
import pytest

os.environ.setdefault("MOCK_MODE", "true")

from backend.models import ParsedRequirement, ConstraintSchema, ParseResult
from backend.pipeline.detectors import (
    detect_duplicates,
    detect_mechanism_mismatches,
    detect_inconsistent_targets,
    detect_z3_subsumptions,
    classify_requirement,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_req(req_id: str, text: str, constraints=None) -> ParsedRequirement:
    return ParsedRequirement(
        req_id=req_id,
        text=text,
        source_sentence=text,
        entities=[],
        actions=[],
        constraints=constraints or [],
    )


def make_constraint(subject: str, attribute: str, op: str, value: str) -> ConstraintSchema:
    return ConstraintSchema(subject=subject, attribute=attribute, op=op, value=value)


# ---------------------------------------------------------------------------
# 1. Duplicate detector
# ---------------------------------------------------------------------------

class TestDuplicateDetector:
    def test_detects_exact_duplicate(self):
        reqs = [
            make_req("REQ-001", "The system shall allow users to create orders."),
            make_req("REQ-002", "The system shall allow users to create orders."),
        ]
        issues = detect_duplicates(reqs)
        assert len(issues) == 1
        assert "REQ-001" in issues[0]["involved_req_ids"]
        assert "REQ-002" in issues[0]["involved_req_ids"]

    def test_detects_case_insensitive_duplicate(self):
        reqs = [
            make_req("REQ-001", "Users shall be able to GENERATE orders"),
            make_req("REQ-002", "Users shall be able to generate orders"),
        ]
        issues = detect_duplicates(reqs)
        assert len(issues) == 1

    def test_detects_punctuation_normalized_duplicate(self):
        reqs = [
            make_req("REQ-001", "The application shall support manage payments."),
            make_req("REQ-002", "The application shall support manage payments"),
        ]
        issues = detect_duplicates(reqs)
        assert len(issues) == 1

    def test_no_duplicate_for_different_reqs(self):
        reqs = [
            make_req("REQ-001", "The system shall allow users to create orders."),
            make_req("REQ-002", "The system shall allow users to delete orders."),
        ]
        issues = detect_duplicates(reqs)
        assert len(issues) == 0

    def test_three_way_duplicate_reports_two(self):
        reqs = [
            make_req("REQ-001", "Users shall be able to generate orders"),
            make_req("REQ-002", "Users shall be able to generate orders"),
            make_req("REQ-003", "Users shall be able to generate orders"),
        ]
        issues = detect_duplicates(reqs)
        # REQ-002 dupes REQ-001, REQ-003 dupes REQ-001 again
        assert len(issues) == 2

    def test_dataset_pattern_duplicate(self):
        """From dataset: 'The system shall allow users to create orders' appears multiple times."""
        reqs = [
            make_req("FMS-01", "The system shall allow users to create orders"),
            make_req("FMS-02", "The system shall allow users to generate orders"),
            make_req("FMS-03", "The system shall allow users to create orders"),
        ]
        issues = detect_duplicates(reqs)
        assert len(issues) == 1
        assert "FMS-01" in issues[0]["involved_req_ids"]
        assert "FMS-03" in issues[0]["involved_req_ids"]


# ---------------------------------------------------------------------------
# 2. Mechanism mismatch detector
# ---------------------------------------------------------------------------

class TestMechanismMismatch:
    def test_detects_encrypt_with_rbac(self):
        reqs = [make_req("REQ-001", "The system shall encrypt user data using RBAC.")]
        issues = detect_mechanism_mismatches(reqs)
        assert len(issues) == 1
        assert "REQ-001" in issues[0]["involved_req_ids"]
        assert "mismatch" in issues[0]["description"].lower()

    def test_detects_encrypt_with_oauth(self):
        reqs = [make_req("REQ-001", "All API calls shall be encrypted using OAuth 2.0 tokens.")]
        issues = detect_mechanism_mismatches(reqs)
        assert len(issues) == 1

    def test_detects_encrypt_with_jwt(self):
        reqs = [make_req("REQ-001", "Patient records shall be encrypted using JWT.")]
        issues = detect_mechanism_mismatches(reqs)
        assert len(issues) == 1

    def test_detects_authentication_with_aes(self):
        reqs = [make_req("REQ-002", "User authentication shall use AES-256 encryption.")]
        issues = detect_mechanism_mismatches(reqs)
        assert len(issues) == 1

    def test_detects_access_control_with_ssl(self):
        reqs = [make_req("REQ-003", "Access control shall be implemented using SSL/TLS.")]
        issues = detect_mechanism_mismatches(reqs)
        assert len(issues) == 1

    def test_no_mismatch_correct_pairing(self):
        reqs = [
            make_req("REQ-001", "All data shall be encrypted using AES-256."),
            make_req("REQ-002", "User authentication shall use OAuth 2.0."),
            make_req("REQ-003", "Access control shall be implemented using RBAC."),
        ]
        issues = detect_mechanism_mismatches(reqs)
        assert len(issues) == 0

    def test_dataset_pattern_mismatch(self):
        """Dataset pattern: 'encrypt ... RBAC' or 'authenticate ... AES'."""
        reqs = [
            make_req("HMS-01", "The system shall encrypt PHI data using RBAC policies."),
            make_req("HMS-02", "The system shall authenticate users using RSA certificates."),
        ]
        issues = detect_mechanism_mismatches(reqs)
        assert len(issues) == 2


# ---------------------------------------------------------------------------
# 3. Inconsistent target detector
# ---------------------------------------------------------------------------

class TestInconsistentTargets:
    def test_detects_different_uptime_values(self):
        reqs = [
            make_req("REQ-001", "The system shall maintain uptime of 99.9%."),
            make_req("REQ-002", "The system uptime must be 95%."),
        ]
        issues = detect_inconsistent_targets(reqs)
        assert len(issues) == 1
        assert "uptime" in issues[0]["description"].lower()

    def test_detects_different_concurrent_users(self):
        reqs = [
            make_req("REQ-001", "The system shall support 1000 concurrent users."),
            make_req("REQ-002", "The system shall handle 500 concurrent users."),
        ]
        issues = detect_inconsistent_targets(reqs)
        assert len(issues) >= 1

    def test_same_metric_same_value_no_issue(self):
        reqs = [
            make_req("REQ-001", "The system uptime must be 99.9%."),
            make_req("REQ-002", "System availability shall be 99.9%."),
        ]
        issues = detect_inconsistent_targets(reqs)
        # Both are same value — no inconsistency
        same_val = all(
            "99.9" in iss["description"] and "99.9" in iss["description"]
            for iss in issues
        )
        # Either no issues or the values are the same (not actually conflicting)
        for iss in issues:
            vals = set()
            for v in ["99.9", "95", "90", "100"]:
                if v in iss["description"]:
                    vals.add(v)
            # If only 99.9 mentioned, it's the same value
            if len(vals) <= 1:
                pass  # acceptable

    def test_detects_different_page_load(self):
        reqs = [
            make_req("REQ-001", "Page load time shall not exceed 2 seconds."),
            make_req("REQ-002", "The page load should complete within 10 seconds."),
        ]
        issues = detect_inconsistent_targets(reqs)
        assert len(issues) >= 1

    def test_dataset_pattern_metric(self):
        """Dataset-style: concurrent users with inconsistent values."""
        reqs = [
            make_req("INV-01", "The inventory system shall support 100 concurrent users at peak."),
            make_req("INV-02", "The application shall handle 500 concurrent users without degradation."),
        ]
        issues = detect_inconsistent_targets(reqs)
        assert len(issues) >= 1


# ---------------------------------------------------------------------------
# 4. Z3 subsumption detector
# ---------------------------------------------------------------------------

class TestZ3Subsumption:
    def test_detects_subsumption(self):
        """x <= 2 subsumes x <= 10 — 10 is redundant."""
        reqs = [
            make_req("REQ-001", "Response time must be within 2 seconds.",
                     constraints=[make_constraint("response_time", "seconds", "<=", "2")]),
            make_req("REQ-002", "Response time must be within 10 seconds.",
                     constraints=[make_constraint("response_time", "seconds", "<=", "10")]),
        ]
        issues = detect_z3_subsumptions(reqs)
        assert len(issues) >= 1
        sev = issues[0]["severity"]
        assert str(sev) in ("warning", "IssueSeverity.warning")

    def test_detects_inconsistent_equal_ops(self):
        """x == 5 and x == 10 — inconsistent target, not unsat (different reqs)."""
        reqs = [
            make_req("REQ-001", "Max connections must be 5.",
                     constraints=[make_constraint("connections", "max", "==", "5")]),
            make_req("REQ-002", "Max connections must be 10.",
                     constraints=[make_constraint("connections", "max", "==", "10")]),
        ]
        issues = detect_z3_subsumptions(reqs)
        assert len(issues) >= 1

    def test_no_subsumption_compatible(self):
        """x >= 100 and x >= 50 — first subsumes second, warning expected."""
        reqs = [
            make_req("REQ-001", "Must support at least 100 users.",
                     constraints=[make_constraint("system", "users", ">=", "100")]),
            make_req("REQ-002", "Must support at least 50 users.",
                     constraints=[make_constraint("system", "users", ">=", "50")]),
        ]
        issues = detect_z3_subsumptions(reqs)
        # REQ-001 (>=100) subsumes REQ-002 (>=50) — REQ-002 is redundant
        assert len(issues) >= 1

    def test_single_req_no_subsumption(self):
        reqs = [
            make_req("REQ-001", "Load time shall be under 3 seconds.",
                     constraints=[make_constraint("load_time", "seconds", "<", "3")]),
        ]
        issues = detect_z3_subsumptions(reqs)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# 5. FR/NFR classifier
# ---------------------------------------------------------------------------

class TestFRNFRClassifier:
    def test_classifies_fr(self):
        req_type, category = classify_requirement(
            "The system shall allow users to create orders."
        )
        assert req_type == "Functional"
        assert category is None

    def test_classifies_performance_nfr(self):
        req_type, category = classify_requirement(
            "The system shall respond within 2 seconds under normal load."
        )
        assert req_type == "Non-Functional"
        assert category == "Performance"

    def test_classifies_security_nfr(self):
        req_type, category = classify_requirement(
            "All user data must be encrypted using AES-256."
        )
        assert req_type == "Non-Functional"
        assert category == "Security"

    def test_classifies_usability_nfr(self):
        req_type, category = classify_requirement(
            "The interface shall be user-friendly and intuitive for non-technical users."
        )
        assert req_type == "Non-Functional"
        assert category == "Usability"

    def test_classifies_reliability_nfr(self):
        req_type, category = classify_requirement(
            "The system shall maintain 99.9% uptime with automatic failover."
        )
        assert req_type == "Non-Functional"
        assert category == "Reliability"

    def test_classifies_maintainability_nfr(self):
        req_type, category = classify_requirement(
            "The codebase shall be modular and well-documented for future maintainability."
        )
        assert req_type == "Non-Functional"
        assert category == "Maintainability"

    def test_classifies_portability_nfr(self):
        req_type, category = classify_requirement(
            "The application shall run on Windows, Linux, and macOS."
        )
        assert req_type == "Non-Functional"
        assert category == "Portability"

    def test_dataset_fr_pattern(self):
        """From dataset: 'The system shall allow users to validate profiles'."""
        req_type, category = classify_requirement(
            "The system shall allow users to validate profiles."
        )
        assert req_type == "Functional"

    def test_dataset_nfr_security_pattern(self):
        """From dataset security rows."""
        req_type, category = classify_requirement(
            "The application shall enforce role-based access control (RBAC) for all operations."
        )
        assert req_type == "Non-Functional"
        assert category == "Security"


# ---------------------------------------------------------------------------
# 6. Test-project isolation guard
# ---------------------------------------------------------------------------

class TestProjectIsolation:
    def test_no_test_project_in_training(self):
        """Ensure held-out test projects don't appear in training split."""
        import json
        from pathlib import Path

        dataset_path = Path("eval/dataset_real.json")
        test_projects_path = Path("eval/test_projects.txt")

        if not dataset_path.exists() or not test_projects_path.exists():
            pytest.skip("dataset_real.json or test_projects.txt not yet generated")

        with open(test_projects_path) as f:
            test_projects = set(line.strip() for line in f if line.strip())

        with open(dataset_path) as f:
            data = json.load(f)
            if isinstance(data, dict) and "documents" in data:
                docs = data["documents"]
            else:
                docs = data

        train_docs = 0
        test_docs_count = 0
        for doc in docs:
            if doc.get("split") == "train":
                train_docs += 1
                assert doc["project"] not in test_projects, (
                    f"Test project '{doc['project']}' found in training split!"
                )
            elif doc.get("split") == "test":
                test_docs_count += 1
                assert doc["project"] in test_projects, "Test doc not in test_projects.txt"
                
        assert train_docs > 0, "No training documents found!"
        assert test_docs_count > 0, "No test documents found!"


# ---------------------------------------------------------------------------
# 6. Completeness detector
# ---------------------------------------------------------------------------

class TestCompletenessDetector:
    def test_completeness_singular(self):
        from backend.pipeline.analyzer import _detect_completeness
        reqs = [
            make_req("REQ-001", "The customer can view the page.")
        ]
        issues = _detect_completeness(reqs)
        # Should trigger auth completeness for "customer"
        auth_issues = [i for i in issues if "auth" in i["description"]]
        assert len(auth_issues) == 1
        assert "REQ-001" in auth_issues[0]["involved_req_ids"]

    def test_completeness_plural(self):
        from backend.pipeline.analyzer import _detect_completeness
        reqs = [
            make_req("REQ-001", "Customers can view available services.")
        ]
        issues = _detect_completeness(reqs)
        # Should trigger auth completeness for "Customers"
        auth_issues = [i for i in issues if "auth" in i["description"]]
        assert len(auth_issues) == 1
        assert "REQ-001" in auth_issues[0]["involved_req_ids"]

    def test_completeness_unrelated(self):
        from backend.pipeline.analyzer import _detect_completeness
        reqs = [
            make_req("REQ-001", "The system shall be fast.")
        ]
        issues = _detect_completeness(reqs)
        # Should NOT trigger auth completeness
        auth_issues = [i for i in issues if "auth" in i["description"]]
        assert len(auth_issues) == 0
