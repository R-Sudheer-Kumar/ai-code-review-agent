"""Google Gemini API client using the official google-genai SDK."""

from typing import Any, Dict, Optional
from google import genai
from google.genai import types

from src.agent.json_utils import extract_json_payload
from src.config import settings


class GeminiClientError(Exception):
    """Base exception for Gemini API errors."""
    pass


class GeminiAuthError(GeminiClientError):
    """Raised when Gemini API key is missing or invalid."""
    pass


class GeminiClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        self.api_key = (api_key or settings.gemini_api_key or "").strip() or None
        self.default_model = default_model or settings.gemini_model

    def is_available(self, api_key: Optional[str] = None) -> bool:
        """Check whether a Gemini API key is configured."""
        effective_key = (api_key or self.api_key or "").strip()
        return bool(effective_key)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a code review prompt to Google Gemini with structured JSON output.

        Args:
            system_prompt: Guiding system rules and JSON schema.
            user_prompt: Fenced diff and context.
            model: Optional Gemini model name override.
            api_key: Optional Gemini API key override.

        Returns:
            Parsed JSON dict from Gemini's response.
        """
        effective_key = (api_key or self.api_key or "").strip()
        if not effective_key:
            raise GeminiAuthError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in .env or provide it in the UI."
            )

        target_model = model or self.default_model

        try:
            client = genai.Client(api_key=effective_key)
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
                response_mime_type="application/json",
            )
            response = client.models.generate_content(
                model=target_model,
                contents=user_prompt,
                config=config,
            )
        except Exception as e:
            err_msg = str(e)
            # Redact key if somehow echoed by SDK
            if effective_key in err_msg:
                err_msg = err_msg.replace(effective_key, "***")
            if "API_KEY_INVALID" in err_msg or "401" in err_msg or "403" in err_msg:
                raise GeminiAuthError(f"Gemini authentication failed: {err_msg}") from e
            raise GeminiClientError(
                f"Gemini API error ({target_model}): {err_msg}"
            ) from e

        raw_text = getattr(response, "text", None) or ""
        if not raw_text.strip():
            raise GeminiClientError(f"Gemini ({target_model}) returned an empty response.")

        try:
            return extract_json_payload(raw_text)
        except ValueError as e:
            raise GeminiClientError(str(e)) from e
