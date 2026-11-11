"""Pydantic schemas and data models for AI Code Review Agent."""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class FindingCategory(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MISSING_TEST = "missing_test"
    STYLE = "style"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewRecommendation(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class ReviewFinding(BaseModel):
    category: FindingCategory = Field(
        ...,
        description="Category: bug, security, performance, missing_test, or style",
    )
    severity: FindingSeverity = Field(
        ...,
        description="Severity level: critical, high, medium, or low",
    )
    title: str = Field(..., min_length=3, max_length=150, description="Concise summary of the finding")
    file_path: str = Field(..., description="Target file path referenced in the diff")
    line_start: Optional[int] = Field(None, ge=1, description="Start line of changed code")
    line_end: Optional[int] = Field(None, ge=1, description="End line of changed code")
    description: str = Field(..., min_length=10, description="Detailed explanation of the issue")
    impact: str = Field(..., min_length=5, description="Potential operational, security or runtime impact")
    suggested_fix: str = Field(..., min_length=5, description="Clear, actionable code or architecture fix")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Model confidence score between 0.0 (uncertain) and 1.0 (verified)",
    )

    @field_validator("line_end")
    @classmethod
    def validate_line_range(cls, v: Optional[int], info) -> Optional[int]:
        line_start = info.data.get("line_start")
        if v is not None and line_start is not None and v < line_start:
            return line_start
        return v


class CodeReviewResult(BaseModel):
    summary: str = Field(..., min_length=10, description="High-level narrative review summary")
    recommendation: ReviewRecommendation = Field(
        ...,
        description="Review decision: approve, request_changes, or needs_manual_review",
    )
    counts_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Finding counts indexed by category",
    )
    counts_by_severity: Dict[str, int] = Field(
        default_factory=dict,
        description="Finding counts indexed by severity",
    )
    findings: List[ReviewFinding] = Field(
        default_factory=list,
        description="Individual review findings",
    )
    missing_test_suggestions: List[str] = Field(
        default_factory=list,
        description="Actionable suggestions for missing unit or integration tests",
    )
    analyzer_backend: str = Field(
        default="qwen2.5-coder",
        description="LLM model or heuristic analyzer that produced the review",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Operational warnings (e.g. truncated diff, fallback used)",
    )

    @model_validator(mode="after")
    def compute_counts(self) -> "CodeReviewResult":
        # Recalculate category and severity counts deterministically
        cat_counts: Dict[str, int] = {cat.value: 0 for cat in FindingCategory}
        sev_counts: Dict[str, int] = {sev.value: 0 for sev in FindingSeverity}

        for f in self.findings:
            cat_val = f.category.value if isinstance(f.category, FindingCategory) else str(f.category)
            sev_val = f.severity.value if isinstance(f.severity, FindingSeverity) else str(f.severity)

            cat_counts[cat_val] = cat_counts.get(cat_val, 0) + 1
            sev_counts[sev_val] = sev_counts.get(sev_val, 0) + 1

        self.counts_by_category = cat_counts
        self.counts_by_severity = sev_counts
        return self


# API Request/Response Schemas
class ReviewDiffRequest(BaseModel):
    diff: str = Field(default="", description="Raw Unified Git Diff text")
    provider: Optional[str] = Field(None, description="Model provider: auto, gemini, ollama, or heuristic")
    model: Optional[str] = Field(None, description="Optional model override")
    api_key: Optional[str] = Field(None, description="Optional API key override (e.g. Gemini API key)")
    context_notes: Optional[str] = Field(None, description="Optional extra pull request description or context")


class ReviewRepoRequest(BaseModel):
    repo_path: str = Field(..., min_length=1, description="Local path to Git repository")
    base_ref: str = Field(default="HEAD~1", description="Base commit / branch ref")
    head_ref: str = Field(default="HEAD", description="Target commit / branch ref")
    provider: Optional[str] = Field(None, description="Model provider: auto, gemini, ollama, or heuristic")
    model: Optional[str] = Field(None, description="Optional model override")
    api_key: Optional[str] = Field(None, description="Optional API key override (e.g. Gemini API key)")


class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    ollama_url: str
    default_model: str
    gemini_configured: bool
    gemini_model: str
    git_available: bool
