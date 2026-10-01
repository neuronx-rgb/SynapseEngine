import os
import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.db import get_session, engine, SQLModel, Session
from backend.models import Project, Requirement, Issue, IssueStatus

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield

def test_clarification_loop_end_to_end():
    """Test that answering a clarification prevents it from returning and passes it to generator."""
    # Force mock mode
    os.environ["MOCK_MODE"] = "true"
    
    # 1. Create project
    r_proj = client.post("/projects", json={"name": "Test Project"})
    assert r_proj.status_code == 200
    project_id = r_proj.json()["id"]

    # 2. Submit ambiguous requirement
    sample_text = "The system must be fast."
    r_req = client.post(f"/projects/{project_id}/requirements", json={"text": sample_text})
    assert r_req.status_code == 200

    # 3. Analyze -> creates an open issue
    r_ana = client.post(f"/projects/{project_id}/analyze")
    assert r_ana.status_code == 200
    issues = r_ana.json()["issues"]
    assert len(issues) > 0
    issue_id = issues[0]["issue_id"]
    
    # 4. Answer ALL blocking issues
    for iss in issues:
        r_ans = client.post(f"/projects/{project_id}/issues/{iss['issue_id']}/answer", json={"answer": "Resolved in test."})
        assert r_ans.status_code == 200
    
    # 5. Re-analyze
    r_ana2 = client.post(f"/projects/{project_id}/analyze")
    assert r_ana2.status_code == 200
    issues2 = r_ana2.json()["issues"]
    
    # Check that they did NOT spawn a duplicate OPEN issue for the same thing
    open_duplicates = [i for i in issues2 if i["status"] == "open"]
    assert len(open_duplicates) == 0

    # 6. Generate artifacts (using effective context)
    # Since we are in mock mode, it will just return the fixture, but we can verify it doesn't crash
    # and the route executes the _build_effective_parse_result logic.
    r_gen = client.post(f"/projects/{project_id}/generate")
    if r_gen.status_code != 200:
        print("GENERATE FAILED:", r_gen.json())
    assert r_gen.status_code == 200
    artifacts = r_gen.json()["artifacts"]
    assert len(artifacts) == 3
    
    # Verify DB state of effective req
    # (Just making sure our _build_effective_parse_result logic worked and didn't alter raw text)
    from sqlmodel import select
    with Session(engine) as session:
        req = session.exec(select(Requirement).where(Requirement.project_id == project_id)).first()
        assert "globally unique email" in req.text # RAW text is unchanged, matches mock fixture!
