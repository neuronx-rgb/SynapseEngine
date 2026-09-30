"""
frontend/api_client.py
Thin httpx wrapper around the Synapse Engine backend.
Reads BACKEND_MODE (embedded|remote) and BACKEND_URL from env/st.secrets.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

# Config — read env first, then st.secrets if available
def _get_backend_url() -> str:
    url = os.getenv("BACKEND_URL", "")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("BACKEND_URL", "")
        except Exception:
            pass
    return url or "http://127.0.0.1:8000"


BACKEND_URL = _get_backend_url()
TIMEOUT = 60.0


class APIClient:
    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=TIMEOUT)

    def _get(self, path: str, **kwargs) -> Any:
        r = self._client.get(path, **kwargs)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json: Any = None, **kwargs) -> Any:
        r = self._client.post(path, json=json, **kwargs)
        r.raise_for_status()
        return r.json()

    # Health
    def health(self) -> dict:
        return self._get("/health")

    # Projects
    def create_project(self, name: str = "Untitled") -> dict:
        return self._post("/projects", json={"name": name})

    def list_projects(self) -> list:
        return self._get("/projects")

    def get_project(self, project_id: int) -> dict:
        return self._get(f"/projects/{project_id}")

    # Requirements
    def submit_requirements(self, project_id: int, text: str) -> dict:
        return self._post(f"/projects/{project_id}/requirements", json={"text": text})

    # Analysis
    def analyze(self, project_id: int) -> dict:
        return self._post(f"/projects/{project_id}/analyze")

    # Issues
    def get_issues(self, project_id: int) -> list:
        return self._get(f"/projects/{project_id}/issues")

    def answer_issue(self, issue_id: str, answer: str) -> dict:
        return self._post(f"/issues/{issue_id}/answer", json={"answer": answer})

    def assume_issue(self, issue_id: str, assumption: str = "default behavior assumed") -> dict:
        return self._post(f"/issues/{issue_id}/assume", json={"assumption": assumption})

    # Generation
    def generate(self, project_id: int) -> dict:
        return self._post(f"/projects/{project_id}/generate")

    # Artifacts
    def get_artifacts(self, project_id: int) -> list:
        return self._get(f"/projects/{project_id}/artifacts")

    # Traceability
    def get_traceability(self, project_id: int) -> dict:
        return self._get(f"/projects/{project_id}/traceability")

    # Export
    def export_url(self, project_id: int) -> str:
        return f"{self.base_url}/projects/{project_id}/export"

    # Evaluation
    def evaluate(self) -> dict:
        return self._post("/evaluate")


# Singleton
_client: Optional[APIClient] = None


def get_client() -> APIClient:
    global _client
    if _client is None:
        _client = APIClient()
    return _client
