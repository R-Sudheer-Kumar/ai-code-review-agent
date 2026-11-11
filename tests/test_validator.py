"""Unit tests for review output validator tool."""

from src.models.schemas import (
    CodeReviewResult,
    FindingCategory,
    FindingSeverity,
    ReviewFinding,
    ReviewRecommendation,
)
from src.tools.validator import validate_review

SAMPLE_DIFF = """diff --git a/src/service.py b/src/service.py
index abc..def 100644
--- a/src/service.py
+++ b/src/service.py
@@ -10,4 +10,6 @@ def process():
+    user_input = request.get('q')
+    db.execute("SELECT * FROM " + user_input)
"""


def test_validator_detects_unmodified_files():
    # Model hallucinated a file "unrelated/phantom.py"
    finding = ReviewFinding(
        category=FindingCategory.BUG,
        severity=FindingSeverity.MEDIUM,
        title="Phantom issue",
        file_path="unrelated/phantom.py",
        line_start=1,
        description="Issue reported on non-existent file",
        impact="Theoretical defect in referenced module",
        suggested_fix="Verify referenced file path in codebase",
        confidence=0.9,
    )
    review = CodeReviewResult(
        summary="Review with phantom file",
        recommendation=ReviewRecommendation.APPROVE,
        findings=[finding],
    )

    validated = validate_review(review, SAMPLE_DIFF)
    assert len(validated.warnings) > 0
    assert "was not modified in this diff" in validated.warnings[0]
    # Confidence should be penalized
    assert validated.findings[0].confidence < 0.9


def test_validator_overrides_approve_when_critical_finding_present():
    finding = ReviewFinding(
        category=FindingCategory.SECURITY,
        severity=FindingSeverity.CRITICAL,
        title="SQL injection vulnerability",
        file_path="src/service.py",
        line_start=11,
        description="Direct string concatenation in SQL query",
        impact="Critical database compromise",
        suggested_fix="Use parameterized queries",
        confidence=0.95,
    )
    # LLM mistakenly recommended approve
    review = CodeReviewResult(
        summary="Looks mostly good",
        recommendation=ReviewRecommendation.APPROVE,
        findings=[finding],
    )

    validated = validate_review(review, SAMPLE_DIFF)
    assert validated.recommendation == ReviewRecommendation.REQUEST_CHANGES
    assert any("overridden to 'request_changes'" in w for w in validated.warnings)


def test_validator_flags_line_numbers_outside_hunk():
    finding = ReviewFinding(
        category=FindingCategory.STYLE,
        severity=FindingSeverity.LOW,
        title="Style issue on line 999",
        file_path="src/service.py",
        line_start=999,  # Line 999 is outside the hunk 10-16
        description="Whitespace anomaly on line 999",
        impact="Minor",
        suggested_fix="Format line",
        confidence=0.8,
    )
    review = CodeReviewResult(
        summary="Review with line outside range",
        recommendation=ReviewRecommendation.APPROVE,
        findings=[finding],
    )

    validated = validate_review(review, SAMPLE_DIFF)
    assert "outside the explicit hunk range" in validated.findings[0].description
    assert validated.findings[0].confidence < 0.8
