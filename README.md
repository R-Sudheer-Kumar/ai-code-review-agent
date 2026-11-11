# AI Code Review Agent

## 1. What It Does

AI Code Review Agent is a tool-using AI application that reviews Git diffs and identifies potential bugs, security risks, performance issues, missing test cases, and coding style problems.

It retrieves changed code and relevant context, analyzes the changes using an LLM, and generates structured feedback with severity levels, explanations, and suggested fixes.

## 2. How I Built It

**Technology Stack**
- Python and FastAPI for the backend.
- Streamlit for the user interface.
- Ollama with Qwen2.5-Coder for local LLM inference.
- Pydantic for structured output validation.
- Git CLI and Python subprocess for retrieving code changes.
- Pytest for testing.

**Agent Workflow**

1. Retrieve Git diff using a custom Git tool.
2. Identify changed files.
3. Retrieve relevant source code and tests.
4. Send the collected context to the LLM.
5. Generate structured review findings.
6. Validate and display the results.

## 3. Challenges and How I Handled Them

- **Inconsistent LLM responses:** Used structured prompts and Pydantic validation.
- **Large code changes:** Limited the diff and relevant context passed to the model.
- **Incorrect findings:** Included instructions to distinguish potential risks from confirmed issues and provide evidence.
- **Git errors:** Added validation for repository paths, references, and empty diffs.

## 4. What I Would Improve Next

- Integrate directly with GitHub Pull Requests.
- Add automated test execution and static analysis.
- Improve code context retrieval.
- Support multiple programming languages.
- Add review history and feedback-based evaluation.
- Introduce severity-based filtering and configurable review rules.

## 5. Running Locally

Install dependencies, start Ollama and download the configured model.

Start the backend:

`uvicorn backend.main:app --reload`

Start the frontend:

`streamlit run frontend/app.py`

Run tests:

`pytest -v`
