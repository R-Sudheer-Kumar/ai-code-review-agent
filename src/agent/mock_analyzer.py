"""Offline heuristic static analysis engine.

Used as a deterministic fallback when Ollama is offline, for automated unit tests,
or when quick local evaluation is requested.
"""

import re
from typing import Any, Dict, List, Optional
from src.models.schemas import (
    CodeReviewResult,
    FindingCategory,
    FindingSeverity,
    ReviewFinding,
    ReviewRecommendation,
)


class MockStaticAnalyzer:
    """Deterministic rule-based static analyzer for code review."""

    def analyze(
        self,
        diff: str,
        changed_files: List[Dict[str, Any]],
        file_context: Optional[Dict[str, str]] = None,
    ) -> CodeReviewResult:
        findings: List[ReviewFinding] = []
        test_suggestions: List[str] = []

        if not changed_files or not diff.strip():
            return CodeReviewResult(
                summary="Empty diff provided. No changes detected to review.",
                recommendation=ReviewRecommendation.APPROVE,
                findings=[],
                missing_test_suggestions=[],
                analyzer_backend="offline-static-rule-engine",
                warnings=["No code modifications found in the provided diff."],
            )

        for file_info in changed_files:
            file_path = file_info.get("file_path", "unknown")
            added_lines = file_info.get("added_lines", [])

            # Track if file has any tests
            has_tests = False
            if file_context:
                for ctx_key in file_context.keys():
                    if ctx_key.startswith("test::") or "test" in ctx_key.lower():
                        has_tests = True

            new_functions_count = 0

            for line_no, line in added_lines:
                stripped = line.strip()

                # Rule 1: SQL Injection risk
                sql_pattern = re.search(
                    r'(execute|query)\s*\(\s*(f["\']|["\'].*?%s.*?["\']\s*\%|["\'].*?\+\s*\w+)',
                    stripped,
                    re.IGNORECASE,
                )
                if sql_pattern or ("SELECT" in stripped.upper() and ("+ " in stripped or "f\"" in stripped or "f'" in stripped)):
                    findings.append(
                        ReviewFinding(
                            category=FindingCategory.SECURITY,
                            severity=FindingSeverity.CRITICAL,
                            title="Potential SQL Injection Vulnerability",
                            file_path=file_path,
                            line_start=line_no,
                            line_end=line_no,
                            description=(
                                f"Direct string concatenation or f-string interpolation detected in SQL query: `{stripped}`. "
                                "This allows untrusted user inputs to alter SQL query semantics."
                            ),
                            impact="Critical security exposure: Unauthorized data access, exfiltration, or database tampering.",
                            suggested_fix="Use parameterized queries or prepared statements (e.g. cursor.execute('SELECT * FROM tbl WHERE id = %s', (val,))).",
                            confidence=0.95,
                        )
                    )

                # Rule 2: Hardcoded Secrets / API Keys
                secret_pattern = re.search(
                    r'(api_key|secret_key|private_key|auth_token|password)\s*=\s*["\'][A-Za-z0-9_\-\.\/+=]{8,}["\']',
                    stripped,
                    re.IGNORECASE,
                )
                if secret_pattern and "os.getenv" not in stripped and "environ" not in stripped:
                    findings.append(
                        ReviewFinding(
                            category=FindingCategory.SECURITY,
                            severity=FindingSeverity.HIGH,
                            title="Hardcoded Credential or API Token Detected",
                            file_path=file_path,
                            line_start=line_no,
                            line_end=line_no,
                            description=(
                                f"Plaintext secret or authentication key is hardcoded directly in source code: `{stripped[:40]}...`."
                            ),
                            impact="Credential leakage: Exposing production credentials or service tokens in version control.",
                            suggested_fix="Extract secrets to environment variables or secret manager (e.g. os.getenv('API_KEY')).",
                            confidence=0.9,
                        )
                    )

                # Rule 3: Zero Division Bug
                if re.search(r'/\s*0(?!\d)', stripped):
                    findings.append(
                        ReviewFinding(
                            category=FindingCategory.BUG,
                            severity=FindingSeverity.HIGH,
                            title="Unconditional Division by Zero",
                            file_path=file_path,
                            line_start=line_no,
                            line_end=line_no,
                            description="Expression explicitly divides by constant zero, resulting in ZeroDivisionError at runtime.",
                            impact="Runtime crash: Unhandled exception terminates the request or execution thread.",
                            suggested_fix="Validate denominator before division or guard with a non-zero check.",
                            confidence=1.0,
                        )
                    )

                # Rule 4: Dangerous functions (eval, exec)
                if re.search(r'\b(eval|exec)\s*\(', stripped):
                    findings.append(
                        ReviewFinding(
                            category=FindingCategory.SECURITY,
                            severity=FindingSeverity.CRITICAL,
                            title="Dangerous Code Execution Function Call",
                            file_path=file_path,
                            line_start=line_no,
                            line_end=line_no,
                            description="Use of dynamic code evaluation (eval/exec) allows arbitrary code execution if inputs are user-controlled.",
                            impact="Remote code execution (RCE) risk.",
                            suggested_fix="Replace dynamic code execution with safe parsing libraries (such as ast.literal_eval or json.loads).",
                            confidence=0.95,
                        )
                    )

                # Rule 5: Debugger leftover
                if re.search(r'\b(breakpoint\(\)|import\s+pdb|pdb\.set_trace\(\))', stripped):
                    findings.append(
                        ReviewFinding(
                            category=FindingCategory.BUG,
                            severity=FindingSeverity.MEDIUM,
                            title="Interactive Debugger Breakpoint Left in Code",
                            file_path=file_path,
                            line_start=line_no,
                            line_end=line_no,
                            description="Active debugger breakpoint found. If deployed to production, it causes worker processes to freeze.",
                            impact="Process hangs indefinitely waiting for terminal input.",
                            suggested_fix="Remove breakpoint() and debugging hooks prior to merging.",
                            confidence=1.0,
                        )
                    )

                # Rule 6: Swallowed exception (except: pass)
                if re.search(r'except(?:\s+Exception)?:\s*pass', stripped):
                    findings.append(
                        ReviewFinding(
                            category=FindingCategory.BUG,
                            severity=FindingSeverity.MEDIUM,
                            title="Silent Exception Swallowing",
                            file_path=file_path,
                            line_start=line_no,
                            line_end=line_no,
                            description="Catching broad exceptions with `pass` silently hides fatal failures and corrupts application state.",
                            impact="Silent failures and difficult debugging in production environments.",
                            suggested_fix="Log the exception with proper traceback or catch specific exception classes.",
                            confidence=0.85,
                        )
                    )

                # Rule 7: Wildcard imports
                if re.search(r'from\s+\S+\s+import\s+\*', stripped):
                    findings.append(
                        ReviewFinding(
                            category=FindingCategory.STYLE,
                            severity=FindingSeverity.LOW,
                            title="Wildcard Import Pollution",
                            file_path=file_path,
                            line_start=line_no,
                            line_end=line_no,
                            description=f"Wildcard import `{stripped}` pollutes local namespace and obscures symbol origins.",
                            impact="Namespace conflicts and degraded static analysis tooling.",
                            suggested_fix="Import only required symbols explicitly.",
                            confidence=0.9,
                        )
                    )

                # Count new functions
                if re.match(r'^(def|async\s+def)\s+([a-zA-Z0-9_]+)', stripped):
                    new_functions_count += 1

            if new_functions_count > 0 and not has_tests and not ("test" in file_path.lower()):
                test_suggestions.append(
                    f"File `{file_path}` introduced {new_functions_count} new function(s) without corresponding unit tests. Add test coverage in `tests/test_{file_path.split('/')[-1]}`."
                )

        # Recommendation calculation
        has_critical = any(f.severity == FindingSeverity.CRITICAL for f in findings)
        has_high = any(f.severity == FindingSeverity.HIGH for f in findings)

        if has_critical or has_high:
            recommendation = ReviewRecommendation.REQUEST_CHANGES
            summary = (
                f"Review completed with {len(findings)} findings. High or critical risk issues "
                f"were detected in changed files. Changes requested before merging."
            )
        elif findings:
            recommendation = ReviewRecommendation.NEEDS_MANUAL_REVIEW
            summary = (
                f"Review completed with {len(findings)} minor or stylistic findings. "
                f"Manual sanity verification recommended."
            )
        else:
            recommendation = ReviewRecommendation.APPROVE
            summary = "No security, bug, or maintainability anomalies detected. Changes look good to approve."

        return CodeReviewResult(
            summary=summary,
            recommendation=recommendation,
            findings=findings,
            missing_test_suggestions=test_suggestions,
            analyzer_backend="offline-static-rule-engine",
            warnings=[
                "Generated using deterministic offline static analysis engine (Ollama service fallback or offline mode)."
            ],
        )
