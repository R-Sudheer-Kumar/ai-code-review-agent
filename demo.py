"""Quick CLI Demo script for AI Code Review Agent."""

import json
import tempfile
from pathlib import Path

from sample_data.synthetic_repo_builder import create_synthetic_buggy_repo
from src.agent.orchestrator import AgentOrchestrator


def run_demo():
    print("=" * 70)
    print("AI CODE REVIEW AGENT - INTERACTIVE CLI DEMO")
    print("=" * 70)

    orchestrator = AgentOrchestrator()

    # 1. Review Sample Buggy Diff
    sample_diff_path = Path("sample_data/sample.diff")
    diff_content = sample_diff_path.read_text(encoding="utf-8")
    print(f"\n[1/2] Reviewing pasted diff from {sample_diff_path}...\n")
    diff_result = orchestrator.review_diff(diff_content)

    print(f"Recommendation : {diff_result.recommendation.value.upper()}")
    print(f"Engine Used    : {diff_result.analyzer_backend}")
    print(f"Summary        : {diff_result.summary}")
    print(f"Severity Counts: {diff_result.counts_by_severity}")
    print(f"Findings ({len(diff_result.findings)}):")
    for idx, f in enumerate(diff_result.findings, 1):
        print(
            f"  {idx}. [{f.severity.value.upper()}] ({f.category.value}) "
            f"{f.title} -> {f.file_path}:{f.line_start}"
        )
    if diff_result.missing_test_suggestions:
        print("Missing Test Suggestions:")
        for s in diff_result.missing_test_suggestions:
            print(f"  - {s}")

    # 2. Review Synthetic Git Repository
    print("\n" + "-" * 70)
    print("[2/2] Building and reviewing synthetic Git repository (HEAD~1..HEAD)...\n")
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = create_synthetic_buggy_repo(Path(tmpdir) / "demo_repo")
        repo_result = orchestrator.review_repository(
            repo_path=str(repo_path),
            base_ref="HEAD~1",
            head_ref="HEAD",
        )
        print(f"Repo Path      : {repo_path}")
        print(f"Recommendation : {repo_result.recommendation.value.upper()}")
        print(f"Summary        : {repo_result.summary}")
        print(f"Findings ({len(repo_result.findings)}):")
        for idx, f in enumerate(repo_result.findings, 1):
            print(
                f"  {idx}. [{f.severity.value.upper()}] ({f.category.value}) "
                f"{f.title} -> {f.file_path}:{f.line_start}"
            )

    print("\n" + "=" * 70)
    print("Demo Complete! Start web UI via: python -m streamlit run src/frontend/app.py")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
