"""
backend/pipeline/generator.py
Generates three artifacts from resolved requirements:
1. OpenAPI 3 YAML
2. SQL DDL
3. Test Plan JSON

Each artifact carries source_req_ids for full traceability.
Splits into separate LLM calls to stay within token limits.
"""
from __future__ import annotations

import json
from typing import List

from backend.llm import generate_json
from backend.models import (
    ArtifactOut,
    ArtifactType,
    IssueOut,
    OpenAPIGenerateResult,
    ParsedRequirement,
    ParseResult,
    SQLGenerateResult,
    TestCase,
    TestPlanResult,
)

# ---------------------------------------------------------------------------
# OpenAPI generation
# ---------------------------------------------------------------------------

OPENAPI_PROMPT = """
You are an API designer. Based on these software requirements, generate a complete
OpenAPI 3.0.3 specification in YAML format.

Requirements:
{reqs_json}

Rules:
- Include all endpoints implied by the requirements
- Include proper request/response schemas with all fields
- Include error responses (400, 401, 404, 422, 500)
- Add source_req_ids as an x-source-requirements extension on each operation
- Use proper HTTP methods (GET, POST, PUT, DELETE, PATCH)
- Include authentication if required by specs

Return ONLY valid JSON with this structure:
{{
  "yaml_content": "<complete OpenAPI YAML as a string>",
  "source_req_ids": ["REQ-001", "REQ-002"]
}}
"""


def generate_openapi(requirements: List[ParsedRequirement]) -> ArtifactOut:
    reqs_simple = [{"id": r.req_id, "text": r.text, "entities": r.entities, "actions": r.actions}
                   for r in requirements]
    prompt = OPENAPI_PROMPT.format(reqs_json=json.dumps(reqs_simple, indent=2))
    result = generate_json(prompt, OpenAPIGenerateResult)
    return ArtifactOut(
        artifact_type=ArtifactType.openapi,
        content=result.yaml_content,
        is_valid=False,
        validation_errors=[],
    )


# ---------------------------------------------------------------------------
# SQL DDL generation
# ---------------------------------------------------------------------------

SQL_PROMPT = """
You are a database architect. Based on these software requirements, generate SQL DDL
(CREATE TABLE statements) for SQLite-compatible schema.

Requirements:
{reqs_json}

Rules:
- Include all tables implied by the requirements
- Add proper PRIMARY KEY, NOT NULL, UNIQUE, FOREIGN KEY, CHECK constraints
- Include created_at / updated_at timestamps where appropriate
- Each table comment should reference the source requirement IDs

Return ONLY valid JSON with this structure:
{{
  "ddl_content": "<complete SQL DDL as a string>",
  "source_req_ids": ["REQ-001", "REQ-002"]
}}
"""


def generate_sql(requirements: List[ParsedRequirement]) -> ArtifactOut:
    reqs_simple = [{"id": r.req_id, "text": r.text, "entities": r.entities, "constraints": [c.model_dump() for c in r.constraints]}
                   for r in requirements]
    prompt = SQL_PROMPT.format(reqs_json=json.dumps(reqs_simple, indent=2))
    result = generate_json(prompt, SQLGenerateResult)
    return ArtifactOut(
        artifact_type=ArtifactType.sql_ddl,
        content=result.ddl_content,
        is_valid=False,
        validation_errors=[],
    )


# ---------------------------------------------------------------------------
# Test plan generation
# ---------------------------------------------------------------------------

TEST_PLAN_PROMPT = """
You are a QA engineer. Based on these software requirements, generate a comprehensive
test plan covering positive, negative, and boundary test cases.

Requirements:
{reqs_json}

Rules:
- Generate at least 2 test cases per requirement
- For numeric constraints (e.g., amount > $500), include boundary tests:
  exactly at the boundary (e.g., $500.00), just above ($500.01), just below ($499.99)
- Include negative cases (invalid input, unauthorized access, etc.)
- Each test must reference the source requirement IDs

Return ONLY valid JSON with this structure:
{{
  "test_cases": [
    {{
      "test_id": "TC-001",
      "name": "...",
      "category": "positive|negative|boundary",
      "req_ids": ["REQ-001"],
      "description": "...",
      "input_data": {{}},
      "expected_outcome": "..."
    }}
  ]
}}
"""


def generate_tests(requirements: List[ParsedRequirement]) -> ArtifactOut:
    reqs_simple = [{"id": r.req_id, "text": r.text, "entities": r.entities,
                    "actions": r.actions, "constraints": [c.model_dump() for c in r.constraints]}
                   for r in requirements]
    prompt = TEST_PLAN_PROMPT.format(reqs_json=json.dumps(reqs_simple, indent=2))
    result = generate_json(prompt, TestPlanResult)
    return ArtifactOut(
        artifact_type=ArtifactType.test_plan,
        content=result.model_dump_json(indent=2),
        is_valid=False,
        validation_errors=[],
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_all(parse_result: ParseResult, issues: List[IssueOut]) -> List[ArtifactOut]:
    """
    Generate all three artifacts. Raises if blocking issues remain open.
    """
    from backend.pipeline.clarifier import has_blocking_issues
    if has_blocking_issues(issues):
        raise ValueError("Cannot generate artifacts while blocking issues are open.")

    requirements = parse_result.requirements
    artifacts = [
        generate_openapi(requirements),
        generate_sql(requirements),
        generate_tests(requirements),
    ]
    return artifacts
