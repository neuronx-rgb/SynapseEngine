"""
backend/pipeline/clarifier.py
Issue clarification loop:
- One targeted question per open issue
- Answer updates requirement text, re-analyzes affected requirements
- "Assume default" logs in decision log, marks issue assumed
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from backend.models import IssueOut, IssueStatus, IssueSeverity


def has_blocking_issues(issues: List[IssueOut]) -> bool:
    """Return True if any issue is blocking and open."""
    return any(
        i.severity == IssueSeverity.blocking and i.status == IssueStatus.open
        for i in issues
    )


def get_open_issues(issues: List[IssueOut]) -> List[IssueOut]:
    return [i for i in issues if i.status == IssueStatus.open]


def get_blocking_open(issues: List[IssueOut]) -> List[IssueOut]:
    return [i for i in issues if i.status == IssueStatus.open and i.severity == IssueSeverity.blocking]


def apply_answer(issue: IssueOut, answer: str) -> IssueOut:
    """Mark issue as answered with given answer text."""
    return issue.model_copy(update={"status": IssueStatus.answered, "answer": answer})


def apply_assumption(issue: IssueOut, assumption: str = "default behavior assumed") -> IssueOut:
    """Mark issue as assumed with given assumption text."""
    return issue.model_copy(update={
        "status": IssueStatus.assumed,
        "assumption": assumption,
    })


def build_decision_log_entry(issue: IssueOut) -> dict:
    """Create a decision log entry for an answered/assumed issue."""
    return {
        "issue_id": issue.issue_id,
        "issue_type": issue.issue_type,
        "question": issue.suggested_question,
        "answer": issue.answer,
        "assumption": issue.assumption,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }

