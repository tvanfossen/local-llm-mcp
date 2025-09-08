"""All Validations MCP Tool - Unified Testing and Validation

Responsibilities:
- Run all validation checks in sequence
- Execute tests with coverage
- Run pre-commit hooks
- Validate file lengths and schemas
- Provide comprehensive validation report

Generated from template on 2025-01-09T10:00:00
Template version: 1.0.0
"""

import logging
from typing import Any

from src.mcp.tools.testing.precommit.precommit import run_pre_commit
from src.mcp.tools.testing.run_tests.run_tests import run_tests
from src.mcp.tools.validation.file_length.file_length import validate_file_length

logger = logging.getLogger(__name__)


async def run_all_validations(args: dict[str, Any] = None) -> dict[str, Any]:
    """Run all validation checks and tests"""
    try:
        results = {
            "tests": {"status": "pending"},
            "precommit": {"status": "pending"},
            "file_length": {"status": "pending"},
            "schema": {"status": "pending"}
        }
        
        failures = []
        
        # 1. Run tests with coverage
        logger.info("Running tests with coverage...")
        test_result = await run_tests({"coverage": True, "verbose": False})
        results["tests"]["status"] = "passed" if not test_result.get("isError") else "failed"
        results["tests"]["details"] = test_result["content"][0]["text"]
        if test_result.get("isError"):
            failures.append("Tests")
        
        # 2. Run pre-commit hooks
        logger.info("Running pre-commit hooks...")
        precommit_result = await run_pre_commit({"all_files": True})
        results["precommit"]["status"] = "passed" if not precommit_result.get("isError") else "failed"
        results["precommit"]["details"] = precommit_result["content"][0]["text"]
        if precommit_result.get("isError"):
            failures.append("Pre-commit")
        
        # 3. Validate key file lengths
        logger.info("Validating file lengths...")
        key_files = [
            "src/core/agents/agent/agent.py",
            "src/api/http/server/server.py",
            "src/mcp/handler.py",
            "src/mcp/tools/executor/executor.py"
        ]
        
        length_result = await validate_file_length({
            "file_paths": key_files,
            "max_lines": 300
        })
        results["file_length"]["status"] = "passed" if not length_result.get("isError") else "failed"
        results["file_length"]["details"] = length_result["content"][0]["text"]
        if length_result.get("isError"):
            failures.append("File Length")
        
        # 4. Run schema validation
        logger.info("Running schema validation...")
        import subprocess
        from pathlib import Path
        
        schema_result = subprocess.run(
            ["python3", "scripts/schema_validator.py"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        results["schema"]["status"] = "passed" if schema_result.returncode == 0 else "failed"
        results["schema"]["details"] = schema_result.stdout or schema_result.stderr
        if schema_result.returncode != 0:
            failures.append("Schema")
        
        # Build comprehensive report
        report = "🔍 **Comprehensive Validation Report**\n\n"
        
        for check, data in results.items():
            icon = "✅" if data["status"] == "passed" else "❌"
            report += f"{icon} **{check.title()}**: {data['status']}\n"
        
        report += "\n---\n\n"
        
        if not failures:
            report += "🎉 **All Validations Passed!**\n\n"
            report += "Your code is ready for deployment:\n"
            report += "• Tests are passing with good coverage\n"
            report += "• Pre-commit hooks validated\n"
            report += "• File sizes within limits\n"
            report += "• Schema compliance verified\n"
            
            return {
                "content": [{"type": "text", "text": report}],
                "isError": False
            }
        else:
            report += f"❌ **Validation Failures: {', '.join(failures)}**\n\n"
            report += "Please fix the following issues:\n\n"
            
            for check, data in results.items():
                if data["status"] == "failed":
                    report += f"### {check.title()}\n"
                    # Truncate details if too long
                    details = data.get("details", "No details available")
                    if len(details) > 500:
                        details = details[:500] + "\n... [truncated]"
                    report += f"{details}\n\n"
            
            return {
                "content": [{"type": "text", "text": report}],
                "isError": True
            }
            
    except Exception as e:
        logger.error(f"All validations failed: {e}")
        return {
            "content": [{"type": "text", "text": f"❌ **Validation Error:** {str(e)}"}],
            "isError": True
        }