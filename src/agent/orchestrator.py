"""Deterministic Agent Orchestrator for AI Code Review."""

import logging
from typing import Any, Dict, List, Optional
from pydantic import ValidationError

from src.agent.gemini_client import (
    GeminiAuthError,
    GeminiClient,
    GeminiClientError,
)
from src.agent.mock_analyzer import MockStaticAnalyzer
from src.agent.ollama_client import (
    OllamaClient,
    OllamaClientError,
    OllamaConnectionError,
    OllamaModelNotFoundError,
)
from src.agent.prompt import SYSTEM_PROMPT, build_review_prompt
from src.config import settings
from src.models.schemas import (
    CodeReviewResult,
    ReviewRecommendation,
)
from src.tools.git_tools import (
    GitToolError,
    get_changed_files,
    get_file_context,
    get_git_diff,
)
from src.tools.validator import validate_review

logger = logging.getLogger("code_review_agent")


class AgentOrchestrator:
    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        ollama_client: Optional[OllamaClient] = None,
        mock_analyzer: Optional[MockStaticAnalyzer] = None,
    ):
        self.gemini = gemini_client or GeminiClient()
        self.ollama = ollama_client or OllamaClient()
        self.mock_analyzer = mock_analyzer or MockStaticAnalyzer()

    def resolve_provider(
        self,
        requested_provider: Optional[str] = None,
        api_key: Optional[str] = None,
        force_mock: bool = False,
    ) -> str:
        """Resolve which provider engine to use."""
        if force_mock:
            return "heuristic"

        prov = (requested_provider or settings.default_provider or "auto").lower().strip()
        if prov in ("heuristic", "mock"):
            return "heuristic"

        if prov == "gemini":
            return "gemini"

        if prov == "ollama":
            return "ollama"

        # Auto detection: prefer Gemini if API key is present; then Ollama if online; else heuristic
        if self.gemini.is_available(api_key=api_key):
            return "gemini"
        if self.ollama.is_available():
            return "ollama"

        return "heuristic"

    def review_diff(
        self,
        diff: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        context_notes: Optional[str] = None,
        repo_path: Optional[str] = None,
        force_mock: bool = False,
    ) -> CodeReviewResult:
        """
        Orchestrate end-to-end code review for a given diff string.
        """
        warnings: List[str] = []

        # Step 1: Input sanity check
        if not diff or not diff.strip():
            return CodeReviewResult(
                summary="Empty diff provided. No changes detected to review.",
                recommendation=ReviewRecommendation.APPROVE,
                findings=[],
                missing_test_suggestions=[],
                analyzer_backend="rule-engine-noop",
                warnings=["The provided Git diff contains no changes."],
            )

        # Step 2: Guard against oversized diffs
        original_len = len(diff.encode("utf-8"))
        if original_len > settings.max_diff_bytes:
            truncated_diff = diff[: settings.max_diff_bytes]
            last_newline = truncated_diff.rfind("\n")
            if last_newline != -1:
                truncated_diff = truncated_diff[:last_newline]
            diff = truncated_diff
            warning_msg = (
                f"Diff exceeded maximum allowed size ({original_len} bytes > {settings.max_diff_bytes} bytes). "
                "Truncated for review."
            )
            warnings.append(warning_msg)
            logger.warning(warning_msg)

        # Step 3: Parse changed files tool
        changed_files_info = get_changed_files(diff)
        changed_file_names = [f["file_path"] for f in changed_files_info]

        # Step 4: Retrieve file and test context tool
        file_context: Dict[str, str] = {}
        if repo_path and changed_file_names:
            try:
                file_context = get_file_context(
                    repo_path=repo_path,
                    changed_files=changed_file_names,
                    max_lines=settings.max_file_context_lines,
                )
            except Exception as e:
                logger.warning("Failed retrieving file context: %s", e)

        # Step 5: Determine provider and invoke engine
        chosen_provider = self.resolve_provider(
            requested_provider=provider,
            api_key=api_key,
            force_mock=force_mock,
        )

        review_result: Optional[CodeReviewResult] = None
        user_prompt: Optional[str] = None

        def get_prompt() -> str:
            nonlocal user_prompt
            if user_prompt is None:
                user_prompt = build_review_prompt(
                    diff=diff,
                    changed_files=changed_files_info,
                    file_context=file_context,
                    context_notes=context_notes,
                )
            return user_prompt

        # Attempt Gemini
        if chosen_provider == "gemini":
            try:
                target_model = model or settings.gemini_model
                raw_json = self.gemini.generate(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=get_prompt(),
                    model=target_model,
                    api_key=api_key,
                )
                raw_json["analyzer_backend"] = f"gemini:{target_model}"
                raw_json.setdefault("warnings", []).extend(warnings)
                review_result = CodeReviewResult.model_validate(raw_json)
            except (GeminiAuthError, GeminiClientError, ValidationError) as err:
                logger.error("Gemini execution error: %s", err)
                if not settings.enable_offline_fallback:
                    raise
                warnings.append(
                    f"Gemini Analyzer unavailable ({type(err).__name__}: {str(err)}). "
                    "Fell back to local deterministic static analysis engine."
                )
                chosen_provider = "heuristic"

        # Attempt Ollama
        elif chosen_provider == "ollama":
            try:
                target_model = model or self.ollama.default_model
                raw_json = self.ollama.generate(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=get_prompt(),
                    model=target_model,
                )
                raw_json["analyzer_backend"] = f"ollama:{target_model}"
                raw_json.setdefault("warnings", []).extend(warnings)
                review_result = CodeReviewResult.model_validate(raw_json)
            except (OllamaConnectionError, OllamaModelNotFoundError, OllamaClientError, ValidationError) as err:
                logger.error("Ollama execution error: %s", err)
                if not settings.enable_offline_fallback:
                    raise
                warnings.append(
                    f"Ollama Analyzer unavailable ({type(err).__name__}: {str(err)}). "
                    "Fell back to local deterministic static analysis engine."
                )
                chosen_provider = "heuristic"

        # Deterministic Heuristic Fallback
        if chosen_provider == "heuristic" or review_result is None:
            review_result = self.mock_analyzer.analyze(
                diff=diff,
                changed_files=changed_files_info,
                file_context=file_context,
            )
            review_result.warnings.extend(warnings)

        # Step 6: Deterministic post-validation tool
        validated_result = validate_review(
            review=review_result,
            diff=diff,
            changed_files_info=changed_files_info,
        )
        return validated_result

    def review_repository(
        self,
        repo_path: str,
        base_ref: str = "HEAD~1",
        head_ref: str = "HEAD",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        force_mock: bool = False,
    ) -> CodeReviewResult:
        """
        Orchestrate code review for a local Git repository comparison.
        """
        try:
            diff_text = get_git_diff(
                repo_path=repo_path,
                base_ref=base_ref,
                head_ref=head_ref,
            )
        except (GitToolError, ValueError) as e:
            raise e

        return self.review_diff(
            diff=diff_text,
            provider=provider,
            model=model,
            api_key=api_key,
            context_notes=f"Git repository comparison: base={base_ref}, head={head_ref}",
            repo_path=repo_path,
            force_mock=force_mock,
        )
