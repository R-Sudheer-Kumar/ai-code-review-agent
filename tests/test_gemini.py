"""Unit tests for Gemini API client and integration."""

from unittest.mock import MagicMock, patch
import pytest

from src.agent.gemini_client import (
    GeminiAuthError,
    GeminiClient,
    GeminiClientError,
)
from src.agent.orchestrator import AgentOrchestrator
from src.models.schemas import FindingCategory, ReviewRecommendation


def test_gemini_client_availability():
    client = GeminiClient(api_key=None)
    assert client.is_available() is False
    assert client.is_available(api_key="AIzaSyTestKey123") is True


def test_gemini_client_missing_key_raises_auth_error():
    client = GeminiClient(api_key="")
    with pytest.raises(GeminiAuthError, match="Gemini API key is not configured"):
        client.generate(system_prompt="sys", user_prompt="usr", api_key="")


@patch("src.agent.gemini_client.genai.Client")
def test_gemini_client_mock_generate_success(mock_client_cls):
    mock_response = MagicMock()
    mock_response.text = """
    {
      "summary": "Gemini analyzed diff and found critical vulnerabilities.",
      "recommendation": "request_changes",
      "findings": [
        {
          "category": "security",
          "severity": "critical",
          "title": "SQL Injection in User Query",
          "file_path": "backend/auth.py",
          "line_start": 8,
          "line_end": 8,
          "description": "Direct format string used in SQL query execution.",
          "impact": "Full database exfiltration risk",
          "suggested_fix": "Use db.execute('SELECT * FROM tbl WHERE id = %s', (val,))",
          "confidence": 0.98
        }
      ],
      "missing_test_suggestions": ["Add integration test for query injection payloads"]
    }
    """
    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_client_cls.return_value = mock_client_instance

    client = GeminiClient(api_key="fake-test-key")
    result = client.generate("system", "user")

    assert result["recommendation"] == "request_changes"
    assert len(result["findings"]) == 1
    assert result["findings"][0]["category"] == "security"


@patch("src.agent.gemini_client.genai.Client")
def test_orchestrator_with_gemini(mock_client_cls):
    mock_response = MagicMock()
    mock_response.text = """
    {
      "summary": "Changes approved by Gemini review.",
      "recommendation": "approve",
      "findings": [],
      "missing_test_suggestions": []
    }
    """
    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_client_cls.return_value = mock_client_instance

    orchestrator = AgentOrchestrator(
        gemini_client=GeminiClient(api_key="fake-test-key")
    )
    result = orchestrator.review_diff(
        diff="diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n",
        provider="gemini",
        api_key="fake-test-key",
    )
    assert result.recommendation == ReviewRecommendation.APPROVE
    assert "gemini" in result.analyzer_backend
