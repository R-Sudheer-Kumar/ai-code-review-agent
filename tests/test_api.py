"""API endpoint tests for FastAPI backend."""

import pytest
from fastapi.testclient import TestClient

from sample_data.synthetic_repo_builder import create_synthetic_buggy_repo
from src.api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "ollama_connected" in data
    assert "git_available" in data
    assert data["git_available"] is True


def test_review_diff_endpoint_empty():
    response = client.post("/review/diff", json={"diff": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["recommendation"] == "approve"
    assert len(data["findings"]) == 0


def test_review_diff_endpoint_with_issues():
    diff_payload = {
        "diff": """diff --git a/app.py b/app.py
new file mode 100644
--- /dev/null
+++ b/app.py
@@ -0,0 +1,5 @@
+API_KEY = "demo_dummy_secret_998877665544"
+def divide(a, b):
+    return a / 0
+"""
    }
    response = client.post("/review/diff", json=diff_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["recommendation"] == "request_changes"
    assert len(data["findings"]) >= 1


def test_review_repository_endpoint(tmp_path):
    repo_dir = create_synthetic_buggy_repo(tmp_path / "api_test_repo")
    payload = {
        "repo_path": str(repo_dir),
        "base_ref": "HEAD~1",
        "head_ref": "HEAD",
    }
    response = client.post("/review/repository", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["recommendation"] == "request_changes"
    assert len(data["findings"]) >= 2


def test_review_repository_endpoint_invalid_path():
    payload = {
        "repo_path": "invalid/path/that/does/not/exist/9999",
        "base_ref": "HEAD~1",
        "head_ref": "HEAD",
    }
    response = client.post("/review/repository", json=payload)
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]
