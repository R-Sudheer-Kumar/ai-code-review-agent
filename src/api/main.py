"""FastAPI backend service for AI Code Review Agent."""

import subprocess
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from src.agent.gemini_client import (
    GeminiAuthError,
    GeminiClient,
    GeminiClientError,
)
from src.agent.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaModelNotFoundError,
)
from src.agent.orchestrator import AgentOrchestrator
from src.config import settings
from src.models.schemas import (
    CodeReviewResult,
    HealthResponse,
    ReviewDiffRequest,
    ReviewRepoRequest,
)
from src.tools.git_tools import GitToolError

app = FastAPI(
    title="AI Code Review Agent API",
    description="Agentic code review service leveraging local LLMs (Qwen2.5-Coder) and deterministic static analysis.",
    version="1.0.0",
)

# Enable CORS for local Streamlit and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = AgentOrchestrator()


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check API health, Gemini & Ollama connectivity, and Git CLI availability."""
    ollama = OllamaClient()
    ollama_ok = ollama.is_available()

    gemini = GeminiClient()
    gemini_ok = gemini.is_available()

    git_ok = False
    try:
        git_check = subprocess.run(["git", "--version"], capture_output=True, text=True)
        git_ok = git_check.returncode == 0
    except Exception:
        git_ok = False

    return HealthResponse(
        status="healthy",
        ollama_connected=ollama_ok,
        ollama_url=settings.ollama_base_url,
        default_model=settings.ollama_model,
        gemini_configured=gemini_ok,
        gemini_model=settings.gemini_model,
        git_available=git_ok,
    )


@app.post("/review/diff", response_model=CodeReviewResult)
def review_diff_endpoint(request: ReviewDiffRequest) -> CodeReviewResult:
    """
    Review code changes provided as a raw unified Git diff.
    """
    try:
        result = orchestrator.review_diff(
            diff=request.diff,
            provider=request.provider,
            model=request.model,
            api_key=request.api_key,
            context_notes=request.context_notes,
        )
        return result
    except GeminiAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except (OllamaConnectionError, OllamaModelNotFoundError, GeminiClientError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review failed: {str(e)}",
        )


@app.post("/review/repository", response_model=CodeReviewResult)
def review_repository_endpoint(request: ReviewRepoRequest) -> CodeReviewResult:
    """
    Review code changes between two Git refs in a local repository directory.
    """
    try:
        result = orchestrator.review_repository(
            repo_path=request.repo_path,
            base_ref=request.base_ref,
            head_ref=request.head_ref,
            provider=request.provider,
            model=request.model,
            api_key=request.api_key,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except GitToolError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except GeminiAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except (OllamaConnectionError, OllamaModelNotFoundError, GeminiClientError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Repository review failed: {str(e)}",
        )
