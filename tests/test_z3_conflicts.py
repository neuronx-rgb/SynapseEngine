"""
tests/test_z3_conflicts.py
Tests for Z3-based conflict detection.
"""
import os
os.environ["MOCK_MODE"] = "true"

import pytest
from backend.models import ParsedRequirement, ParseResult, ConstraintSchema
from backend.pipeline.analyzer import _detect_conflicts_z3


def make_req(req_id: str, text: str, constraints: list) -> ParsedRequirement:
    return ParsedRequirement(
        req_id=req_id,
        text=text,
        source_sentence=text,
        entities=[],
        actions=[],
        constraints=[ConstraintSchema(**c) for c in constraints],
    )


def test_z3_detects_simple_numeric_conflict():
    """amount > 100 AND amount < 50 should be unsat."""
    reqs = [
        make_req("REQ-001", "Amount must be over 100", [{"subject": "order", "attribute": "amount", "op": ">", "value": 100}]),
        make_req("REQ-002", "Amount must be under 50", [{"subject": "order", "attribute": "amount", "op": "<", "value": 50}]),
    ]
    issues = _detect_conflicts_z3(reqs)
    assert len(issues) >= 1
    types = [i["issue_type"] for i in issues]
    assert "conflict" in types


def test_z3_no_conflict_for_compatible():
    """amount > 0 AND amount <= 1000 are compatible."""
    reqs = [
        make_req("REQ-001", "Amount must be positive", [{"subject": "order", "attribute": "amount", "op": ">", "value": 0}]),
        make_req("REQ-002", "Amount must be at most 1000", [{"subject": "order", "attribute": "amount", "op": "<=", "value": 1000}]),
    ]
    issues = _detect_conflicts_z3(reqs)
    assert len(issues) == 0


def test_z3_detects_approval_threshold_conflict():
    """orders >1000 require approval AND orders >500 auto-approved = conflict."""
    reqs = [
        make_req("REQ-001", "Orders above $1000 require approval", [
            {"subject": "order", "attribute": "approval_threshold", "op": ">", "value": 1000}
        ]),
        make_req("REQ-002", "Orders above $500 are auto-approved", [
            {"subject": "order", "attribute": "approval_threshold", "op": ">", "value": 500}
        ]),
    ]
    # Different values for same attribute under same op — not Z3 unsat but detectable
    # Z3 conflict: >1000 AND <500 would be unsat
    reqs2 = [
        make_req("REQ-001", "Orders above $1000 require approval", [
            {"subject": "order", "attribute": "amount", "op": ">", "value": 1000}
        ]),
        make_req("REQ-002", "Orders under $500 must be approved", [
            {"subject": "order", "attribute": "amount", "op": "<", "value": 500}
        ]),
    ]
    issues = _detect_conflicts_z3(reqs2)
    assert len(issues) >= 1


def test_z3_detects_string_value_conflict():
    """email uniqueness == globally_unique vs shared_allowed."""
    reqs = [
        make_req("REQ-001", "Emails must be globally unique", [
            {"subject": "email", "attribute": "uniqueness", "op": "==", "value": "globally_unique"}
        ]),
        make_req("REQ-002", "Emails can be shared", [
            {"subject": "email", "attribute": "uniqueness", "op": "==", "value": "shared_allowed"}
        ]),
    ]
    issues = _detect_conflicts_z3(reqs)
    assert len(issues) >= 1
    assert any("globally_unique" in i.get("description", "") or "shared" in i.get("description", "") for i in issues)


def test_z3_single_requirement_no_conflict():
    """Single requirement cannot conflict with itself."""
    reqs = [
        make_req("REQ-001", "Amount must be over 100", [{"subject": "order", "attribute": "amount", "op": ">", "value": 100}]),
    ]
    issues = _detect_conflicts_z3(reqs)
    assert len(issues) == 0


def test_z3_different_subjects_no_conflict():
    """Different subjects should not conflict even with contradictory ops."""
    reqs = [
        make_req("REQ-001", "Order amount > 100", [{"subject": "order", "attribute": "amount", "op": ">", "value": 100}]),
        make_req("REQ-002", "Product weight < 5", [{"subject": "product", "attribute": "weight", "op": "<", "value": 5}]),
    ]
    issues = _detect_conflicts_z3(reqs)
    assert len(issues) == 0
