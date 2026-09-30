"""
backend/models.py
All SQLModel (DB) + Pydantic (API/LLM) schemas for Synapse Engine.
"""

import enum
import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, field_validator
from sqlmodel import JSON, Column, Field, Relationship, SQLModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IssueType(str, enum.Enum):
    ambiguity = "ambiguity"
    conflict = "conflict"
    incompleteness = "incompleteness"


class IssueSeverity(str, enum.Enum):
    blocking = "blocking"
    warning = "warning"


class IssueStatus(str, enum.Enum):
    open = "open"
    answered = "answered"
    assumed = "assumed"


class ArtifactType(str, enum.Enum):
    openapi = "openapi"
    sql_ddl = "sql_ddl"
    test_plan = "test_plan"


# ---------------------------------------------------------------------------
# DB Tables (SQLModel)
# ---------------------------------------------------------------------------

class Project(SQLModel, table=True):
    __tablename__ = "projects"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="Untitled Project")
    raw_text: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    requirements: List["Requirement"] = Relationship(back_populates="project")
    artifacts: List["Artifact"] = Relationship(back_populates="project")


class Requirement(SQLModel, table=True):
    __tablename__ = "requirements"
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    req_id: str  # REQ-001
    text: str
    source_sentence: str
    entities: str = Field(default="[]")   # JSON list
    actions: str = Field(default="[]")    # JSON list
    constraints: str = Field(default="[]")  # JSON list of Constraint dicts
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project: Optional[Project] = Relationship(back_populates="requirements")
    issues: List["Issue"] = Relationship(back_populates="requirement")

    def get_constraints(self) -> list:
        return json.loads(self.constraints)

    def get_entities(self) -> list:
        return json.loads(self.entities)

    def get_actions(self) -> list:
        return json.loads(self.actions)


class Issue(SQLModel, table=True):
    __tablename__ = "issues"
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    requirement_id: Optional[int] = Field(default=None, foreign_key="requirements.id")
    issue_id: str  # ISS-001
    issue_type: IssueType
    severity: IssueSeverity
    involved_req_ids: str = Field(default="[]")  # JSON list of req_id strings
    description: str
    suggested_question: str
    status: IssueStatus = Field(default=IssueStatus.open)
    answer: Optional[str] = None
    assumption: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    answered_at: Optional[datetime] = None

    requirement: Optional[Requirement] = Relationship(back_populates="issues")

    def get_involved_req_ids(self) -> list[str]:
        return json.loads(self.involved_req_ids)


class Artifact(SQLModel, table=True):
    __tablename__ = "artifacts"
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    artifact_type: ArtifactType
    content: str  # YAML, SQL, or JSON string
    is_valid: bool = Field(default=False)
    validation_errors: str = Field(default="[]")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project: Optional[Project] = Relationship(back_populates="artifacts")


class TraceLink(SQLModel, table=True):
    __tablename__ = "tracelinks"
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    req_id: str
    artifact_type: ArtifactType
    item_id: str   # endpoint path, table.column, test id
    item_label: str


class DecisionLog(SQLModel, table=True):
    __tablename__ = "decision_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    issue_id: str
    question: str
    answer: Optional[str] = None
    assumption: Optional[str] = None
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Pydantic schemas (API request/response + LLM output)
# ---------------------------------------------------------------------------

class ConstraintSchema(BaseModel):
    subject: str
    attribute: str
    op: str  # ==, !=, <, <=, >, >=
    value: Any

    @field_validator("op")
    @classmethod
    def validate_op(cls, v: str) -> str:
        allowed = {"==", "!=", "<", "<=", ">", ">="}
        if v not in allowed:
            raise ValueError(f"op must be one of {allowed}")
        return v


class ParsedRequirement(BaseModel):
    req_id: str
    text: str
    source_sentence: str
    entities: List[str]
    actions: List[str]
    constraints: List[ConstraintSchema]


class ParseResult(BaseModel):
    requirements: List[ParsedRequirement]


class IssueOut(BaseModel):
    issue_id: str
    issue_type: IssueType
    severity: IssueSeverity
    involved_req_ids: List[str]
    description: str
    suggested_question: str
    status: IssueStatus
    answer: Optional[str] = None
    assumption: Optional[str] = None


class AnalyzeResult(BaseModel):
    issues: List[IssueOut]


class AnswerRequest(BaseModel):
    answer: str


class AssumeRequest(BaseModel):
    assumption: str = "default behavior assumed"


class GenerateRequest(BaseModel):
    project_id: int


class ArtifactOut(BaseModel):
    artifact_type: ArtifactType
    content: str
    is_valid: bool
    validation_errors: List[str]


class TraceLinkOut(BaseModel):
    req_id: str
    artifact_type: ArtifactType
    item_id: str
    item_label: str


class TraceabilityOut(BaseModel):
    links: List[TraceLinkOut]
    uncovered_req_ids: List[str]
    coverage_pct: float
    decision_log: List[dict]


class HealthOut(BaseModel):
    status: str
    mock_mode: bool
    active_provider: str
    model: str


class ProjectCreate(BaseModel):
    name: str = "Untitled Project"


class ProjectOut(BaseModel):
    id: int
    name: str
    created_at: datetime


class RequirementsInput(BaseModel):
    text: str
    max_length: int = 8000

    @field_validator("text")
    @classmethod
    def cap_length(cls, v: str) -> str:
        if len(v) > 8000:
            raise ValueError("Input exceeds 8000 character limit")
        return v


# LLM output schemas used by generate_json()
class LLMIssue(BaseModel):
    issue_id: str
    issue_type: IssueType
    severity: IssueSeverity
    involved_req_ids: List[str]
    description: str
    suggested_question: str


class LLMIssueList(BaseModel):
    issues: List[LLMIssue]


class OpenAPIGenerateResult(BaseModel):
    yaml_content: str
    source_req_ids: List[str]


class SQLGenerateResult(BaseModel):
    ddl_content: str
    source_req_ids: List[str]


class TestCase(BaseModel):
    test_id: str
    name: str
    category: str  # positive, negative, boundary
    req_ids: List[str]
    description: str
    input_data: dict
    expected_outcome: str


class TestPlanResult(BaseModel):
    test_cases: List[TestCase]


class EvalMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    openapi_valid_rate: float
    sql_exec_rate: float
    test_coverage_pct: float
