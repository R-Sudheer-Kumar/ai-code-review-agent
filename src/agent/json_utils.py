"""Shared JSON extraction utilities for LLM responses."""

import json
import re
from typing import Any, Dict


def extract_json_payload(content: str) -> Dict[str, Any]:
    """
    Extract and parse a JSON object safely from raw LLM output.
    Handles markdown code fences (```json ... ```) and surrounding chatter.
    """
    cleaned = (content or "").strip()

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            substring = cleaned[start : end + 1]
            return json.loads(substring)
        raise ValueError(f"Model response could not be parsed as JSON: {content[:200]}...")
