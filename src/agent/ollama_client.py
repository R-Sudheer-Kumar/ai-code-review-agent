"""Ollama API client for interacting with local LLMs (Qwen2.5-Coder)."""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
from src.agent.json_utils import extract_json_payload
from src.config import settings


class OllamaClientError(Exception):
    """Base exception for Ollama errors."""
    pass


class OllamaConnectionError(OllamaClientError):
    """Raised when Ollama server is unreachable."""
    pass


class OllamaModelNotFoundError(OllamaClientError):
    """Raised when the specified model is not downloaded in Ollama."""
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout_seconds

    def is_available(self) -> bool:
        """Check if Ollama service is reachable."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """List models installed in local Ollama instance."""
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return [m.get("name") for m in data.get("models", []) if "name" in m]
        except Exception:
            pass
        return []

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to Ollama with JSON mode enabled.
        
        Args:
            system_prompt: Guiding system rules and schema.
            user_prompt: Fenced diff and context.
            model: Model name override (defaults to settings.ollama_model).
            
        Returns:
            Parsed JSON dict from Ollama's response.
        """
        target_model = model or self.default_model
        endpoint = f"{self.base_url}/api/chat"

        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(endpoint, json=payload)
        except httpx.ConnectError as e:
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {self.base_url}. Ensure Ollama is running (`ollama serve`)."
            ) from e
        except httpx.TimeoutException as e:
            raise OllamaClientError(
                f"Ollama request timed out after {self.timeout}s while generating with model {target_model}."
            ) from e
        except Exception as e:
            raise OllamaClientError(f"Unexpected error communicating with Ollama: {str(e)}") from e

        if response.status_code == 404:
            raise OllamaModelNotFoundError(
                f"Model '{target_model}' not found in Ollama. Run `ollama pull {target_model}`."
            )
        elif response.status_code != 200:
            raise OllamaClientError(
                f"Ollama returned HTTP {response.status_code}: {response.text}"
            )

        resp_json = response.json()
        raw_content = resp_json.get("message", {}).get("content", "")
        return self._extract_json(raw_content)

    @staticmethod
    def _extract_json(content: str) -> Dict[str, Any]:
        """Extract and parse JSON safely from raw LLM output."""
        try:
            return extract_json_payload(content)
        except ValueError as e:
            raise OllamaClientError(str(e)) from e
