"""Validation Tool - Consolidated Testing and Validation Operations

Path: src/mcp/tools/validation/validation.py
Responsibilities:
- Run pytest with coverage
- Run pre-commit hooks
- Validate file lengths
- Run all validations combined
- Consolidated from testing directory duplicates
"""

import logging
import subprocess
from pathlib import Path
from typing import Any

from src.core.utils.utils import create_mcp_response, handle_exception, truncate_string

logger = logging.getLogger(__name__)


async def run_tests(args: dict[str, Any] = None) -> dict[str, Any]:
    """Run pytest with optional coverage"""
    try:
        test_path = args.get("test_path", "src/") if args else "src/"
        coverage = args.get("coverage", True) if args else True
        verbose = args.get("verbose", False) if args else False

        cmd = ["python3", "-m", "pytest", test_path]

        if coverage:
            cmd.extend(["--cov=src", "--cov-report=term-missing"])

        if verbose:
            cmd.append("-v")
        else:
            cmd.append("--tb=short")

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        return _process_test_result(result, coverage)
    except Exception as e:
        return handle_exception(e, "Test Execution")


def _process_test_result(result, coverage: bool) -> dict[str, Any]:
    """Process test execution result"""
    output = result.stdout + "\n" + result.stderr

    # Extract test summary
    passed = failed = 0
    for line in output.split("\n"):
        if "passed" in line and "failed" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "passed":
                    passed = int(parts[i - 1])
                elif part == "failed":
                    failed = int(parts[i - 1])

    if result.returncode == 0:
        summary = "✅ **Tests Passed**\n"
        summary += f"📊 Results: {passed} passed"
        if coverage:
            for line in output.split("\n"):
                if "TOTAL" in line and "%" in line:
                    parts = line.split()
                    for part in parts:
                        if "%" in part:
                            summary += f"\n📈 Coverage: {part}"
                            break
        return create_mcp_response(True, summary)
    else:
        summary = "❌ **Tests Failed**\n"
        summary += f"📊 Results: {passed} passed, {failed} failed"
        output = truncate_string(output, 1000, "\n\n... [output truncated]")
        return create_mcp_response(False, summary + f"\n\n```\n{output}\n```")


async def run_pre_commit(args: dict[str, Any] = None) -> dict[str, Any]:
    """Run pre-commit hooks for validation"""
    try:
        hook = args.get("hook") if args else None
        all_files = args.get("all_files", False) if args else False

        cmd = ["pre-commit", "run"]

        if hook:
            cmd.append(hook)

        if all_files:
            cmd.append("--all-files")
        else:
            # Get staged files for targeted checking
            staged_result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, cwd=Path.cwd()
            )
            if staged_result.stdout:
                cmd.extend(["--files"] + staged_result.stdout.strip().split("\n"))
            else:
                return create_mcp_response(True, "✅ **Pre-commit:** No staged files to check")

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        return _process_precommit_result(result, hook, all_files)
    except FileNotFoundError:
        return create_mcp_response(False, "Pre-commit not installed. Install with: pip install pre-commit")
    except Exception as e:
        return handle_exception(e, "Pre-commit")


def _process_precommit_result(result, hook: str, all_files: bool) -> dict[str, Any]:
    """Process pre-commit result"""
    output = result.stdout + result.stderr

    if result.returncode == 0:
        scope = "all files" if all_files else "staged files"
        hook_name = hook if hook else "all hooks"
        return create_mcp_response(
            True, f"✅ **Pre-commit Passed**\n🔍 Checked: {hook_name} on {scope}\nAll validation checks passed!"
        )

    # Parse failures
    failures = []
    for line in output.split("\n"):
        if "Failed" in line or "ERROR" in line:
            failures.append(line.strip())

    summary = "❌ **Pre-commit Validation Failed**\n\n"
    if failures:
        summary += "**Failures:**\n"
        for failure in failures[:5]:  # Limit to 5
            summary += f"• {failure}\n"

    output = truncate_string(output, 800, "\n... [output truncated]")
    return create_mcp_response(False, summary + f"\n```\n{output}\n```")


async def validate_file_length(args: dict[str, Any] = None) -> dict[str, Any]:
    """Validate file line counts against limits"""
    try:
        file_paths = args.get("file_paths", []) if args else []
        max_lines = args.get("max_lines", 300) if args else 300

        if not file_paths:
            return create_mcp_response(False, "file_paths parameter required")

        violations = []
        for file_path in file_paths:
            path = Path(file_path)
            if path.exists():
                lines = len(path.read_text().splitlines())
                if lines > max_lines:
                    violations.append(f"{path.name}: {lines} lines (limit: {max_lines})")

        if violations:
            summary = f"❌ **File Length Violations ({len(violations)})**\n\n"
            for v in violations:
                summary += f"• {v}\n"
            return create_mcp_response(False, summary)

        return create_mcp_response(True, f"✅ All {len(file_paths)} files within {max_lines} line limit")
    except Exception as e:
        return handle_exception(e, "File Length Validation")


async def run_all_validations(args: dict[str, Any] = None) -> dict[str, Any]:
    """Run all validation checks"""
    try:
        results = []

        # Run tests
        test_result = await run_tests({"coverage": True})
        results.append(("Tests", not test_result.get("isError", False)))

        # Run pre-commit
        precommit_result = await run_pre_commit({"all_files": True})
        results.append(("Pre-commit", not precommit_result.get("isError", False)))

        # Check key file lengths
        key_files = [
            "src/mcp/tools/executor/executor.py",
            "src/core/agents/agent/agent.py",
            "src/core/utils/utils.py",
            "src/api/http/handlers/handlers.py",
            "src/core/config/manager/manager.py",
        ]
        length_result = await validate_file_length({"file_paths": key_files, "max_lines": 300})
        results.append(("File Lengths", not length_result.get("isError", False)))

        # Summarize results
        passed = sum(1 for _, success in results if success)
        total = len(results)

        summary = f"📊 **Validation Summary: {passed}/{total} Passed**\n\n"
        for name, success in results:
            icon = "✅" if success else "❌"
            summary += f"{icon} {name}\n"

        success_all = passed == total
        final_message = summary + ("\n🎉 All validations passed!" if success_all else "")
        return create_mcp_response(success_all, final_message)

    except Exception as e:
        return handle_exception(e, "All Validations")
