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
        validation_error = self._validate_coverage_prerequisites(agent)
        if validation_error:
            return validation_error

        test_file = self._get_test_file_path(agent)
        main_file = agent.get_managed_file_path()

        # Execute coverage test
        return self._execute_coverage_test(test_file, main_file)

    def _validate_coverage_prerequisites(self, agent: Agent) -> tuple[bool, float, str] | None:
        """Validate prerequisites for coverage testing"""
        test_file = self._get_test_file_path(agent)
        if not test_file.exists():
            return False, 0.0, "No test file found"

        main_file = agent.get_managed_file_path()
        if not main_file.exists():
            return False, 0.0, "Managed file not found"

        return None  # No validation errors

    def _execute_coverage_test(self, test_file: Path, main_file: Path) -> tuple[bool, float, str]:
        """Execute the actual coverage test - simplified complexity"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Copy files to temp directory
                self._copy_test_files(test_file, main_file, temp_path)

                # Run pytest with coverage
                result = self._run_pytest_coverage(test_file, temp_path)

                # Parse coverage results
                return self._parse_coverage_results(temp_path, result)

        except Exception as e:
            logger.error(f"Coverage validation failed: {e}")
            return False, 0.0, f"Error: {e!s}"

    def _copy_test_files(self, test_file: Path, main_file: Path, temp_path: Path):
        """Copy test files to temporary directory"""
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
            with open(coverage_json) as f:
                coverage_data = json.load(f)

            totals = coverage_data.get("totals", {})
            coverage_percent = totals.get("percent_covered", 0)

            # Build detailed report
            report = self._build_coverage_report(result.stdout, coverage_percent, coverage_data)

            return coverage_percent == 100, coverage_percent, report

        # Fallback: parse from stdout
        coverage_percent = self._parse_coverage_from_output(result.stdout)
        return coverage_percent == 100, coverage_percent, result.stdout

    def _build_coverage_report(
        self, stdout: str, coverage_percent: float, coverage_data: dict
    ) -> str:
        """Build detailed coverage report"""
        report = f"Test Results:\n{stdout}\n\n"
        report += f"Coverage: {coverage_percent:.1f}%\n"

        if coverage_percent == 100:
            report += "✅ 100% coverage achieved!"
        else:
            # Find uncovered lines
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
            for line in lines:
                if "TOTAL" in line and "%" in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith("%"):
                            return float(part.rstrip("%"))
        except Exception:
            pass
        return 0.0

    def _get_test_file_path(self, agent: Agent) -> Path:
        """Get the test file path for an agent's managed file"""
        managed_file = Path(agent.state.managed_file)
        test_name = f"test_{managed_file.stem}{managed_file.suffix}"

        # Look for test agent managing this file
        test_file_path = (
            agent.workspace_dir.parent / "test_agents" / agent.state.agent_id / "files" / test_name
        )
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

            # Determine target file path
            target_file = target_repo / agent.state.managed_file

            # Read source content
            with open(source_file) as f:
                source_content = f.readlines()

            # Read target content if exists
            target_content = []
            if target_file.exists():
                with open(target_file) as f:
                    target_content = f.readlines()

            # Generate unified diff
            diff = difflib.unified_diff(
                target_content,
                source_content,
                fromfile=f"a/{agent.state.managed_file}",
                tofile=f"b/{agent.state.managed_file}",
                lineterm="",
            )

            diff_text = "\n".join(diff)
            has_changes = len(diff_text) > 0

            return has_changes, diff_text, str(target_file)

        except Exception as e:
            logger.error(f"Diff generation failed: {e}")
            return False, f"Error: {e!s}", ""

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

            # Validate test coverage
            coverage_ok, coverage_percent, coverage_report = self.validate_test_coverage(agent)

            # Generate diff
            has_changes, diff_text, target_path = self.generate_diff(agent, target_repo)

            # Create deployment record
            deployment_info = DeploymentInfo(
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

            deployment_record = self._create_deployment_record(deployment_info)
            deployment_id = deployment_record["deployment_id"]
            self.pending_deployments[deployment_id] = deployment_record

            return True, deployment_id, deployment_record

        except Exception as e:
            logger.error(f"Staging failed: {e}")
            return False, "", {"error": str(e)}

    def _create_deployment_record(self, info: DeploymentInfo) -> dict[str, Any]:
        """Create deployment record - fixed to use dataclass"""
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
        """Execute a staged deployment - simplified error handling"""
        # Validate prerequisites
        validation_result = self._validate_deployment_prerequisites(deployment_id, session_token)
        if validation_result["error"]:
            return False, validation_result["message"]

        deployment = validation_result["deployment"]
        session = validation_result["session"]

        # Execute deployment workflow
        workflow_result = self._execute_deployment_workflow(deployment, session, session_token)

        return workflow_result["success"], workflow_result["message"]

    def _validate_deployment_prerequisites(self, deployment_id: str, session_token: str) -> dict:
        """Validate deployment prerequisites - simplified to single return"""
        # Check session validity
        valid, session = self.security_manager.validate_session(session_token)
        if not valid:
            return {"error": True, "message": "Invalid session"}

        # Check deployment exists
        if deployment_id not in self.pending_deployments:
            return {"error": True, "message": "Deployment not found"}

        deployment = self.pending_deployments[deployment_id]

        # Check coverage requirement
        if not deployment["coverage_ok"]:
            return {
                "error": True,
                "message": f"Coverage requirement not met: {deployment['coverage_percent']}%",
            }

        return {"error": False, "deployment": deployment, "session": session}

    def _execute_deployment_workflow(
        self, deployment: dict, session: dict, session_token: str
    ) -> dict:
        """Execute the deployment workflow"""
        try:
            # Authorize with security manager
            authorized, error = self.security_manager.authorize_deployment(
                session_token,
                deployment["agent_id"],
                Path(deployment["source_path"]),
                Path(deployment["target_path"]),
            )

            if not authorized:
                return {"success": False, "message": f"Authorization failed: {error}"}

            # Create backup and deploy
            backup_path = self._create_backup_if_needed(deployment)
            self._copy_deployment_file(deployment, backup_path)

            # Update deployment record
            self._update_deployment_record(deployment, session, backup_path)

            # Save to history
            self._save_deployment_history(deployment)

            logger.info(
                f"Deployment successful: {deployment['managed_file']} -> {deployment['target_path']}"
            )
            return {
                "success": True,
                "message": f"Successfully deployed {deployment['managed_file']}",
            }

        except Exception as e:
            return {"success": False, "message": f"Deployment workflow failed: {e!s}"}

    def _create_backup_if_needed(self, deployment: dict) -> Path | None:
        """Create backup if target file exists"""
        target_path = Path(deployment["target_path"])
        if target_path.exists():
            backup_path = (
                self.deployments_dir / f"backup_{deployment['deployment_id']}_{target_path.name}"
            )
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
        """Rollback a deployment - simplified to single return"""
        # Validate session
        valid, session = self.security_manager.validate_session(session_token)
        if not valid:
            return False, "Invalid session"

        # Find and validate deployment
        rollback_validation = self._validate_rollback_deployment(deployment_id)
        if rollback_validation["error"]:
            return False, rollback_validation["message"]

        # Execute the rollback
        deployment = rollback_validation["deployment"]
        return self._execute_rollback(deployment, session)

    def _validate_rollback_deployment(self, deployment_id: str) -> dict:
        """Validate deployment for rollback"""
        # Find deployment in history
        deployment = self._find_deployment_in_history(deployment_id)
        if not deployment:
            return {"error": True, "message": "Deployment not found in history"}

        # Check eligibility
        if deployment.get("status") != "deployed":
            return {"error": True, "message": "Deployment was not successfully deployed"}

        backup_path = deployment.get("backup_path")
        if not backup_path or not Path(backup_path).exists():
            return {"error": True, "message": "No backup available for rollback"}

        return {"error": False, "deployment": deployment}

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

        # Add or update entry
        found = False
        for i, entry in enumerate(history):
            if entry.get("deployment_id") == deployment["deployment_id"]:
                history[i] = deployment
                found = True
                break

        if not found:
            history.append(deployment)

        # Keep only last 1000 entries
        if len(history) > 1000:
            history = history[-1000:]

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

        # Count by status
        status_counts = {}
        for entry in history:
            status = entry.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "pending_deployments": len(self.pending_deployments),
            "total_deployments": len(history),
            "status_breakdown": status_counts,
            "recent_deployments": history[-10:] if history else [],
        }

    def validate_code_quality(self, agent: Agent) -> tuple[bool, dict[str, Any], str]:
        """Run pre-commit quality gates on agent's file - simplified complexity"""
        try:
            file_path = agent.get_managed_file_path()
            if not file_path.exists():
                return False, {}, "File not found"

            # Create a temporary git repo for pre-commit to work
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Setup temporary repo and run checks
                quality_results = self._run_quality_checks(file_path, temp_path)

                # Build detailed report
                report = self._build_quality_report(quality_results)

                # Determine if all checks passed
                all_passed = quality_results.get("returncode", 1) == 0

                return all_passed, quality_results, report

        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            return False, {"error": str(e)}, f"Error running quality checks: {e!s}"

    def _run_quality_checks(self, file_path: Path, temp_path: Path) -> dict[str, Any]:
        """Run quality checks in temporary repo - simplified"""
        # Initialize git repo
        self._setup_temp_git_repo(temp_path, file_path)

        # Run pre-commit hooks
        result = subprocess.run(
            ["pre-commit", "run", "--all-files", "--verbose"],
            check=False,
            cwd=temp_path,
            capture_output=True,
            text=True,
        )

        # Parse results
        return self._parse_precommit_output(result.stdout, result.stderr, result.returncode)

    def _setup_temp_git_repo(self, temp_path: Path, file_path: Path):
        """Setup temporary git repository - extracted to reduce complexity"""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=temp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_path,
            check=True,
            capture_output=True,
        )

        # Copy file to temp repo
        target_file = temp_path / file_path.name
        shutil.copy(file_path, target_file)

        # Copy pre-commit config
        precommit_config = Path(__file__).parent.parent / ".pre-commit-config.yaml"
        if precommit_config.exists():
            shutil.copy(precommit_config, temp_path / ".pre-commit-config.yaml")

        # Stage the file
        subprocess.run(["git", "add", "."], cwd=temp_path, check=True, capture_output=True)

    def _parse_precommit_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
        """Parse pre-commit output into structured results - simplified"""
        results = {
            "checks_run": [],
            "passed": [],
            "failed": [],
            "skipped": [],
            "details": {},
            "returncode": returncode,
        }

        # Parse hook results from output
        self._extract_hook_results(stdout, results)

        # Add summary
        results["summary"] = {
            "total": len(results["checks_run"]),
            "passed": len(results["passed"]),
            "failed": len(results["failed"]),
            "skipped": len(results["skipped"]),
            "pass_rate": (
                len(results["passed"]) / len(results["checks_run"]) if results["checks_run"] else 0
            ),
        }

        return results

    def _extract_hook_results(self, stdout: str, results: dict):
        """Extract hook results from stdout - simplified parsing"""
        lines = stdout.split("\n")
        for line in lines:
            if "......................." in line:
                # This is a hook result line
                parts = line.split(".")
                if len(parts) >= 2:
                    hook_name = parts[0].strip()
                    status = parts[-1].strip()

                    results["checks_run"].append(hook_name)

                    if "Passed" in status or "✓" in status:
                        results["passed"].append(hook_name)
                    elif "Failed" in status or "✗" in status:
                        results["failed"].append(hook_name)
                        # Capture failure details
                        results["details"][hook_name] = self._extract_failure_details(
                            stdout, hook_name
                        )
                    elif "Skipped" in status:
                        results["skipped"].append(hook_name)

    def _extract_failure_details(self, output: str, hook_name: str) -> dict[str, Any]:
        """Extract detailed failure information for a specific hook"""
        details = {
            "issues": [],
            "suggestions": [],
        }

        # Hook-specific parsing
        if "ruff" in hook_name.lower():
            # Parse ruff output
            for line in output.split("\n"):
                if " | " in line and "error" in line.lower():
                    details["issues"].append(line.strip())

        elif "mypy" in hook_name.lower():
            # Parse mypy output
            for line in output.split("\n"):
                if "error:" in line.lower():
                    details["issues"].append(line.strip())

        elif "bandit" in hook_name.lower():
            # Parse bandit security issues
            in_issue = False
            for line in output.split("\n"):
                if "Issue:" in line:
                    in_issue = True
                    details["issues"].append(line.strip())
                elif in_issue and line.strip():
                    details["issues"][-1] += " " + line.strip()
                else:
                    in_issue = False

        elif "complexity" in hook_name.lower():
            # Parse complexity issues
            for line in output.split("\n"):
                if "complexity" in line.lower() and any(char.isdigit() for char in line):
                    details["issues"].append(line.strip())

        return details

    def _build_quality_report(self, results: dict[str, Any]) -> str:
        """Build human-readable quality report - simplified"""
        report = []
        report.append("=" * 60)
        report.append("CODE QUALITY VALIDATION REPORT")
        report.append("=" * 60)

        # Summary
        summary = results.get("summary", {})
        report.append("\n📊 Summary:")
        report.append(f"  Total Checks: {summary.get('total', 0)}")
        report.append(f"  ✅ Passed: {summary.get('passed', 0)}")
        report.append(f"  ❌ Failed: {summary.get('failed', 0)}")
        report.append(f"  ⏭️  Skipped: {summary.get('skipped', 0)}")
        report.append(f"  📈 Pass Rate: {summary.get('pass_rate', 0):.1%}")

        # Add passed/failed sections
        self._add_quality_report_sections(results, report)

        # Add recommendations
        if results.get("failed"):
            report.append("\n💡 Recommendations:")
            self._add_quality_recommendations(results, report)

        report.append("\n" + "=" * 60)
        return "\n".join(report)

    def _add_quality_report_sections(self, results: dict, report: list[str]):
        """Add quality report sections for passed/failed checks"""
        # Passed checks
        if results.get("passed"):
            report.append("\n✅ Passed Checks:")
            for check in results["passed"]:
                report.append(f"  • {check}")

        # Failed checks with details
        if results.get("failed"):
            report.append("\n❌ Failed Checks:")
            for check in results["failed"]:
                report.append(f"  • {check}")
                details = results.get("details", {}).get(check, {})
                if details.get("issues"):
                    for issue in details["issues"][:5]:  # Limit to first 5 issues
                        report.append(f"    → {issue}")
                    if len(details["issues"]) > 5:
                        report.append(f"    ... and {len(details['issues']) - 5} more issues")

    def _add_quality_recommendations(self, results: dict, report: list[str]):
        """Add quality recommendations to report"""
        failed_checks = str(results.get("failed", []))

        if "ruff" in failed_checks:
            report.append("  • Run 'ruff check --fix' to auto-fix formatting issues")
        if "mypy" in failed_checks:
            report.append("  • Add type hints to resolve mypy errors")
        if "bandit" in failed_checks:
            report.append("  • Review security issues and add '# nosec' for false positives")
        if "complexity" in failed_checks:
            report.append("  • Refactor complex functions to reduce cyclomatic complexity")
