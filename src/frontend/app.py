"""Streamlit Frontend for AI Code Review Agent."""

import json
import os
import sys
from pathlib import Path
import streamlit as st

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.agent.gemini_client import GeminiClient
from src.agent.ollama_client import OllamaClient
from src.agent.orchestrator import AgentOrchestrator
from src.config import settings
from src.models.schemas import (
    CodeReviewResult,
    FindingCategory,
    FindingSeverity,
    ReviewRecommendation,
)
from src.tools.git_tools import GitToolError

# Page setup
st.set_page_config(
    page_title="AI Code Review Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        color: #1E293B;
    }
    .sub-title {
        color: #64748B;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .badge-approve {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-request-changes {
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-manual-review {
        background-color: #FEF08A;
        color: #713F12;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        display: inline-block;
    }
    .metric-card {
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
        background: #F8FAFC;
        text-align: center;
    }
    .finding-card {
        border-left: 5px solid #CBD5E1;
        padding: 14px 18px;
        background-color: #FFFFFF;
        border-radius: 4px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .finding-critical { border-left-color: #E02424 !important; }
    .finding-high { border-left-color: #FF5A1F !important; }
    .finding-medium { border-left-color: #3F83F8 !important; }
    .finding-low { border-left-color: #9CA3AF !important; }
    </style>
""",
    unsafe_allow_html=True,
)

# Sample diffs for instant 1-click demonstration
SAMPLE_BUGGY_DIFF = """diff --git a/app/auth.py b/app/auth.py
new file mode 100644
--- /dev/null
+++ b/app/auth.py
@@ -0,0 +1,28 @@
+import sqlite3
+
+ADMIN_API_KEY = "demo_dummy_secret_key_9948271638"
+
+def authenticate_user(username, password, db_conn):
+    # Direct query string interpolation - SQL Injection risk
+    cursor = db_conn.cursor()
+    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
+    cursor.execute(query)
+    return cursor.fetchone()
+
+def calculate_ratio(success_count, total_count):
+    # Potential division by zero
+    ratio = success_count / 0
+    return ratio
+
+def parse_config(data):
+    # Dangerous eval usage
+    return eval(data)
+
+def silent_handler():
+    try:
+        dangerous_op()
+    except Exception:
+        pass
+"""


def render_sidebar():
    """Render sidebar configuration and connection status."""
    st.sidebar.title("⚙️ AI Engine Settings")

    engine_choice = st.sidebar.radio(
        "Select Review Provider",
        options=[
            "✨ Google Gemini",
            "🦙 Local Ollama (Qwen2.5-Coder)",
            "🛡️ Offline Heuristic Engine",
        ],
        index=0,
    )

    gemini_key = ""
    gemini_model = settings.gemini_model
    ollama_url = settings.ollama_base_url
    ollama_model = settings.ollama_model
    provider = "auto"
    force_mock = False

    if "Gemini" in engine_choice:
        provider = "gemini"
        st.sidebar.markdown("##### ✨ Google Gemini Configuration")
        saved_key = settings.gemini_api_key or ""
        gemini_key = st.sidebar.text_input(
            "Gemini API Key",
            value=saved_key,
            type="password",
            help="Enter your Gemini API key (or set GEMINI_API_KEY in .env)",
        )
        if gemini_key:
            st.sidebar.success("🟢 API Key Provided")
        else:
            st.sidebar.info("💡 Paste your Gemini API key above to activate live Gemini review.")

        gemini_model = st.sidebar.selectbox(
            "Gemini Model",
            options=[
                "gemini-3-flash-preview",
                "gemini-3-pro-preview",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
            ],
            index=0,
        )

    elif "Ollama" in engine_choice:
        provider = "ollama"
        st.sidebar.markdown("##### 🦙 Ollama Configuration")
        ollama_url = st.sidebar.text_input("Ollama Base URL", value=settings.ollama_base_url)
        ollama_model = st.sidebar.text_input("Ollama Model", value=settings.ollama_model)

        client = OllamaClient(base_url=ollama_url, default_model=ollama_model)
        if client.is_available():
            st.sidebar.success(f"🟢 Ollama Connected ({ollama_url})")
            models = client.list_models()
            if models:
                st.sidebar.caption(f"Installed: {', '.join(models)}")
        else:
            st.sidebar.warning("🟡 Ollama Offline (Run `ollama serve`)")

    else:
        provider = "heuristic"
        force_mock = True
        st.sidebar.info("🛡️ Running deterministic static analysis rule engine with zero external API calls.")

    st.sidebar.divider()
    st.sidebar.markdown(
        """
    **Supported Engines:**
    - ✨ **Google Gemini** (`gemini-3-flash-preview`, `gemini-3-pro-preview`)
    - 🦙 **Qwen2.5-Coder** (Ollama Local)
    - 🛡️ **Offline Heuristic Engine** (Deterministic AST & Regex)
    """
    )
    return provider, gemini_key, gemini_model, ollama_url, ollama_model, force_mock


def render_review_result(result: CodeReviewResult):
    """Render the structured CodeReviewResult dashboard."""
    st.markdown("---")
    st.subheader("📋 Review Assessment Dashboard")

    # Header row with recommendation and summary
    rec = result.recommendation
    badge_class = "badge-approve"
    rec_text = "✅ APPROVE"
    if rec == ReviewRecommendation.REQUEST_CHANGES:
        badge_class = "badge-request-changes"
        rec_text = "🚫 REQUEST CHANGES"
    elif rec == ReviewRecommendation.NEEDS_MANUAL_REVIEW:
        badge_class = "badge-manual-review"
        rec_text = "⚠️ NEEDS MANUAL REVIEW"

    col_rec, col_eng = st.columns([2, 1])
    with col_rec:
        st.markdown(f"### Recommendation: <span class='{badge_class}'>{rec_text}</span>", unsafe_allow_html=True)
    with col_eng:
        st.caption(f"Engine: **{result.analyzer_backend}**")

    st.info(f"**Executive Summary:** {result.summary}")

    if result.warnings:
        with st.expander("⚠️ System Warnings / Fallback Logs", expanded=False):
            for w in result.warnings:
                st.write(f"- {w}")

    # Severity Counts Row
    st.markdown("#### Severity Distribution")
    s_cols = st.columns(4)
    sev_counts = result.counts_by_severity
    severities = [
        ("Critical", FindingSeverity.CRITICAL.value, "🔴", s_cols[0]),
        ("High", FindingSeverity.HIGH.value, "🟠", s_cols[1]),
        ("Medium", FindingSeverity.MEDIUM.value, "🔵", s_cols[2]),
        ("Low", FindingSeverity.LOW.value, "⚪", s_cols[3]),
    ]
    for label, key, icon, col in severities:
        count = sev_counts.get(key, 0)
        with col:
            st.metric(label=f"{icon} {label}", value=count)

    # Findings section with filters
    st.markdown("---")
    st.markdown("#### 🔍 Detailed Findings")

    if not result.findings:
        st.success("🎉 No issues identified in the reviewed code changes!")
    else:
        # Filter controls
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            selected_categories = st.multiselect(
                "Filter by Category",
                options=[c.value for c in FindingCategory],
                default=[c.value for c in FindingCategory],
            )
        with f_col2:
            selected_severities = st.multiselect(
                "Filter by Severity",
                options=[s.value for s in FindingSeverity],
                default=[s.value for s in FindingSeverity],
            )

        filtered_findings = [
            f for f in result.findings
            if f.category.value in selected_categories and f.severity.value in selected_severities
        ]

        st.caption(f"Showing {len(filtered_findings)} of {len(result.findings)} findings")

        for f in filtered_findings:
            sev_class = f"finding-{f.severity.value}"
            with st.container():
                st.markdown(
                    f"""
                    <div class="finding-card {sev_class}">
                        <h4 style="margin: 0 0 6px 0;">{f.title}</h4>
                        <span style="font-size: 0.85rem; color: #4B5563;">
                            <strong>File:</strong> <code>{f.file_path}</code> | 
                            <strong>Lines:</strong> {f.line_start or 'N/A'} - {f.line_end or 'N/A'} | 
                            <strong>Severity:</strong> <span style="text-transform: uppercase; font-weight: 600;">{f.severity.value}</span> | 
                            <strong>Category:</strong> {f.category.value} | 
                            <strong>Confidence:</strong> {int(f.confidence * 100)}%
                        </span>
                        <p style="margin-top: 8px; margin-bottom: 6px;"><strong>Description:</strong> {f.description}</p>
                        <p style="margin-top: 0; margin-bottom: 6px; color: #991B1B;"><strong>Impact:</strong> {f.impact}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander(f"💡 Suggested Fix for: {f.title}"):
                    st.code(f.suggested_fix, language="python")

    # Missing Test Suggestions Section
    if result.missing_test_suggestions:
        st.markdown("---")
        st.markdown("#### 🧪 Missing Test Suggestions")
        for suggestion in result.missing_test_suggestions:
            st.markdown(f"- 🧪 {suggestion}")

    # Raw JSON inspect
    with st.expander("🛠️ Raw Pydantic JSON Output"):
        st.json(result.model_dump())


def main():
    st.markdown("<div class='main-title'>🛡️ AI Code Review Agent</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='sub-title'>Deterministic Agent Orchestrator with Google Gemini, Qwen2.5-Coder & Safety Guards</div>",
        unsafe_allow_html=True,
    )

    provider, gemini_key, gemini_model, ollama_url, ollama_model, force_mock = render_sidebar()

    gemini_client = GeminiClient(api_key=gemini_key, default_model=gemini_model)
    ollama_client = OllamaClient(base_url=ollama_url, default_model=ollama_model)
    orchestrator = AgentOrchestrator(
        gemini_client=gemini_client,
        ollama_client=ollama_client,
    )

    active_model = gemini_model if provider == "gemini" else ollama_model

    tab_diff, tab_repo = st.tabs(["📝 Paste Diff", "📂 Review Git Repository"])

    with tab_diff:
        st.markdown("##### Paste a unified Git diff below:")

        col_b1, col_b2 = st.columns([1, 4])
        with col_b1:
            if st.button("📥 Load Buggy Sample Diff"):
                st.session_state["diff_input"] = SAMPLE_BUGGY_DIFF

        default_diff = st.session_state.get("diff_input", "")
        diff_input = st.text_area(
            "Unified Git Diff",
            value=default_diff,
            height=260,
            placeholder="diff --git a/src/main.py b/src/main.py\nindex abc..def 100644\n--- a/src/main.py\n+++ b/src/main.py\n@@ ...",
        )

        notes_input = st.text_input("Optional Context / PR Notes", placeholder="e.g. Migration of auth layer to OAuth")

        if st.button("🚀 Run Code Review", type="primary", key="btn_review_diff"):
            if not diff_input.strip():
                st.error("Please enter a non-empty Git diff or click 'Load Buggy Sample Diff'.")
            else:
                with st.spinner(f"Analyzing diff with {provider} ({active_model})..."):
                    try:
                        result = orchestrator.review_diff(
                            diff=diff_input,
                            provider=provider,
                            model=active_model,
                            api_key=gemini_key,
                            context_notes=notes_input,
                            force_mock=force_mock,
                        )
                        render_review_result(result)
                    except Exception as e:
                        st.error(f"Review failed: {str(e)}")

    with tab_repo:
        st.markdown("##### Compare Git references in a local repository:")

        repo_path_input = st.text_input(
            "Local Repository Path",
            value=str(Path.cwd()),
            help="Directory path of the local git repository.",
        )
        r_col1, r_col2 = st.columns(2)
        with r_col1:
            base_ref_input = st.text_input("Base Reference (branch / commit)", value="HEAD~1")
        with r_col2:
            head_ref_input = st.text_input("Head Reference (branch / commit)", value="HEAD")

        if st.button("🔍 Review Repository Changes", type="primary", key="btn_review_repo"):
            with st.spinner(f"Comparing {base_ref_input}..{head_ref_input} in {repo_path_input}..."):
                try:
                    result = orchestrator.review_repository(
                        repo_path=repo_path_input,
                        base_ref=base_ref_input,
                        head_ref=head_ref_input,
                        provider=provider,
                        model=active_model,
                        api_key=gemini_key,
                        force_mock=force_mock,
                    )
                    render_review_result(result)
                except (GitToolError, ValueError) as ge:
                    st.error(f"Git Error: {str(ge)}")
                except Exception as e:
                    st.error(f"Repository review failed: {str(e)}")


if __name__ == "__main__":
    main()
