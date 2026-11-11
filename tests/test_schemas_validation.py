"""Unit tests for Pydantic schemas and validations."""

import pytest
from pydantic import ValidationError

from src.models.schemas import (
    CodeReviewResult,
    FindingCategory,
    FindingSeverity,
    ReviewFinding,
    ReviewRecommendation,
)


def test_valid_review_finding():
    finding = ReviewFinding(
        category=FindingCategory.BUG,
        severity=FindingSeverity.HIGH,
        title="Zero division bug",
        file_path="app/math.py",
        line_start=10,
        line_end=12,
        description="Division by zero encountered in calculation",
        impact="Process crash",
        suggested_fix="Check denominator before dividing",
        confidence=0.95,
    )
    assert finding.title == "Zero division bug"
    assert finding.confidence == 0.95
    assert finding.line_end == 12


def test_line_range_auto_correction():
    # If line_end is less than line_start, it should be auto-corrected to line_start
    finding = ReviewFinding(
        category=FindingCategory.STYLE,
        severity=FindingSeverity.LOW,
        title="Formatting anomaly",
        file_path="app/main.py",
        line_start=20,
        line_end=15,
        description="Minor indent irregularity",
        impact="Code style inconsistency",
        suggested_fix="Reformat with black or ruff",
        confidence=0.7,
    )
    assert finding.line_end == 20


def test_invalid_category_fails():
    with pytest.raises(ValidationError):
        ReviewFinding(
            category="not_a_valid_category",  # Invalid enum
            severity=FindingSeverity.LOW,
            title="Some title",
            file_path="main.py",
            description="A description that is long enough",
            impact="Low impact",
            suggested_fix="Fix it",
        )


def test_confidence_range_validation():
    with pytest.raises(ValidationError):
        ReviewFinding(
            category=FindingCategory.BUG,
            severity=FindingSeverity.LOW,
            title="Some bug",
            file_path="main.py",
            description="A description that is long enough",
            impact="Low impact",
            suggested_fix="Fix it",
            confidence=1.5,  # Out of [0.0, 1.0]
        )


def test_code_review_result_computes_counts_automatically():
    findings = [
        ReviewFinding(
            category=FindingCategory.SECURITY,
            severity=FindingSeverity.CRITICAL,
            title="SQL injection",
            file_path="app/db.py",
            line_start=5,
            description="Unescaped query parameter",
            impact="Data leak",
            suggested_fix="Use parameterized query",
            confidence=0.99,
        ),
        ReviewFinding(
            category=FindingCategory.BUG,
            severity=FindingSeverity.HIGH,
            title="Index out of range",
            file_path="app/db.py",
            line_start=15,
            description="Array index without bounds check",
            impact="Crash",
            suggested_fix="Add len check",
            confidence=0.85,
        ),
    ]

    result = CodeReviewResult(
        summary="Review completed with critical issues.",
        recommendation=ReviewRecommendation.REQUEST_CHANGES,
        findings=findings,
        missing_test_suggestions=["Add integration tests for DB queries"],
    )

    # Verification of automatic category & severity count computation
    assert result.counts_by_category["security"] == 1
    assert result.counts_by_category["bug"] == 1
    assert result.counts_by_category["performance"] == 0
    assert result.counts_by_severity["critical"] == 1
    assert result.counts_by_severity["high"] == 1
    assert result.counts_by_severity["low"] == 0
