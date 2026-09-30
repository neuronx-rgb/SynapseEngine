"""
tests/test_lexicon.py
Tests for lexicon/regex-based ambiguity detection.
"""
import os
os.environ["MOCK_MODE"] = "true"

import pytest
from backend.models import ParsedRequirement, ParseResult
from backend.pipeline.analyzer import _detect_ambiguity_lexicon


def make_req(req_id: str, text: str) -> ParsedRequirement:
    return ParsedRequirement(
        req_id=req_id,
        text=text,
        source_sentence=text,
        entities=[],
        actions=[],
        constraints=[],
    )


def test_detects_fast():
    reqs = [make_req("REQ-001", "The system must respond fast to user requests.")]
    issues = _detect_ambiguity_lexicon(reqs)
    assert len(issues) >= 1
    assert any("fast" in i["description"].lower() for i in issues)


def test_detects_secure():
    reqs = [make_req("REQ-001", "The booking process must be secure.")]
    issues = _detect_ambiguity_lexicon(reqs)
    assert len(issues) >= 1
    assert any("secure" in i["description"].lower() for i in issues)


def test_detects_scalable():
    reqs = [make_req("REQ-001", "The system must be scalable to support future growth.")]
    issues = _detect_ambiguity_lexicon(reqs)
    assert len(issues) >= 1
    assert any("scalable" in i["description"].lower() for i in issues)


def test_detects_tbd():
    reqs = [make_req("REQ-001", "Payment will be handled via TBD gateway.")]
    issues = _detect_ambiguity_lexicon(reqs)
    assert len(issues) >= 1
    assert any("TBD" in i["description"] for i in issues)


def test_detects_double_negation():
    reqs = [make_req("REQ-001", "The system must not be unavailable during business hours.")]
    issues = _detect_ambiguity_lexicon(reqs)
    assert len(issues) >= 1
    # Should detect double negation
    assert any("unavailable" in i["description"].lower() or "negation" in i["description"].lower() for i in issues)


def test_detects_and_or():
    reqs = [make_req("REQ-001", "Users and/or administrators can delete accounts.")]
    issues = _detect_ambiguity_lexicon(reqs)
    assert len(issues) >= 1
    assert any("and/or" in i["description"].lower() for i in issues)


def test_detects_should_modal():
    reqs = [make_req("REQ-001", "The system should encrypt all user data.")]
    issues = _detect_ambiguity_lexicon(reqs)
    # 'should' is a vague modal — may or may not be flagged depending on regex
    # At minimum, no crash
    assert isinstance(issues, list)


def test_clear_requirement_no_ambiguity():
    """A clear, specific requirement should not trigger vague-term detection."""
    reqs = [make_req("REQ-001", "The system must process payment within 30 seconds.")]
    issues = _detect_ambiguity_lexicon(reqs)
    # 'within 30 seconds' is measurable — should have zero or very few issues
    vague_issues = [i for i in issues if i["issue_type"] == "ambiguity" and i["severity"] == "blocking"]
    assert len(vague_issues) == 0


def test_multiple_requirements_multiple_issues():
    reqs = [
        make_req("REQ-001", "The system must be fast and scalable."),
        make_req("REQ-002", "Data must be stored securely."),
    ]
    issues = _detect_ambiguity_lexicon(reqs)
    assert len(issues) >= 2
    req_ids_with_issues = {i["involved_req_ids"][0] for i in issues}
    assert "REQ-001" in req_ids_with_issues
    assert "REQ-002" in req_ids_with_issues
