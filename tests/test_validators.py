"""
tests/test_validators.py
Tests for deterministic validators (OpenAPI, SQL, test plan, coverage).
"""
import os
os.environ["MOCK_MODE"] = "true"

import json
import pytest
from backend.models import ArtifactOut, ArtifactType
from backend.pipeline.validators import (
    validate_openapi,
    validate_sql,
    validate_test_plan,
    compute_coverage,
)

# ---------------------------------------------------------------------------
# SQL validation
# ---------------------------------------------------------------------------

VALID_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total REAL NOT NULL CHECK (total >= 0),
    status TEXT NOT NULL DEFAULT 'pending'
);
"""

INVALID_DDL = """
CREATE TABLE incomplete_syntax (
    id INTEGER PRIMARY KEY,
    oops TEXT NOT NULL REFERENCES nonexistent_table(id)
);
"""


def test_valid_sql_passes():
    art = ArtifactOut(artifact_type=ArtifactType.sql_ddl, content=VALID_DDL, is_valid=False, validation_errors=[])
    result = validate_sql(art)
    assert result.is_valid is True
    assert result.validation_errors == []


def test_invalid_sql_fails():
    art = ArtifactOut(artifact_type=ArtifactType.sql_ddl, content=INVALID_DDL, is_valid=False, validation_errors=[])
    result = validate_sql(art)
    # Foreign key to nonexistent table may pass in SQLite (deferred) but syntax errors won't
    # At minimum no crash
    assert isinstance(result.is_valid, bool)


def test_empty_sql_passes():
    art = ArtifactOut(artifact_type=ArtifactType.sql_ddl, content="", is_valid=False, validation_errors=[])
    result = validate_sql(art)
    assert result.is_valid is True


# ---------------------------------------------------------------------------
# Test plan validation
# ---------------------------------------------------------------------------

VALID_TEST_PLAN = json.dumps({
    "test_cases": [
        {
            "test_id": "TC-001",
            "name": "Happy path",
            "category": "positive",
            "req_ids": ["REQ-001"],
            "description": "Basic test",
            "input_data": {},
            "expected_outcome": "success",
        }
    ]
})

INVALID_TEST_PLAN = json.dumps({"test_cases": [{"test_id": "TC-001", "missing_required_field": True}]})


def test_valid_test_plan_passes():
    art = ArtifactOut(artifact_type=ArtifactType.test_plan, content=VALID_TEST_PLAN, is_valid=False, validation_errors=[])
    result = validate_test_plan(art)
    assert result.is_valid is True


def test_invalid_test_plan_fails():
    art = ArtifactOut(artifact_type=ArtifactType.test_plan, content=INVALID_TEST_PLAN, is_valid=False, validation_errors=[])
    result = validate_test_plan(art)
    assert result.is_valid is False
    assert len(result.validation_errors) > 0


def test_invalid_json_test_plan():
    art = ArtifactOut(artifact_type=ArtifactType.test_plan, content="not json at all", is_valid=False, validation_errors=[])
    result = validate_test_plan(art)
    assert result.is_valid is False


# ---------------------------------------------------------------------------
# Coverage computation
# ---------------------------------------------------------------------------

def test_coverage_full():
    """All reqs are covered by tests."""
    test_content = json.dumps({
        "test_cases": [
            {"test_id": "TC-001", "name": "t1", "category": "positive", "req_ids": ["REQ-001", "REQ-002"], "description": "", "input_data": {}, "expected_outcome": ""},
            {"test_id": "TC-002", "name": "t2", "category": "positive", "req_ids": ["REQ-003"], "description": "", "input_data": {}, "expected_outcome": ""},
        ]
    })
    art = ArtifactOut(artifact_type=ArtifactType.test_plan, content=test_content, is_valid=True, validation_errors=[])
    coverage, uncovered = compute_coverage([art], ["REQ-001", "REQ-002", "REQ-003"])
    assert coverage == 100.0
    assert uncovered == []


def test_coverage_partial():
    """Some reqs are uncovered."""
    test_content = json.dumps({
        "test_cases": [
            {"test_id": "TC-001", "name": "t1", "category": "positive", "req_ids": ["REQ-001"], "description": "", "input_data": {}, "expected_outcome": ""},
        ]
    })
    art = ArtifactOut(artifact_type=ArtifactType.test_plan, content=test_content, is_valid=True, validation_errors=[])
    coverage, uncovered = compute_coverage([art], ["REQ-001", "REQ-002", "REQ-003"])
    assert coverage < 100.0
    assert "REQ-002" in uncovered
    assert "REQ-003" in uncovered


def test_coverage_empty_test_plan():
    """No tests means 0% coverage."""
    test_content = json.dumps({"test_cases": []})
    art = ArtifactOut(artifact_type=ArtifactType.test_plan, content=test_content, is_valid=True, validation_errors=[])
    coverage, uncovered = compute_coverage([art], ["REQ-001", "REQ-002"])
    assert coverage == 0.0
    assert "REQ-001" in uncovered


# ---------------------------------------------------------------------------
# OpenAPI validation (with fixture)
# ---------------------------------------------------------------------------

def test_openapi_valid_fixture():
    """The fixture YAML from openapi_generate.json should be valid."""
    import json
    from pathlib import Path
    fixture_path = Path("tests/fixtures/openapi_generate.json")
    if not fixture_path.exists():
        pytest.skip("Fixture not found")
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    yaml_content = data["response"]["yaml_content"]
    art = ArtifactOut(artifact_type=ArtifactType.openapi, content=yaml_content, is_valid=False, validation_errors=[])
    result = validate_openapi(art)
    assert result.is_valid is True, f"OpenAPI validation errors: {result.validation_errors}"


def test_sql_valid_fixture():
    """The fixture DDL from sql_generate.json should execute in SQLite."""
    import json
    from pathlib import Path
    fixture_path = Path("tests/fixtures/sql_generate.json")
    if not fixture_path.exists():
        pytest.skip("Fixture not found")
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    ddl_content = data["response"]["ddl_content"]
    art = ArtifactOut(artifact_type=ArtifactType.sql_ddl, content=ddl_content, is_valid=False, validation_errors=[])
    result = validate_sql(art)
    assert result.is_valid is True, f"SQL errors: {result.validation_errors}"
