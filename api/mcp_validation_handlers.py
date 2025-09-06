import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MCPValidationHandlers:
    """Testing and validation MCP tool handlers"""

    def __init__(self, agent_registry):
        self.agent_registry = agent_registry

    @staticmethod
    def _create_success(text: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": text}], "isError": False}

    @staticmethod
    def _create_error(title: str, message: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}

    @staticmethod
    def _handle_exception(e: Exception, context: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": f"❌ **{context} Error:** {str(e)}"}], "isError": True}

    def _validate_agent_id(self, agent_id: str) -> tuple[bool, dict[str, Any]]:
        if not agent_id:
            return False, self._create_error("Missing Parameter", "agent_id is required")
        return True, None

    def _get_agent(self, agent_id: str) -> tuple[bool, dict[str, Any], Any]:
        agent = self.agent_registry.get_agent(agent_id)
        if not agent:
            return False, self._create_error("Agent Not Found", f"Agent {agent_id} not found"), None
        return True, None, agent

    def _validate_and_get_agent(self, args: dict[str, Any]) -> tuple[bool, dict[str, Any], Any]:
        valid, error = self._validate_agent_id(args.get("agent_id"))
        if not valid:
            return False, error, None

        valid, error, agent = self._get_agent(args["agent_id"])
        if not valid:
            return False, error, None

        return True, None, agent

    async def run_tests(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Run pytest tests for the project"""
        try:
            test_path = args.get("test_path") if args else None
            coverage = args.get("coverage", True) if args else True
            verbose = args.get("verbose", False) if args else False

            cmd = self._build_test_command(test_path, coverage, verbose)
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
            return self._process_test_result(result, coverage)
        except Exception as e:
            return self._handle_exception(e, "Run Tests")

    def _build_test_command(self, test_path: str, coverage: bool, verbose: bool) -> list:
        """Build pytest command"""
        cmd = ["python", "-m", "pytest"]
        if coverage:
            cmd.extend(["--cov=.", "--cov-report=term-missing"])
        if verbose:
            cmd.append("-v")
        if test_path:
            cmd.append(test_path)
        return cmd

    def _process_test_result(self, result, coverage: bool) -> dict[str, Any]:
        """Process pytest test result"""
        stdout, stderr = result.stdout, result.stderr
        success = result.returncode == 0
        status_emoji = "✅" if success else "❌"
        status_text = "PASSED" if success else "FAILED"

        response = f"{status_emoji} **Test Results - {status_text}**\n\n"
        response += self._extract_test_metrics(stdout, coverage)
        response += self._format_test_output(stdout, stderr, success)

        return self._create_success(response) if success else self._create_error("Tests Failed", response)

    def _extract_test_metrics(self, stdout: str, coverage: bool) -> str:
        """Extract test metrics from pytest output"""
        response = ""
        if "collected" in stdout:
            collected_lines = [line for line in stdout.split("\n") if "collected" in line]
            if collected_lines:
                response += f"**Tests Collected:** {collected_lines[0].strip()}\n"

        if "passed" in stdout or "failed" in stdout:
            summary_lines = [
                line
                for line in stdout.split("\n")
                if any(word in line for word in ["passed", "failed", "error", "skipped"])
            ]
            if summary_lines:
                response += f"**Summary:** {summary_lines[-1].strip()}\n"

        if coverage and "coverage" in stdout.lower():
            coverage_lines = [line for line in stdout.split("\n") if "%" in line and "TOTAL" in line]
            if coverage_lines:
                response += f"**Coverage:** {coverage_lines[0].strip()}\n"

        return response

    def _format_test_output(self, stdout: str, stderr: str, success: bool) -> str:
        """Format test output"""
        response = "\n**Output:**\n"
        if stdout:
            output_text = stdout
            if len(output_text) > 1500:
                output_text = output_text[:1500] + "... (output truncated)"
            response += f"```\n{output_text}\n```"

        if stderr and not success:
            response += f"\n**Errors:**\n```\n{stderr[:500]}\n```"

        return response

    async def run_pre_commit(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Run pre-commit hooks for validation"""
        try:
            all_files = args.get("all_files", False) if args else False
            hook = args.get("hook") if args else None

            cmd = self._build_precommit_command(all_files, hook)
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
            return self._process_precommit_result(result)
        except Exception as e:
            return self._handle_exception(e, "Pre-commit")

    def _build_precommit_command(self, all_files: bool, hook: str) -> list:
        """Build pre-commit command"""
        cmd = ["pre-commit", "run"]
        if all_files:
            cmd.append("--all-files")
        if hook:
            cmd.append(hook)
        return cmd

    def _process_precommit_result(self, result) -> dict[str, Any]:
        """Process pre-commit result"""
        stdout, stderr = result.stdout, result.stderr
        success = result.returncode == 0
        status_emoji = "✅" if success else "❌"
        status_text = "PASSED" if success else "FAILED"

        response = f"{status_emoji} **Pre-commit Hooks - {status_text}**\n\n"
        response += self._extract_hook_results(stdout)
        response += self._format_precommit_output(stdout, stderr, success)

        return self._create_success(response) if success else self._create_error("Pre-commit Failed", response)

    def _extract_hook_results(self, stdout: str) -> str:
        """Extract hook results from pre-commit output"""
        if not stdout:
            return ""

        lines = stdout.split("\n")
        hook_results = []
        for line in lines:
            if any(status in line for status in ["Passed", "Failed", "Skipped"]):
                hook_results.append(f"  {line.strip()}")

        if hook_results:
            return "**Hook Results:**\n" + "\n".join(hook_results) + "\n\n"
        return ""

    def _format_precommit_output(self, stdout: str, stderr: str, success: bool) -> str:
        """Format pre-commit output"""
        response = "**Output:**\n"
        if stdout:
            output_text = stdout
            if len(output_text) > 1000:
                output_text = output_text[:1000] + "... (output truncated)"
            response += f"```\n{output_text}\n```"

        if stderr and not success:
            response += f"\n**Errors:**\n```\n{stderr[:500]}\n```"

        return response

    async def validate_file_length(self, args: dict[str, Any]) -> dict[str, Any]:
        """Check if files comply with length requirements (<300 lines)"""
        try:
            file_paths = args.get("file_paths", [])
            max_lines = args.get("max_lines", 300)

            if not file_paths:
                return self._create_error("Missing Parameter", "file_paths is required")

            results, violations = self._check_file_lengths(file_paths, max_lines)
            return self._format_length_validation_result(file_paths, max_lines, results, violations)
        except Exception as e:
            return self._handle_exception(e, "File Length Validation")

    def _check_file_lengths(self, file_paths: list, max_lines: int) -> tuple[list, list]:
        """Check file lengths against limit"""
        results = []
        violations = []

        for file_path in file_paths:
            try:
                path = Path(file_path)
                if not path.exists():
                    results.append(f"  ❓ {file_path}: File not found")
                    continue

                with open(path, encoding="utf-8") as f:
                    lines = len(f.readlines())

                if lines > max_lines:
                    status = f"❌ {file_path}: {lines} lines (exceeds {max_lines})"
                    violations.append(file_path)
                else:
                    status = f"✅ {file_path}: {lines} lines (within limit)"

                results.append(f"  {status}")

            except Exception as e:
                results.append(f"  ⚠️ {file_path}: Error reading file - {str(e)}")

        return results, violations

    def _format_length_validation_result(
        self, file_paths: list, max_lines: int, results: list, violations: list
    ) -> dict[str, Any]:
        """Format file length validation result"""
        success = len(violations) == 0
        status_emoji = "✅" if success else "❌"
        status_text = "COMPLIANT" if success else "VIOLATIONS FOUND"

        response = f"{status_emoji} **File Length Validation - {status_text}**\n\n"
        response += f"**Max Lines Allowed:** {max_lines}\n"
        response += f"**Files Checked:** {len(file_paths)}\n"
        response += f"**Violations:** {len(violations)}\n\n"
        response += "**Results:**\n" + "\n".join(results)

        if violations:
            response += "\n\n**Files Exceeding Limit:**\n"
            for file_path in violations:
                response += f"  📄 {file_path}\n"

        return self._create_success(response) if success else self._create_error("Length Violations", response)

    async def validate_agent_file(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate an agent's managed file meets all requirements"""
        try:
            valid, error, agent = self._validate_and_get_agent(args)
            if not valid:
                return error

            file_path = agent.state.managed_file
            path = Path(file_path)

            checks, violations = self._perform_agent_file_checks(path, file_path)
            return self._format_agent_validation_result(agent, file_path, checks, violations)
        except Exception as e:
            return self._handle_exception(e, "Agent File Validation")

    def _perform_agent_file_checks(self, path: Path, file_path: str) -> tuple[list, list]:
        """Perform validation checks on agent file"""
        checks = []
        violations = []

        if not path.exists():
            checks.append("❓ File does not exist yet")
            return checks, violations

        checks.append("✅ File exists")

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
                lines = len(content.split("\n"))

            # Check file length
            if lines <= 300:
                checks.append(f"✅ File length: {lines} lines (within 300 limit)")
            else:
                checks.append(f"❌ File length: {lines} lines (exceeds 300 limit)")
                violations.append("File too long")

            # Check file size
            file_size = len(content)
            if file_size < 100000:  # 100KB limit
                checks.append(f"✅ File size: {file_size:,} bytes")
            else:
                checks.append(f"⚠️ File size: {file_size:,} bytes (large)")

            # Check for basic syntax (Python files)
            if file_path.endswith(".py"):
                try:
                    compile(content, file_path, "exec")
                    checks.append("✅ Python syntax valid")
                except SyntaxError as e:
                    checks.append(f"❌ Python syntax error: {str(e)}")
                    violations.append("Syntax error")

        except Exception as e:
            checks.append(f"⚠️ Error reading file: {str(e)}")
            violations.append("Read error")

        return checks, violations

    def _format_agent_validation_result(self, agent, file_path: str, checks: list, violations: list) -> dict[str, Any]:
        """Format agent file validation result"""
        success = len(violations) == 0
        status_emoji = "✅" if success else "❌"
        status_text = "VALID" if success else "ISSUES FOUND"

        response = f"{status_emoji} **Agent File Validation - {status_text}**\n\n"
        response += f"**Agent:** {agent.state.name}\n"
        response += f"**File:** `{file_path}`\n\n"
        response += "**Validation Results:**\n" + "\n".join(f"  {check}" for check in checks)

        if violations:
            response += "\n\n**Issues Found:**\n"
            for violation in violations:
                response += f"  🚨 {violation}\n"

        return self._create_success(response) if success else self._create_error("Validation Failed", response)
