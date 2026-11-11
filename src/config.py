"""Configuration settings for AI Code Review Agent."""

import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file if present in project root
load_dotenv()


class Settings(BaseModel):
    # Provider selection: auto, gemini, ollama, heuristic
    default_provider: str = Field(
        default=os.getenv("DEFAULT_PROVIDER", "auto")
    )

    # Google Gemini settings
    gemini_api_key: Optional[str] = Field(
        default=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    )
    gemini_model: str = Field(
        default=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    )

    # Ollama settings
    ollama_base_url: str = Field(
        default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = Field(
        default=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:latest")
    )
    ollama_timeout_seconds: float = Field(
        default=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60.0"))
    )

    # Agent constraints
    max_diff_bytes: int = Field(
        default=int(os.getenv("MAX_DIFF_BYTES", "1048576"))  # 1MB
    )
    max_file_context_lines: int = Field(
        default=int(os.getenv("MAX_FILE_CONTEXT_LINES", "150"))
    )
    
    # Fallback to local heuristic engine if LLM provider is unreachable
    enable_offline_fallback: bool = Field(
        default=os.getenv("ENABLE_OFFLINE_FALLBACK", "true").lower() in ("true", "1", "yes")
    )

    # Server settings
    api_host: str = Field(default=os.getenv("API_HOST", "127.0.0.1"))
    api_port: int = Field(default=int(os.getenv("API_PORT", "8000")))


settings = Settings()
