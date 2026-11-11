"""Helper to build a synthetic local Git repository with intentional bugs for testing."""

import subprocess
from pathlib import Path


def create_synthetic_buggy_repo(target_dir: Path) -> Path:
    """
    Initializes a git repository with an initial commit and a second commit
    introducing bugs (SQL injection, division by zero, hardcoded secret, missing test).
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    def run_git(args):
        subprocess.run(
            ["git"] + args,
            cwd=str(target_dir),
            capture_output=True,
            check=True,
            text=True,
        )

    # Init repo
    run_git(["init"])
    run_git(["config", "user.name", "Test Reviewer"])
    run_git(["config", "user.email", "test@reviewer.local"])

    # Commit 1: Clean initial state
    app_dir = target_dir / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = target_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    init_file = app_dir / "__init__.py"
    init_file.write_text("# Initial module\n", encoding="utf-8")

    calc_file = app_dir / "calculator.py"
    calc_file.write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )

    test_calc = tests_dir / "test_calculator.py"
    test_calc.write_text(
        "from app.calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    run_git(["add", "."])
    run_git(["commit", "-m", "Initial commit: clean calculator"])

    # Commit 2: Introduce bugs
    buggy_service = app_dir / "user_service.py"
    buggy_service.write_text(
        '"""User Service with security flaws."""\n'
        'API_KEY = "demo_dummy_secret_key_1234567890"\n\n'
        'def get_user(cursor, username):\n'
        '    # SQL injection\n'
        '    cursor.execute(f"SELECT * FROM users WHERE username = \'{username}\'")\n'
        '    return cursor.fetchone()\n\n'
        'def compute_discount(amount, divisor):\n'
        '    # Zero division risk\n'
        '    return amount / 0\n',
        encoding="utf-8",
    )

    run_git(["add", "."])
    run_git(["commit", "-m", "Add user service with intentional flaws"])

    return target_dir
