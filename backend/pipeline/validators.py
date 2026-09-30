"""
backend/pipeline/validators.py
Deterministic validators (no LLM):
- OpenAPI: validate with openapi-spec-validator
- SQL DDL: execute in in-memory SQLite
- Test plan: validate against Pydantic schema
- Coverage: % of requirements with >=1 test
- Repair loop: up to 2 LLM repair attempts on failure
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import List, Optional, Tuple

from backend.llm import generate_json, generate_text
from backend.models import (
    ArtifactOut,
    ArtifactType,
    OpenAPIGenerateResult,
    SQLGenerateResult,
    TestPlanResult,
)


# ---------------------------------------------------------------------------
# OpenAPI validation
# ---------------------------------------------------------------------------

def validate_openapi(artifact: ArtifactOut) -> ArtifactOut:
    errors: List[str] = []
    try:
        import yaml
        from openapi_spec_validator import validate
        spec_dict = yaml.safe_load(artifact.content)
        validate(spec_dict)
    except ImportError:
        errors.append("openapi-spec-validator not installed; skipping OpenAPI validation.")
    except Exception as e:
        errors.append(str(e))

    return artifact.model_copy(update={
        "is_valid": len(errors) == 0,
        "validation_errors": errors,
    })


OPENAPI_REPAIR_PROMPT = """
The following OpenAPI 3.0 YAML has validation errors. Fix ONLY the errors listed.
Do not change the API design — just make it spec-compliant.

Original YAML:
{yaml}

Errors:
{errors}

Return valid JSON: {{"yaml_content": "<fixed YAML>", "source_req_ids": {req_ids}}}
"""


def repair_openapi(artifact: ArtifactOut, req_ids: List[str]) -> ArtifactOut:
    for _ in range(2):
        prompt = OPENAPI_REPAIR_PROMPT.format(
            yaml=artifact.content[:4000],
            errors="\n".join(artifact.validation_errors),
            req_ids=json.dumps(req_ids),
        )
        result = generate_json(prompt, OpenAPIGenerateResult)
        repaired = artifact.model_copy(update={"content": result.yaml_content})
        repaired = validate_openapi(repaired)
        if repaired.is_valid:
            return repaired
    return artifact


# ---------------------------------------------------------------------------
# SQL DDL validation
# ---------------------------------------------------------------------------

def validate_sql(artifact: ArtifactOut) -> ArtifactOut:
    errors: List[str] = []
    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # Split by semicolons but keep statements
        statements = [s.strip() for s in artifact.content.split(";") if s.strip()]
        for stmt in statements:
            if stmt:
                cursor.execute(stmt)
        conn.close()
    except Exception as e:
        errors.append(str(e))

    return artifact.model_copy(update={
        "is_valid": len(errors) == 0,
        "validation_errors": errors,
    })


SQL_REPAIR_PROMPT = """
The following SQL DDL has errors when executed in SQLite. Fix ONLY the syntax/compatibility issues.
Do not change the schema design.

Original DDL:
{ddl}

Errors:
{errors}

Return valid JSON: {{"ddl_content": "<fixed DDL>", "source_req_ids": {req_ids}}}
"""


def repair_sql(artifact: ArtifactOut, req_ids: List[str]) -> ArtifactOut:
    for _ in range(2):
        prompt = SQL_REPAIR_PROMPT.format(
            ddl=artifact.content[:4000],
            errors="\n".join(artifact.validation_errors),
            req_ids=json.dumps(req_ids),
        )
        result = generate_json(prompt, SQLGenerateResult)
        repaired = artifact.model_copy(update={"content": result.ddl_content})
        repaired = validate_sql(repaired)
        if repaired.is_valid:
            return repaired
    return artifact


# ---------------------------------------------------------------------------
# Test plan validation
# ---------------------------------------------------------------------------

def validate_test_plan(artifact: ArtifactOut) -> ArtifactOut:
    errors: List[str] = []
    try:
        data = json.loads(artifact.content)
        TestPlanResult.model_validate(data)
    except Exception as e:
        errors.append(str(e))

    return artifact.model_copy(update={
        "is_valid": len(errors) == 0,
        "validation_errors": errors,
    })


# ---------------------------------------------------------------------------
# Coverage computation
# ---------------------------------------------------------------------------

def compute_coverage(artifacts: List[ArtifactOut], req_ids: List[str]) -> Tuple[float, List[str]]:
    """
    Returns (coverage_pct, uncovered_req_ids).
    A req is covered if it appears in at least one test case.
    """
    covered: set[str] = set()
    for art in artifacts:
        if art.artifact_type == ArtifactType.test_plan:
            try:
                data = json.loads(art.content)
                for tc in data.get("test_cases", []):
                    for rid in tc.get("req_ids", []):
                        covered.add(rid)
            except Exception:
                pass

    uncovered = [r for r in req_ids if r not in covered]
    pct = (len(covered) / len(req_ids) * 100) if req_ids else 100.0
    return pct, uncovered


# ---------------------------------------------------------------------------
# Main validate + repair orchestrator
# ---------------------------------------------------------------------------

def validate_and_repair(artifacts: List[ArtifactOut], req_ids: List[str]) -> List[ArtifactOut]:
    """Run validators on all artifacts; attempt repair on failures."""
    result = []
    for art in artifacts:
        if art.artifact_type == ArtifactType.openapi:
            art = validate_openapi(art)
            if not art.is_valid:
                art = repair_openapi(art, req_ids)
        elif art.artifact_type == ArtifactType.sql_ddl:
            art = validate_sql(art)
            if not art.is_valid:
                art = repair_sql(art, req_ids)
        elif art.artifact_type == ArtifactType.test_plan:
            art = validate_test_plan(art)
        result.append(art)
    return result
