# File: ~/Projects/local-llm-mcp/core/deployment.py
"""Deployment Manager

Responsibilities:
- Test coverage validation
- File diff generation
- Secure file deployment to host repositories
- Rollback capabilities
"""

import difflib
import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.agent import Agent
from core.security import SecurityManager

logger = logging.getLogger(__name__)


@dataclass
class DeploymentInfo:
    """Container for deployment information to reduce parameter count"""

    agent_id: str
    agent_name: str
    managed_file: str
    source_path: str
    target_path: str
    target_repo: str
    has_changes: bool
    diff_text: str
    coverage_percent: float
    coverage_ok: bool
    coverage_report: str
    staged_by: str


@dataclass
class ValidationResult:
    """Container for validation results to reduce complexity"""

    success: bool
    error_message: str = ""
    data: dict = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class DeploymentManager:
    """Manages the deployment pipeline from agent workspace to production repository"""

    def __init__(self, security_manager: SecurityManager, workspace_root: Path):
        self.security_manager = security_manager
        self.workspace_root = workspace_root
        self.deployments_dir = workspace_root / "deployments"
        self.deployments_dir.mkdir(parents=True, exist_ok=True)

        # Deployment history
        self.history_file = self.deployments_dir / "deployment_history.json"
        self.pending_deployments: dict[str, dict[str, Any]] = {}

    def validate_test_coverage(self, agent: Agent) -> tuple[bool, float, str]:
        """Validate test coverage for agent's file - simplified error handling"""
        # Validate prerequisites
        validation_result = self._validate_coverage_prerequisites(agent)
        if not validation_result.success:
            return False, 0.0, validation_result.error_message

        test_file = self._get_test_file_path(agent)
        main_file = agent.get_managed_file_path()

        # Execute coverage test
        return self._execute_coverage_test(test_file, main_file)

    def _validate_coverage_prerequisites(self, agent: Agent) -> ValidationResult:
        """Validate prerequisites for coverage testing"""
        test_file = self._get_test_file_path(agent)
        if not test_file.exists():
            return ValidationResult(False, "No test file found")

        main_file = agent.get_managed_file_path()
        if not main_file.exists():
            return ValidationResult(False, "Managed file not found")

        return ValidationResult(True)

    def _execute_coverage_test(self, test_file: Path, main_file: Path) -> tuple[bool, float, str]:
        """Execute the actual coverage test - simplified complexity"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                return self._run_coverage_in_temp_dir(temp_dir, test_file, main_file)
        except Exception as e:
            logger.error(f"Coverage validation failed: {e}")
            return False, 0.0, f"Error: {e!s}"

    def _run_coverage_in_temp_dir(self, temp_dir: str, test_file: Path, main_file: Path) -> tuple[bool, float, str]:
        """Run coverage test in temporary directory"""
        temp_path = Path(temp_dir)
        self._setup_test_environment(test_file, main_file, temp_path)
        result = self._run_pytest_coverage(test_file, temp_path)
        return self._parse_coverage_results(temp_path, result)

    def _setup_test_environment(self, test_file: Path, main_file: Path, temp_path: Path):
        """Setup test environment by copying necessary files"""
        shutil.copy(main_file, temp_path / main_file.name)
        shutil.copy(test_file, temp_path / test_file.name)

    def _run_pytest_coverage(self, test_file: Path, temp_path: Path):
        """Run pytest with coverage"""
        return subprocess.run(
            [
                "pytest",
                str(test_file.name),
                f"--cov={test_file.stem.replace('test_', '')}",
                "--cov-report=json",
                "--cov-report=term",
                "-v",
            ],
            check=False,
            cwd=temp_path,
            capture_output=True,
            text=True,
        )

    def _parse_coverage_results(self, temp_path: Path, result) -> tuple[bool, float, str]:
        """Parse coverage test results"""
        coverage_json = temp_path / "coverage.json"
        if coverage_json.exists():
            return self._parse_json_coverage(coverage_json, result.stdout)

        # Fallback: parse from stdout
        coverage_percent = self._parse_coverage_from_output(result.stdout)
        return coverage_percent == 100, coverage_percent, result.stdout

    def _parse_json_coverage(self, coverage_json: Path, stdout: str) -> tuple[bool, float, str]:
        """Parse coverage from JSON file"""
        with open(coverage_json) as f:
            coverage_data = json.load(f)

        totals = coverage_data.get("totals", {})
        coverage_percent = totals.get("percent_covered", 0)
        report = self._build_coverage_report(stdout, coverage_percent, coverage_data)
        return coverage_percent == 100, coverage_percent, report

    def _build_coverage_report(self, stdout: str, coverage_percent: float, coverage_data: dict) -> str:
        """Build detailed coverage report"""
        report = f"Test Results:\n{stdout}\n\n"
        report += f"Coverage: {coverage_percent:.1f}%\n"

        if coverage_percent == 100:
            report += "✅ 100% coverage achieved!"
        else:
            report += self._build_uncovered_lines_report(coverage_data)

        return report

    def _build_uncovered_lines_report(self, coverage_data: dict) -> str:
        """Build report for uncovered lines"""
        report = ""
        files = coverage_data.get("files", {})
        for filename, file_data in files.items():
            uncovered = file_data.get("missing_lines", [])
            if uncovered:
                report += f"\nUncovered lines in {filename}: {uncovered}"
        return report

    def _parse_coverage_from_output(self, output: str) -> float:
        """Parse coverage percentage from pytest output"""
        try:
            lines = output.split("\n")
            total_line = self._find_total_coverage_line(lines)
            if total_line:
                return self._extract_percentage_from_line(total_line)
        except Exception:
            pass
        return 0.0

    def _find_total_coverage_line(self, lines: list[str]) -> str | None:
        """Find the line containing total coverage information"""
        for line in lines:
            if "TOTAL" in line and "%" in line:
                return line
        return None

    def _extract_percentage_from_line(self, line: str) -> float:
        """Extract percentage value from a coverage line"""
        parts = line.split()
        for part in parts:
            if part.endswith("%"):
                return float(part.rstrip("%"))
        return 0.0

    def _get_test_file_path(self, agent: Agent) -> Path:
        """Get the test file path for an agent's managed file"""
        managed_file = Path(agent.state.managed_file)
        test_name = f"test_{managed_file.stem}{managed_file.suffix}"

        # Look for test agent managing this file
        test_file_path = agent.workspace_dir.parent / "test_agents" / agent.state.agent_id / "files" / test_name
        if test_file_path.exists():
            return test_file_path

        # Alternative: look in same directory
        return agent.files_dir / test_name

    def generate_diff(self, agent: Agent, target_repo: Path) -> tuple[bool, str, str]:
        """Generate diff between agent's file and target repository"""
        try:
            source_file = agent.get_managed_file_path()
            if not source_file.exists():
                return False, "", ""

            target_file = target_repo / agent.state.managed_file
            source_content = self._read_file_lines(source_file)
            target_content = self._read_file_lines(target_file) if target_file.exists() else []

            diff_text = self._generate_unified_diff(source_content, target_content, agent.state.managed_file)
            has_changes = len(diff_text) > 0

            return has_changes, diff_text, str(target_file)

        except Exception as e:
            logger.error(f"Diff generation failed: {e}")
            return False, f"Error: {e!s}", ""

    def _read_file_lines(self, file_path: Path) -> list[str]:
        """Read file and return lines"""
        with open(file_path) as f:
            return f.readlines()

    def _generate_unified_diff(self, source_content: list[str], target_content: list[str], filename: str) -> str:
        """Generate unified diff between source and target content"""
        diff = difflib.unified_diff(
            target_content,
            source_content,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm="",
        )
        return "\n".join(diff)

    def stage_deployment(
        self,
        agent: Agent,
        target_repo: Path,
        session_token: str,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Stage a deployment for approval"""
        try:
            # Validate session
            valid, session = self.security_manager.validate_session(session_token)
            if not valid:
                return False, "", {"error": "Invalid session"}

            deployment_data = self._gather_deployment_data(agent, target_repo, session)
            deployment_record = self._create_deployment_record(deployment_data)
            deployment_id = deployment_record["deployment_id"]
            self.pending_deployments[deployment_id] = deployment_record

            return True, deployment_id, deployment_record

        except Exception as e:
            logger.error(f"Staging failed: {e}")
            return False, "", {"error": str(e)}

    def _gather_deployment_data(self, agent: Agent, target_repo: Path, session: dict) -> DeploymentInfo:
        """Gather all data needed for deployment"""
        # Validate test coverage
        coverage_ok, coverage_percent, coverage_report = self.validate_test_coverage(agent)

        # Generate diff
        has_changes, diff_text, target_path = self.generate_diff(agent, target_repo)

        return DeploymentInfo(
            agent_id=agent.state.agent_id,
            agent_name=agent.state.name,
            managed_file=agent.state.managed_file,
            source_path=str(agent.get_managed_file_path()),
            target_path=target_path,
            target_repo=str(target_repo),
            has_changes=has_changes,
            diff_text=diff_text,
            coverage_percent=coverage_percent,
            coverage_ok=coverage_ok,
            coverage_report=coverage_report,
            staged_by=session["client_name"],
        )

    def _create_deployment_record(self, info: DeploymentInfo) -> dict[str, Any]:
        """Create deployment record"""
        deployment_id = f"{info.agent_id}_{datetime.now().timestamp()}"

        return {
            "deployment_id": deployment_id,
            "agent_id": info.agent_id,
            "agent_name": info.agent_name,
            "managed_file": info.managed_file,
            "source_path": info.source_path,
            "target_path": info.target_path,
            "target_repo": info.target_repo,
            "has_changes": info.has_changes,
            "diff": info.diff_text,
            "coverage_percent": info.coverage_percent,
            "coverage_ok": info.coverage_ok,
            "coverage_report": info.coverage_report,
            "staged_by": info.staged_by,
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "status": "staged" if info.coverage_ok else "failed_coverage",
        }

    def execute_deployment(
        self,
        deployment_id: str,
        session_token: str,
    ) -> tuple[bool, str]:
        """Execute a staged deployment"""
        validation_result = self._validate_deployment_prerequisites(deployment_id, session_token)
        if not validation_result.success:
            return False, validation_result.error_message

        deployment = validation_result.data["deployment"]
        session = validation_result.data["session"]

        workflow_result = self._execute_deployment_workflow(deployment, session, session_token)
        return workflow_result["success"], workflow_result["message"]

    def _validate_deployment_prerequisites(self, deployment_id: str, session_token: str) -> ValidationResult:
        """Validate deployment prerequisites"""
        # Check session validity
        valid, session = self.security_manager.validate_session(session_token)
        if not valid:
            return ValidationResult(False, "Invalid session")

        # Check deployment exists and coverage
        deployment_check = self._check_deployment_readiness(deployment_id)
        if not deployment_check.success:
            return deployment_check

        return ValidationResult(True, data={"deployment": deployment_check.data["deployment"], "session": session})

    def _check_deployment_readiness(self, deployment_id: str) -> ValidationResult:
        """Check if deployment exists and meets coverage requirements"""
        if deployment_id not in self.pending_deployments:
            return ValidationResult(False, "Deployment not found")

        deployment = self.pending_deployments[deployment_id]
        if not deployment["coverage_ok"]:
            error_msg = f"Coverage requirement not met: {deployment['coverage_percent']}%"
            return ValidationResult(False, error_msg)

        return ValidationResult(True, data={"deployment": deployment})

    def _execute_deployment_workflow(self, deployment: dict, session: dict, session_token: str) -> dict:
        """Execute the deployment workflow"""
        try:
            auth_result = self._authorize_deployment(deployment, session_token)
            if not auth_result["success"]:
                return auth_result

            # Create backup and deploy
            backup_path = self._create_backup_if_needed(deployment)
            self._copy_deployment_file(deployment, backup_path)
            self._update_deployment_record(deployment, session, backup_path)
            self._save_deployment_history(deployment)

            logger.info(f"Deployment successful: {deployment['managed_file']} -> {deployment['target_path']}")
            return {
                "success": True,
                "message": f"Successfully deployed {deployment['managed_file']}",
            }

        except Exception as e:
            return {"success": False, "message": f"Deployment workflow failed: {e!s}"}

    def _authorize_deployment(self, deployment: dict, session_token: str) -> dict:
        """Authorize deployment with security manager"""
        authorized, error = self.security_manager.authorize_deployment(
            session_token,
            deployment["agent_id"],
            Path(deployment["source_path"]),
            Path(deployment["target_path"]),
        )

        if authorized:
            return {"success": True}
        else:
            return {"success": False, "message": f"Authorization failed: {error}"}

    def _create_backup_if_needed(self, deployment: dict) -> Path | None:
        """Create backup if target file exists"""
        target_path = Path(deployment["target_path"])
        if target_path.exists():
            backup_path = self.deployments_dir / f"backup_{deployment['deployment_id']}_{target_path.name}"
            shutil.copy2(target_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return backup_path
        return None

    def _copy_deployment_file(self, deployment: dict, backup_path: Path | None):
        """Copy the deployment file to target location"""
        target_path = Path(deployment["target_path"])
        source_path = Path(deployment["source_path"])

        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        shutil.copy2(source_path, target_path)

    def _update_deployment_record(self, deployment: dict, session: dict, backup_path: Path | None):
        """Update deployment record with execution details"""
        deployment["status"] = "deployed"
        deployment["deployed_at"] = datetime.now(timezone.utc).isoformat()
        deployment["deployed_by"] = session["client_name"]
        deployment["backup_path"] = str(backup_path) if backup_path else None

    def rollback_deployment(
        self,
        deployment_id: str,
        session_token: str,
    ) -> tuple[bool, str]:
        """Rollback a deployment"""
        # Validate session
        valid, session = self.security_manager.validate_session(session_token)
        if not valid:
            return False, "Invalid session"

        # Find and validate deployment
        rollback_validation = self._validate_rollback_deployment(deployment_id)
        if not rollback_validation.success:
            return False, rollback_validation.error_message

        # Execute the rollback
        deployment = rollback_validation.data["deployment"]
        return self._execute_rollback(deployment, session)

    def _validate_rollback_deployment(self, deployment_id: str) -> ValidationResult:
        """Validate deployment for rollback"""
        # Find deployment in history
        deployment = self._find_deployment_in_history(deployment_id)
        if not deployment:
            return ValidationResult(False, "Deployment not found in history")

        # Check eligibility and backup availability
        eligibility_check = self._check_rollback_eligibility(deployment)
        return eligibility_check

    def _check_rollback_eligibility(self, deployment: dict) -> ValidationResult:
        """Check if deployment is eligible for rollback"""
        if deployment.get("status") != "deployed":
            return ValidationResult(False, "Deployment was not successfully deployed")

        backup_path = deployment.get("backup_path")
        if not backup_path or not Path(backup_path).exists():
            return ValidationResult(False, "No backup available for rollback")

        return ValidationResult(True, data={"deployment": deployment})

    def _find_deployment_in_history(self, deployment_id: str) -> dict | None:
        """Find deployment in history"""
        history = self._load_deployment_history()
        for entry in history:
            if entry.get("deployment_id") == deployment_id:
                return entry
        return None

    def _execute_rollback(self, deployment: dict, session: dict) -> tuple[bool, str]:
        """Execute the actual rollback"""
        try:
            backup_path = deployment["backup_path"]
            target_path = Path(deployment["target_path"])

            # Restore from backup
            shutil.copy2(backup_path, target_path)

            # Update deployment record
            deployment["status"] = "rolled_back"
            deployment["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
            deployment["rolled_back_by"] = session["client_name"]

            # Save updated history
            self._save_deployment_history(deployment)

            logger.info(f"Rollback successful: {deployment['managed_file']}")
            return True, f"Successfully rolled back {deployment['managed_file']}"

        except Exception as e:
            logger.error(f"Rollback execution failed: {e}")
            return False, f"Rollback execution failed: {e!s}"

    def _save_deployment_history(self, deployment: dict[str, Any]):
        """Save deployment to history"""
        history = self._load_deployment_history()
        history = self._update_deployment_in_history(history, deployment)

        # Keep only last 1000 entries
        if len(history) > 1000:
            history = history[-1000:]

        self._write_deployment_history(history)

    def _update_deployment_in_history(self, history: list, deployment: dict) -> list:
        """Update or add deployment in history"""
        for i, entry in enumerate(history):
            if entry.get("deployment_id") == deployment["deployment_id"]:
                history[i] = deployment
                return history

        history.append(deployment)
        return history

    def _write_deployment_history(self, history: list):
        """Write deployment history to file"""
        try:
            with open(self.history_file, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save deployment history: {e}")

    def _load_deployment_history(self) -> list[dict[str, Any]]:
        """Load deployment history"""
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load deployment history: {e}")
            return []

    def get_deployment_status(self) -> dict[str, Any]:
        """Get current deployment status"""
        history = self._load_deployment_history()
        status_counts = self._count_deployment_statuses(history)

        return {
            "pending_deployments": len(self.pending_deployments),
            "total_deployments": len(history),
            "status_breakdown": status_counts,
            "recent_deployments": history[-10:] if history else [],
        }

    def _count_deployment_statuses(self, history: list) -> dict[str, int]:
        """Count deployments by status"""
        status_counts = {}
        for entry in history:
            status = entry.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts

    def validate_code_quality(self, agent: Agent) -> tuple[bool, dict[str, Any], str]:
        """Run pre-commit quality gates on agent's file"""
        try:
            file_path = agent.get_managed_file_path()
            if not file_path.exists():
                return False, {}, "File not found"

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                quality_results = self._run_quality_checks(file_path, temp_path)
                report = self._build_quality_report(quality_results)
                all_passed = quality_results.get("returncode", 1) == 0

                return all_passed, quality_results, report

        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            return False, {"error": str(e)}, f"Error running quality checks: {e!s}"

    def _run_quality_checks(self, file_path: Path, temp_path: Path) -> dict[str, Any]:
        """Run quality checks in temporary repo"""
        self._prepare_quality_check_environment(file_path, temp_path)
        result = self._execute_precommit_hooks(temp_path)
        return self._parse_precommit_output(result.stdout, result.stderr, result.returncode)

    def _prepare_quality_check_environment(self, file_path: Path, temp_path: Path):
        """Prepare environment for quality checks"""
        self._setup_temp_git_repo(temp_path, file_path)

    def _setup_temp_git_repo(self, temp_path: Path, file_path: Path):
        """Setup temporary git repository"""
        self._initialize_git_repo(temp_path)
        self._setup_git_config(temp_path)
        self._prepare_test_files(temp_path, file_path)
        self._stage_files_for_git(temp_path)

    def _initialize_git_repo(self, temp_path: Path):
        """Initialize git repository"""
        self._run_git_command(temp_path, ["init"])

    def _setup_git_config(self, temp_path: Path):
        """Configure git user settings"""
        self._run_git_command(temp_path, ["config", "user.email", "test@test.com"])
        self._run_git_command(temp_path, ["config", "user.name", "Test User"])

    def _prepare_test_files(self, temp_path: Path, file_path: Path):
        """Copy necessary files for testing"""
        target_file = temp_path / file_path.name
        shutil.copy(file_path, target_file)
        self._copy_precommit_config(temp_path)

    def _stage_files_for_git(self, temp_path: Path):
        """Stage all files in git"""
        self._run_git_command(temp_path, ["add", "."])

    def _run_git_command(self, cwd: Path, args: list[str]):
        """Run git command in specified directory"""
        subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True)

    def _copy_precommit_config(self, temp_path: Path):
        """Copy pre-commit configuration if it exists"""
        precommit_config = Path(__file__).parent.parent / ".pre-commit-config.yaml"
        if precommit_config.exists():
            shutil.copy(precommit_config, temp_path / ".pre-commit-config.yaml")

    def _execute_precommit_hooks(self, temp_path: Path):
        """Execute pre-commit hooks"""
        return subprocess.run(
            ["pre-commit", "run", "--all-files", "--verbose"],
            check=False,
            cwd=temp_path,
            capture_output=True,
            text=True,
        )

    def _parse_precommit_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
        """Parse pre-commit output into structured results"""
        results = self._initialize_precommit_results(returncode)
        self._extract_hook_results(stdout, results)
        self._calculate_precommit_summary(results)
        return results

    def _initialize_precommit_results(self, returncode: int) -> dict[str, Any]:
        """Initialize pre-commit results structure"""
        return {
            "checks_run": [],
            "passed": [],
            "failed": [],
            "skipped": [],
            "details": {},
            "returncode": returncode,
        }

    def _extract_hook_results(self, stdout: str, results: dict):
        """Extract hook results from stdout"""
        lines = stdout.split("\n")
        for line in lines:
            if "......................." in line:
                hook_info = self._parse_hook_line(line)
                if hook_info:
                    self._categorize_hook_result(hook_info, results, stdout)

    def _parse_hook_line(self, line: str) -> dict | None:
        """Parse individual hook result line"""
        parts = line.split(".")
        if len(parts) >= 2:
            return {"name": parts[0].strip(), "status": parts[-1].strip()}
        return None

    def _categorize_hook_result(self, hook_info: dict, results: dict, stdout: str):
        """Categorize hook result into passed/failed/skipped"""
        hook_name = hook_info["name"]
        status = hook_info["status"]

        results["checks_run"].append(hook_name)

        status_handlers = {
            "passed": lambda: self._handle_passed_check(hook_name, results),
            "failed": lambda: self._handle_failed_check(hook_name, results, stdout),
            "skipped": lambda: self._handle_skipped_check(hook_name, results),
        }

        status_type = self._determine_status_type(status)
        handler = status_handlers.get(status_type, lambda: None)
        handler()

    def _determine_status_type(self, status: str) -> str:
        """Determine the type of status from status string"""
        if "Passed" in status or "✓" in status:
            return "passed"
        elif "Failed" in status or "✗" in status:
            return "failed"

        # Handle skipped or unknown statuses
        return "skipped" if "Skipped" in status else "unknown"

    def _handle_passed_check(self, hook_name: str, results: dict):
        """Handle passed check result"""
        results["passed"].append(hook_name)

    def _handle_failed_check(self, hook_name: str, results: dict, stdout: str):
        """Handle failed check result"""
        results["failed"].append(hook_name)
        results["details"][hook_name] = self._extract_failure_details(stdout, hook_name)

    def _handle_skipped_check(self, hook_name: str, results: dict):
        """Handle skipped check result"""
        results["skipped"].append(hook_name)

    def _calculate_precommit_summary(self, results: dict):
        """Calculate summary statistics for pre-commit results"""
        total_checks = len(results["checks_run"])
        passed_checks = len(results["passed"])

        results["summary"] = {
            "total": total_checks,
            "passed": passed_checks,
            "failed": len(results["failed"]),
            "skipped": len(results["skipped"]),
            "pass_rate": (passed_checks / total_checks if total_checks > 0 else 0),
        }

    def _extract_failure_details(self, output: str, hook_name: str) -> dict[str, Any]:
        """Extract detailed failure information for a specific hook"""
        details = {"issues": [], "suggestions": []}

        # Use hook-specific parsers
        parser = self._get_hook_parser(hook_name)
        if parser:
            parser(output, details)

        return details

    def _get_hook_parser(self, hook_name: str):
        """Get the appropriate parser for a hook"""
        hook_parsers = {
            "ruff": self._parse_ruff_errors,
            "mypy": self._parse_mypy_errors,
            "bandit": self._parse_bandit_errors,
            "complexity": self._parse_complexity_errors,
        }

        for hook_type, parser in hook_parsers.items():
            if hook_type in hook_name.lower():
                return parser

        return None

    def _parse_ruff_errors(self, output: str, details: dict):
        """Parse ruff-specific errors"""
        for line in output.split("\n"):
            if " | " in line and "error" in line.lower():
                details["issues"].append(line.strip())

    def _parse_mypy_errors(self, output: str, details: dict):
        """Parse mypy-specific errors"""
        for line in output.split("\n"):
            if "error:" in line.lower():
                details["issues"].append(line.strip())

    def _parse_bandit_errors(self, output: str, details: dict):
        """Parse bandit security issues"""
        in_issue = False
        for line in output.split("\n"):
            if "Issue:" in line:
                in_issue = True
                details["issues"].append(line.strip())
            elif in_issue and line.strip():
                details["issues"][-1] += " " + line.strip()
            else:
                in_issue = False

    def _parse_complexity_errors(self, output: str, details: dict):
        """Parse complexity issues"""
        for line in output.split("\n"):
            if "complexity" in line.lower() and any(char.isdigit() for char in line):
                details["issues"].append(line.strip())

    def _build_quality_report(self, results: dict[str, Any]) -> str:
        """Build human-readable quality report"""
        report_sections = []

        # Header
        report_sections.extend(["=" * 60, "CODE QUALITY VALIDATION REPORT", "=" * 60])

        # Summary section
        report_sections.append(self._build_summary_section(results))

        # Detailed sections
        report_sections.append(self._build_passed_checks_section(results))
        report_sections.append(self._build_failed_checks_section(results))
        report_sections.append(self._build_recommendations_section(results))

        # Footer
        report_sections.append("\n" + "=" * 60)

        return "\n".join(filter(None, report_sections))

    def _build_summary_section(self, results: dict) -> str:
        """Build summary section of quality report"""
        summary = results.get("summary", {})
        return f"""
📊 Summary:
  Total Checks: {summary.get("total", 0)}
  ✅ Passed: {summary.get("passed", 0)}
  ❌ Failed: {summary.get("failed", 0)}
  ⏭️  Skipped: {summary.get("skipped", 0)}
  📈 Pass Rate: {summary.get("pass_rate", 0):.1%}"""

    def _build_passed_checks_section(self, results: dict) -> str:
        """Build passed checks section"""
        if not results.get("passed"):
            return ""

        passed_list = "\n".join(f"  • {check}" for check in results["passed"])
        return f"\n✅ Passed Checks:\n{passed_list}"

    def _build_failed_checks_section(self, results: dict) -> str:
        """Build failed checks section"""
        if not results.get("failed"):
            return ""

        failed_section = "\n❌ Failed Checks:"
        for check in results["failed"]:
            failed_section += self._build_single_failed_check(check, results)

        return failed_section

    def _build_single_failed_check(self, check: str, results: dict) -> str:
        """Build section for a single failed check"""
        check_section = f"\n  • {check}"
        details = results.get("details", {}).get(check, {})

        if details.get("issues"):
            check_section += self._build_issues_list(details["issues"])

        return check_section

    def _build_issues_list(self, issues: list[str]) -> str:
        """Build list of issues with optional truncation"""
        issues_section = ""
        displayed_issues = issues[:5]  # Limit to first 5 issues

        for issue in displayed_issues:
            issues_section += f"\n    → {issue}"

        if len(issues) > 5:
            remaining_count = len(issues) - 5
            issues_section += f"\n    ... and {remaining_count} more issues"

        return issues_section

    def _build_recommendations_section(self, results: dict) -> str:
        """Build recommendations section"""
        if not results.get("failed"):
            return ""

        recommendations = ["\n💡 Recommendations:"]
        failed_checks = str(results.get("failed", []))

        for check_type, recommendation in self._get_recommendation_map().items():
            if check_type in failed_checks:
                recommendations.append(recommendation)

        return "\n".join(recommendations) if len(recommendations) > 1 else ""

    def _get_recommendation_map(self) -> dict[str, str]:
        """Get mapping of check types to recommendations"""
        return {
            "ruff": "  • Run 'ruff check --fix' to auto-fix formatting issues",
            "mypy": "  • Add type hints to resolve mypy errors",
            "bandit": "  • Review security issues and add '# nosec' for false positives",
            "complexity": "  • Refactor complex functions to reduce cyclomatic complexity",
        }
