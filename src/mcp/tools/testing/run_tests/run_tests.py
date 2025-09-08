"""Run Tests MCP Tool

Responsibilities:
- Execute pytest with optional coverage
- Format test results for display
- Handle test path specification
- Provide detailed test output

Generated from template on 2025-01-09T10:00:00
Template version: 1.0.0
"""

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _create_success(text: str) -> dict[str, Any]:
    """Create success response format"""
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _create_error(title: str, message: str) -> dict[str, Any]:
    """Create error response format"""
    return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}


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
        return _process_test_result(result, test_path, coverage)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return _create_error("Test Execution Failed", str(e))


def _process_test_result(result, test_path: str, coverage: bool) -> dict[str, Any]:
    """Process test execution result"""
    output = result.stdout + "\n" + result.stderr
    
    # Extract test summary
    passed = failed = 0
    for line in output.split("\n"):
        if "passed" in line and "failed" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "passed":
                    passed = int(parts[i-1])
                elif part == "failed":
                    failed = int(parts[i-1])
    
    if result.returncode == 0:
        summary = f"✅ **Tests Passed**\n"
        summary += f"📊 Results: {passed} passed"
        if coverage:
            # Extract coverage percentage
            for line in output.split("\n"):
                if "TOTAL" in line and "%" in line:
                    parts = line.split()
                    for part in parts:
                        if "%" in part:
                            summary += f"\n📈 Coverage: {part}"
                            break
        return _create_success(summary)
    else:
        summary = f"❌ **Tests Failed**\n"
        summary += f"📊 Results: {passed} passed, {failed} failed"
        
        # Include failure details (truncated)
        if len(output) > 1000:
            output = output[:1000] + "\n\n... [output truncated]"
        
        return _create_error("Test Failures", summary + f"\n\n```\n{output}\n```")