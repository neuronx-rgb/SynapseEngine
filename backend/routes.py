"""
backend/routes.py
All FastAPI route handlers for Synapse Engine.
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.db import get_session
from backend.llm import MOCK_MODE, get_active_provider
from backend.models import (
    AnswerRequest,
    ArtifactOut,
    ArtifactType,
    AssumeRequest,
    DecisionLog,
    HealthOut,
    Issue,
    IssueOut,
    IssueStatus,
    IssueSeverity,
    IssueType,
    Project,
    ProjectCreate,
    ProjectOut,
    Requirement,
    RequirementsInput,
    Artifact,
    TraceLink,
    TraceabilityOut,
    TraceLinkOut,
    ParsedRequirement,
    ParseResult,
    ConstraintSchema,
)
from backend.pipeline import analyzer, clarifier, generator, parser, traceability, validators

router = APIRouter()

# Session count limiter for public deployment
_session_call_count: dict[str, int] = {}
MAX_CALLS_PER_SESSION = int(os.getenv("MAX_CALLS_PER_SESSION", "20"))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthOut)
def health():
    provider, model = get_active_provider()
    return HealthOut(
        status="ok",
        mock_mode=MOCK_MODE,
        active_provider=provider,
        model=model,
    )


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@router.post("/projects", response_model=ProjectOut)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)):
    project = Project(name=body.name)
    session.add(project)
    session.commit()
    session.refresh(project)
    return ProjectOut(id=project.id, name=project.name, created_at=project.created_at)


@router.get("/projects", response_model=List[ProjectOut])
def list_projects(session: Session = Depends(get_session)):
    projects = session.exec(select(Project)).all()
    return [ProjectOut(id=p.id, name=p.name, created_at=p.created_at) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, session: Session = Depends(get_session)):
    p = session.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return ProjectOut(id=p.id, name=p.name, created_at=p.created_at)


# ---------------------------------------------------------------------------
# Requirements parsing
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/requirements")
def submit_requirements(
    project_id: int,
    body: RequirementsInput,
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Delete old requirements for this project
    old_reqs = session.exec(select(Requirement).where(Requirement.project_id == project_id)).all()
    for r in old_reqs:
        old_issues = session.exec(select(Issue).where(Issue.requirement_id == r.id)).all()
        for i in old_issues:
            session.delete(i)
        session.delete(r)
    session.commit()

    # Parse
    parse_result = parser.parse_requirements(body.text)

    # Save requirements
    saved_reqs = []
    for pr in parse_result.requirements:
        req = Requirement(
            project_id=project_id,
            req_id=pr.req_id,
            text=pr.text,
            source_sentence=pr.source_sentence,
            entities=json.dumps(pr.entities),
            actions=json.dumps(pr.actions),
            constraints=json.dumps([c.model_dump() for c in pr.constraints]),
        )
        session.add(req)
        saved_reqs.append(req)

    project.raw_text = body.text
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()

    return {"project_id": project_id, "requirement_count": len(saved_reqs),
            "req_ids": [r.req_id for r in saved_reqs]}


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/analyze")
def analyze_requirements(project_id: int, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    reqs_db = session.exec(select(Requirement).where(Requirement.project_id == project_id)).all()
    if not reqs_db:
        raise HTTPException(400, "No requirements found. Submit requirements first.")

    # Delete old issues
    old_issues = session.exec(select(Issue).where(Issue.project_id == project_id)).all()
    for i in old_issues:
        session.delete(i)
    session.commit()

    # Build ParseResult from DB
    parsed_reqs = []
    for r in reqs_db:
        constraints_raw = json.loads(r.constraints)
        constraints = [ConstraintSchema(**c) for c in constraints_raw]
        parsed_reqs.append(ParsedRequirement(
            req_id=r.req_id,
            text=r.text,
            source_sentence=r.source_sentence,
            entities=json.loads(r.entities),
            actions=json.loads(r.actions),
            constraints=constraints,
        ))
    parse_result = ParseResult(requirements=parsed_reqs)

    # Run analysis
    issues_out = analyzer.analyze(parse_result)

    # Save issues
    for i, iss in enumerate(issues_out):
        req_id_str = iss.involved_req_ids[0] if iss.involved_req_ids else None
        req_db = None
        if req_id_str:
            req_db = session.exec(
                select(Requirement).where(
                    Requirement.project_id == project_id,
                    Requirement.req_id == req_id_str
                )
            ).first()

        issue = Issue(
            project_id=project_id,
            requirement_id=req_db.id if req_db else None,
            issue_id=iss.issue_id,
            issue_type=iss.issue_type,
            severity=iss.severity,
            involved_req_ids=json.dumps(iss.involved_req_ids),
            description=iss.description,
            suggested_question=iss.suggested_question,
            status=iss.status,
        )
        session.add(issue)
    session.commit()

    blocking = sum(1 for i in issues_out if i.severity == IssueSeverity.blocking and i.status == IssueStatus.open)
    return {
        "issue_count": len(issues_out),
        "blocking_count": blocking,
        "issues": [i.model_dump() for i in issues_out],
    }


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/issues", response_model=List[IssueOut])
def get_issues(project_id: int, session: Session = Depends(get_session)):
    issues = session.exec(select(Issue).where(Issue.project_id == project_id)).all()
    return [_issue_to_out(i) for i in issues]


def _issue_to_out(i: Issue) -> IssueOut:
    return IssueOut(
        issue_id=i.issue_id,
        issue_type=i.issue_type,
        severity=i.severity,
        involved_req_ids=json.loads(i.involved_req_ids),
        description=i.description,
        suggested_question=i.suggested_question,
        status=i.status,
        answer=i.answer,
        assumption=i.assumption,
    )


@router.post("/issues/{issue_id}/answer")
def answer_issue(issue_id: str, body: AnswerRequest, session: Session = Depends(get_session)):
    issue = session.exec(select(Issue).where(Issue.issue_id == issue_id)).first()
    if not issue:
        raise HTTPException(404, f"Issue {issue_id} not found")

    issue.status = IssueStatus.answered
    issue.answer = body.answer
    issue.answered_at = datetime.now(timezone.utc)
    session.add(issue)

    # Log decision
    log = DecisionLog(
        project_id=issue.project_id,
        issue_id=issue_id,
        question=issue.suggested_question,
        answer=body.answer,
        resolved_at=datetime.now(timezone.utc),
    )
    session.add(log)
    session.commit()

    return {"issue_id": issue_id, "status": "answered"}


@router.post("/issues/{issue_id}/assume")
def assume_issue(issue_id: str, body: AssumeRequest, session: Session = Depends(get_session)):
    issue = session.exec(select(Issue).where(Issue.issue_id == issue_id)).first()
    if not issue:
        raise HTTPException(404, f"Issue {issue_id} not found")

    issue.status = IssueStatus.assumed
    issue.assumption = body.assumption
    issue.answered_at = datetime.now(timezone.utc)
    session.add(issue)

    log = DecisionLog(
        project_id=issue.project_id,
        issue_id=issue_id,
        question=issue.suggested_question,
        assumption=body.assumption,
        resolved_at=datetime.now(timezone.utc),
    )
    session.add(log)
    session.commit()

    return {"issue_id": issue_id, "status": "assumed", "assumption": body.assumption}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/generate")
def generate_artifacts(project_id: int, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    issues_db = session.exec(select(Issue).where(Issue.project_id == project_id)).all()
    issues_out = [_issue_to_out(i) for i in issues_db]

    if clarifier.has_blocking_issues(issues_out):
        blocking = [i.issue_id for i in issues_out if i.severity == IssueSeverity.blocking and i.status == IssueStatus.open]
        raise HTTPException(400, f"Cannot generate: blocking issues still open: {blocking}")

    reqs_db = session.exec(select(Requirement).where(Requirement.project_id == project_id)).all()
    from backend.models import ParsedRequirement, ParseResult, ConstraintSchema
    parsed_reqs = []
    for r in reqs_db:
        constraints_raw = json.loads(r.constraints)
        constraints = [ConstraintSchema(**c) for c in constraints_raw]
        parsed_reqs.append(ParsedRequirement(
            req_id=r.req_id,
            text=r.text,
            source_sentence=r.source_sentence,
            entities=json.loads(r.entities),
            actions=json.loads(r.actions),
            constraints=constraints,
        ))
    parse_result = ParseResult(requirements=parsed_reqs)
    req_ids = [r.req_id for r in parsed_reqs]

    # Generate
    artifacts_out = generator.generate_all(parse_result, issues_out)

    # Validate + repair
    artifacts_out = validators.validate_and_repair(artifacts_out, req_ids)

    # Delete old artifacts
    old = session.exec(select(Artifact).where(Artifact.project_id == project_id)).all()
    for a in old:
        session.delete(a)
    # Delete old trace links
    old_links = session.exec(select(TraceLink).where(TraceLink.project_id == project_id)).all()
    for l in old_links:
        session.delete(l)
    session.commit()

    # Save artifacts + trace links
    for art in artifacts_out:
        db_art = Artifact(
            project_id=project_id,
            artifact_type=art.artifact_type,
            content=art.content,
            is_valid=art.is_valid,
            validation_errors=json.dumps(art.validation_errors),
        )
        session.add(db_art)

    # Build and save trace links
    links = traceability.build_trace_links(artifacts_out, req_ids)
    for link in links:
        tl = TraceLink(
            project_id=project_id,
            req_id=link.req_id,
            artifact_type=link.artifact_type,
            item_id=link.item_id,
            item_label=link.item_label,
        )
        session.add(tl)

    session.commit()

    return {
        "artifacts_generated": len(artifacts_out),
        "artifacts": [a.model_dump() for a in artifacts_out],
        "trace_links": len(links),
    }


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/artifacts", response_model=List[ArtifactOut])
def get_artifacts(project_id: int, session: Session = Depends(get_session)):
    arts = session.exec(select(Artifact).where(Artifact.project_id == project_id)).all()
    return [ArtifactOut(
        artifact_type=a.artifact_type,
        content=a.content,
        is_valid=a.is_valid,
        validation_errors=json.loads(a.validation_errors),
    ) for a in arts]


# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/traceability", response_model=TraceabilityOut)
def get_traceability(project_id: int, session: Session = Depends(get_session)):
    links_db = session.exec(select(TraceLink).where(TraceLink.project_id == project_id)).all()
    links_out = [TraceLinkOut(
        req_id=l.req_id,
        artifact_type=l.artifact_type,
        item_id=l.item_id,
        item_label=l.item_label,
    ) for l in links_db]

    reqs_db = session.exec(select(Requirement).where(Requirement.project_id == project_id)).all()
    req_ids = [r.req_id for r in reqs_db]

    uncovered = traceability.get_uncovered_requirements(links_out, req_ids)
    coverage = (len([r for r in req_ids if r not in uncovered]) / len(req_ids) * 100) if req_ids else 100.0

    logs_db = session.exec(select(DecisionLog).where(DecisionLog.project_id == project_id)).all()
    decision_log = [
        {
            "issue_id": l.issue_id,
            "question": l.question,
            "answer": l.answer,
            "assumption": l.assumption,
            "resolved_at": l.resolved_at.isoformat(),
        }
        for l in logs_db
    ]

    return TraceabilityOut(
        links=links_out,
        uncovered_req_ids=uncovered,
        coverage_pct=coverage,
        decision_log=decision_log,
    )


# ---------------------------------------------------------------------------
# Export (ZIP)
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/export")
def export_project(project_id: int, session: Session = Depends(get_session)):
    from fastapi.responses import StreamingResponse
    arts = session.exec(select(Artifact).where(Artifact.project_id == project_id)).all()
    if not arts:
        raise HTTPException(404, "No artifacts found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for art in arts:
            if art.artifact_type == ArtifactType.openapi:
                zf.writestr("openapi.yaml", art.content)
            elif art.artifact_type == ArtifactType.sql_ddl:
                zf.writestr("schema.sql", art.content)
            elif art.artifact_type == ArtifactType.test_plan:
                zf.writestr("test_plan.json", art.content)

        # Add traceability
        links_db = session.exec(select(TraceLink).where(TraceLink.project_id == project_id)).all()
        trace_data = [{"req_id": l.req_id, "artifact_type": l.artifact_type,
                       "item_id": l.item_id, "item_label": l.item_label} for l in links_db]
        zf.writestr("traceability.json", json.dumps(trace_data, indent=2))

        # Add decision log
        logs_db = session.exec(select(DecisionLog).where(DecisionLog.project_id == project_id)).all()
        log_data = [{"issue_id": l.issue_id, "question": l.question,
                     "answer": l.answer, "assumption": l.assumption} for l in logs_db]
        zf.writestr("decision_log.json", json.dumps(log_data, indent=2))

    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename=synapse-project-{project_id}.zip"})


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@router.post("/evaluate")
def run_evaluation():
    """Run the evaluation suite and return metrics."""
    try:
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "eval/run_eval.py"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            # Try to load the saved report
            try:
                with open("eval/eval_report.json", encoding="utf-8") as f:
                    report = json.load(f)
                return report
            except Exception:
                return {"output": result.stdout, "status": "ok"}
        else:
            return {"error": result.stderr, "status": "error"}
    except Exception as e:
        return {"error": str(e), "status": "error"}

