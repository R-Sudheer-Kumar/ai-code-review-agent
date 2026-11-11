# 🛡️ AI Code Review Agent

## 1. What It Does

AI Code Review Agent is a tool-using AI application that reviews Git diffs or local repository commits and identifies potential bugs, security risks, performance issues, missing test cases, and coding style problems.

It retrieves changed code and relevant context, isolates untrusted inputs against prompt injection, analyzes the changes using **Google Gemini**, local **Ollama (`Qwen2.5-Coder`)**, or a deterministic offline static analysis fallback engine, and generates structured, Pydantic-validated feedback with severity levels, line citations, recommendations, and suggested fixes.

## 2. How I Built It

**Technology Stack**
- **Python 3.12** and **FastAPI** (`src/api/main.py`) for the backend REST API (`/health`, `/review/diff`, `/review/repository`).
- **Streamlit** (`src/frontend/app.py`) for the interactive user interface.
- **Google Gemini** (`google-genai` SDK: `gemini-3-flash-preview` / `gemini-3-pro-preview`) and **Ollama** (`qwen2.5-coder:latest`) with a deterministic **Offline Static Heuristic Engine** fallback.
- **Pydantic v2** (`src/models/schemas.py`) for structured output validation and automatic category/severity counting.
- **Git CLI** via Python `subprocess` (`src/tools/git_tools.py`) for retrieving code changes.
- **Pytest** (`tests/`) for automated testing (30 unit & integration tests).

**Agent Workflow (Deterministic Orchestrator)**
1. **Retrieve Git diff**: `get_git_diff(repo_path, base_ref, head_ref)` safely executes `git diff` via subprocess.
2. **Identify changed files**: `get_changed_files(diff)` parses unified diff headers, added lines, and hunk ranges.
3. **Retrieve relevant context**: `get_file_context(repo_path, changed_files)` fetches bounded source context and auto-discovers related test files.
4. **Analyze with LLM / Fallback**: Sends XML-delimited context (`<git_diff>`, `<file_context>`) to Gemini or Ollama, or falls back to `MockStaticAnalyzer` when offline.
5. **Parse & Validate**: Extracts JSON, validates against `CodeReviewResult`, and runs `validate_review(review, diff)` to verify file paths, line ranges, and recommendation logic.
6. **Display Results**: Renders severity distribution, category filters, line citations, and code fixes in Streamlit.

## 3. Challenges and How I Handled Them

- **Inconsistent / Malformed LLM responses:** Used strict JSON-mode prompting, regex fence extraction (`extract_json_payload`), and Pydantic validation with field auto-correction.
- **Offline / Missing Model Environments:** Added a deterministic AST/regex fallback engine (`MockStaticAnalyzer`) so the demo and API run cleanly even when Ollama is offline or no API key is provided.
- **Prompt Injection in Diffs:** Wrapped diff and file context inside `<git_diff>` / `<file_context>` XML boundaries with explicit untrusted-data system instructions.
- **Hallucinated Files or Incorrect Recommendations:** Built `validate_review(review, diff)` to penalize unverified file citations and override unsafe `approve` decisions when critical/high bugs exist.
- **Git Errors & Path Traversal:** Added strict ref character checks, `--show-toplevel` repo validation, empty diff guards, oversized diff truncation, and path traversal checks.

## 4. What I Would Improve Next

- Integrate directly with GitHub Pull Requests via GitHub Actions / REST API inline comments.
- Add multi-turn automated patch generation so developers can apply suggested fixes directly.
- Integrate `tree-sitter` for deeper cross-file AST symbol resolution.
- Support configurable rule profiles and review history persistence.

## 5. Running Locally

### Setup
```bash
pip install -r requirements.txt
```
- **Using Google Gemini**: Set `GEMINI_API_KEY` in `.env` (see `.env.example`) or paste your key directly into the Streamlit sidebar.
- **Using Local Ollama**: Run `ollama pull qwen2.5-coder` and `ollama serve`.

### Start the Backend
```bash
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

### Start the Frontend
```bash
python -m streamlit run src/frontend/app.py
```

### Run CLI Demo & Tests
```bash
# Quick terminal demo against sample diff and synthetic buggy git repo
python demo.py

# Run all 30 Pytest tests
python -m pytest tests -v
```

### Sample Diff for Demonstration
Paste [`sample_data/sample.diff`](sample_data/sample.diff) or click **📥 Load Buggy Sample Diff** in the Streamlit UI:
```diff
diff --git a/backend/user_service.py b/backend/user_service.py
new file mode 100644
--- /dev/null
+++ b/backend/user_service.py
@@ -0,0 +1,16 @@
+API_KEY = "demo_dummy_secret_key_9948271638"
+
+def get_user_by_username(db, username):
+    cursor = db.cursor()
+    query = f"SELECT * FROM users WHERE username = '{username}'"
+    cursor.execute(query)
+    return cursor.fetchone()
+
+def compute_discount_rate(total_spend, tier):
+    if tier == 0:
+        return total_spend / 0
+    return total_spend / tier
```


### Output Images

<img width="831" height="748" alt="image" src="https://github.com/user-attachments/assets/feb77a0f-d39e-46d5-99e2-44f0dc541d69" />

<img width="1917" height="1076" alt="image" src="https://github.com/user-attachments/assets/0b4da4f5-7b41-40f4-998c-b92dfe2c7b98" />

<img width="1917" height="1078" alt="image" src="https://github.com/user-attachments/assets/8d4d2140-ed2a-4b60-92d4-9ea16a6ca165" />

<img width="1916" height="1078" alt="image" src="https://github.com/user-attachments/assets/8ca991aa-9a28-4311-9b83-ce4b7a6f778b" />








