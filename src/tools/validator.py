"""Review validation and post-processing tools."""

from typing import Any, Dict, List, Optional
from src.models.schemas import (
    CodeReviewResult,
    FindingCategory,
    FindingSeverity,
    ReviewRecommendation,
)
from src.tools.git_tools import get_changed_files


def validate_review(
    review: CodeReviewResult,
    diff: str,
    changed_files_info: Optional[List[Dict[str, Any]]] = None,
) -> CodeReviewResult:
    """
    Validate the structured review against the actual Git diff.
    
    Verifies:
    1. Cited file paths exist in the diff.
    2. Line numbers correlate with actual modified line ranges.
    3. Recommendations logically correspond to finding severities.
    4. Categorization counts are mathematically sound.
    5. Hallucinated findings or phantom files are flagged.
    
    Args:
        review: Raw CodeReviewResult parsed from LLM.
        diff: Raw unified diff string.
        changed_files_info: Optional precomputed list from get_changed_files.
        
    Returns:
        Cleaned, validated, and normalized CodeReviewResult.
    """
    if changed_files_info is None:
        changed_files_info = get_changed_files(diff)

    valid_files_map = {
        info["file_path"].strip().replace("\\", "/"): info
        for info in changed_files_info
    }
    # Also index basenames for fuzzy matching if model dropped directory
    basename_map = {
        info["file_path"].split("/")[-1]: info["file_path"].replace("\\", "/")
        for info in changed_files_info
    }

    validated_findings = []
    warnings = list(review.warnings)

    for finding in review.findings:
        normalized_path = finding.file_path.strip().replace("\\", "/").lstrip("./")

        # Check if file path matches any known changed file
        if normalized_path not in valid_files_map:
            # Check basename
            bname = normalized_path.split("/")[-1]
            if bname in basename_map:
                normalized_path = basename_map[bname]
                finding.file_path = normalized_path
            else:
                warnings.append(
                    f"Finding '{finding.title}' referenced file '{finding.file_path}' "
                    "which was not modified in this diff. Confidence adjusted."
                )
                finding.confidence = max(0.2, finding.confidence - 0.4)

        # Check line number bounds against diff hunks
        file_info = valid_files_map.get(normalized_path)
        if file_info and finding.line_start is not None:
            hunks = file_info.get("hunk_ranges", [])
            in_range = False
            for start, count in hunks:
                if start <= finding.line_start <= (start + count + 5):
                    in_range = True
                    break

            if not in_range and hunks:
                # Line number is outside modified hunks; clamp confidence and note uncertainty
                finding.confidence = max(0.3, finding.confidence - 0.2)
                finding.description += f" [Note: Line {finding.line_start} is outside the explicit hunk range]"

        validated_findings.append(finding)

    review.findings = validated_findings

    # Guard recommendation logic against contradictory severity
    has_critical = any(
        f.severity == FindingSeverity.CRITICAL for f in review.findings
    )
    has_high = any(
        f.severity == FindingSeverity.HIGH for f in review.findings
    )
    has_bugs_or_security = any(
        f.category in (FindingCategory.BUG, FindingCategory.SECURITY) and
        f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        for f in review.findings
    )

    if (has_critical or has_bugs_or_security) and review.recommendation == ReviewRecommendation.APPROVE:
        review.recommendation = ReviewRecommendation.REQUEST_CHANGES
        warnings.append(
            "Recommendation overridden to 'request_changes' due to presence of critical/high severity bug or security finding."
        )
    elif has_high and review.recommendation == ReviewRecommendation.APPROVE:
        review.recommendation = ReviewRecommendation.NEEDS_MANUAL_REVIEW
        warnings.append(
            "Recommendation adjusted to 'needs_manual_review' due to presence of high-severity findings."
        )

    review.warnings = warnings
    # Trigger model validator to update category and severity counts
    return review.model_validate(review.model_dump())
