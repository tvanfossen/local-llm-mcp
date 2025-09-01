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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.agent import Agent
from core.security import SecurityManager

logger = logging.getLogger(__name__)


class DeploymentManager:
    """Manages the deployment pipeline from agent workspace to production repository

    Enforces test coverage requirements and handles secure file transfers
    with full audit trail and rollback capabilities.
    """

    def __init__(self, security_manager: SecurityManager, workspace_root: Path):
        self.security_manager = security_manager
        self.workspace_root = workspace_root
        self.deployments_dir = workspace_root / "deployments"
        self.deployments_dir.mkdir(parents=True, exist_ok=True)

        # Deployment history
        self.history_file = self.deployments_dir / "deployment_history.json"
        self.pending_deployments: dict[str, dict[str, Any]] = {}

    def validate_test_coverage(self, agent: Agent) -> tuple[bool, float, str]:
        """Validate test coverage for agent's file

        Returns:
            Tuple of (meets_requirement, coverage_percentage, report)
        """
        try:
            # Get the test file for this agent
            test_file = self._get_test_file_path(agent)
            if not test_file.exists():
                return False, 0.0, "No test file found"

            # Get the main file
            main_file = agent.get_managed_file_path()
            if not main_file.exists():
                return False, 0.0, "Managed file not found"

            # Create temporary directory for testing
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Copy files to temp directory
                shutil.copy(main_file, temp_path / main_file.name)
                shutil.copy(test_file, temp_path / test_file.name)

                # Run pytest with coverage
                result = subprocess.run(
                    [
                        "pytest",
                        str(test_file.name),
                        f"--cov={main_file.stem}",
                        "--cov-report=json",
                        "--cov-report=term",
                        "-v",
                    ],
                    check=False,
                    cwd=temp_path,
                    capture_output=True,
                    text=True,
                )

                # Parse coverage report
                coverage_file = temp_path / ".coverage"
                if coverage_file.exists():
                    coverage_json = temp_path / "coverage.json"
                    if coverage_json.exists():
                        with open(coverage_json) as f:
                            coverage_data = json.load(f)

                        # Extract coverage percentage
                        totals = coverage_data.get("totals", {})
                        coverage_percent = totals.get("percent_covered", 0)

                        # Build report
                        report = f"Test Results:\n{result.stdout}\n\n"
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

                        return coverage_percent == 100, coverage_percent, report

                # Fallback: parse from stdout
                coverage_percent = self._parse_coverage_from_output(result.stdout)
                return coverage_percent == 100, coverage_percent, result.stdout

        except Exception as e:
            logger.error(f"Coverage validation failed: {e}")
            return False, 0.0, f"Error: {e!s}"

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
        """Generate diff between agent's file and target repository

        Returns:
            Tuple of (has_changes, diff_text, target_file_path)
        """
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
        """Stage a deployment for approval

        Returns:
            Tuple of (success, deployment_id, deployment_info)
        """
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
            deployment_id = f"{agent.state.agent_id}_{datetime.now().timestamp()}"

            deployment_info = {
                "deployment_id": deployment_id,
                "agent_id": agent.state.agent_id,
                "agent_name": agent.state.name,
                "managed_file": agent.state.managed_file,
                "source_path": str(agent.get_managed_file_path()),
                "target_path": target_path,
                "target_repo": str(target_repo),
                "has_changes": has_changes,
                "diff": diff_text,
                "coverage_percent": coverage_percent,
                "coverage_ok": coverage_ok,
                "coverage_report": coverage_report,
                "staged_by": session["client_name"],
                "staged_at": datetime.now(timezone.utc).isoformat(),
                "status": "staged" if coverage_ok else "failed_coverage",
            }

            self.pending_deployments[deployment_id] = deployment_info

            return True, deployment_id, deployment_info

        except Exception as e:
            logger.error(f"Staging failed: {e}")
            return False, "", {"error": str(e)}

    def execute_deployment(
        self,
        deployment_id: str,
        session_token: str,
    ) -> tuple[bool, str]:
        """Execute a staged deployment

        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate session
            valid, session = self.security_manager.validate_session(session_token)
            if not valid:
                return False, "Invalid session"

            # Get deployment info
            if deployment_id not in self.pending_deployments:
                return False, "Deployment not found"

            deployment = self.pending_deployments[deployment_id]

            # Verify coverage is still OK
            if not deployment["coverage_ok"]:
                return False, f"Coverage requirement not met: {deployment['coverage_percent']}%"

            # Authorize with security manager
            authorized, error = self.security_manager.authorize_deployment(
                session_token,
                deployment["agent_id"],
                Path(deployment["source_path"]),
                Path(deployment["target_path"]),
            )

            if not authorized:
                return False, f"Authorization failed: {error}"

            # Create backup if target exists
            target_path = Path(deployment["target_path"])
            backup_path = None

            if target_path.exists():
                backup_path = self.deployments_dir / f"backup_{deployment_id}_{target_path.name}"
                shutil.copy2(target_path, backup_path)
                logger.info(f"Created backup: {backup_path}")

            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            source_path = Path(deployment["source_path"])
            shutil.copy2(source_path, target_path)

            # Update deployment record
            deployment["status"] = "deployed"
            deployment["deployed_at"] = datetime.now(timezone.utc).isoformat()
            deployment["deployed_by"] = session["client_name"]
            deployment["backup_path"] = str(backup_path) if backup_path else None

            # Save to history
            self._save_deployment_history(deployment)

            # Remove from pending
            del self.pending_deployments[deployment_id]

            logger.info(f"Deployment successful: {deployment['managed_file']} -> {target_path}")
            return True, f"Successfully deployed {deployment['managed_file']}"

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False, f"Deployment error: {e!s}"

    def rollback_deployment(
        self,
        deployment_id: str,
        session_token: str,
    ) -> tuple[bool, str]:
        """Rollback a deployment

        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate session
            valid, session = self.security_manager.validate_session(session_token)
            if not valid:
                return False, "Invalid session"

            # Load deployment history
            history = self._load_deployment_history()

            # Find deployment
            deployment = None
            for entry in history:
                if entry.get("deployment_id") == deployment_id:
                    deployment = entry
                    break

            if not deployment:
                return False, "Deployment not found in history"

            if deployment.get("status") != "deployed":
                return False, "Deployment was not successfully deployed"

            # Check if backup exists
            backup_path = deployment.get("backup_path")
            if not backup_path or not Path(backup_path).exists():
                return False, "No backup available for rollback"

            # Restore from backup
            target_path = Path(deployment["target_path"])
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
            logger.error(f"Rollback failed: {e}")
            return False, f"Rollback error: {e!s}"

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
        """Run pre-commit quality gates on agent's file

        Returns:
            Tuple of (all_checks_passed, results_dict, detailed_report)
        """
        try:
            file_path = agent.get_managed_file_path()
            if not file_path.exists():
                return False, {}, "File not found"

            # Create a temporary git repo for pre-commit to work
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Initialize git repo (pre-commit needs git)
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

                # Run pre-commit hooks
                result = subprocess.run(
                    ["pre-commit", "run", "--all-files", "--verbose"],
                    check=False,
                    cwd=temp_path,
                    capture_output=True,
                    text=True,
                )

                # Parse results
                quality_results = self._parse_precommit_output(result.stdout, result.stderr)

                # Build detailed report
                report = self._build_quality_report(quality_results)

                # Determine if all checks passed
                all_passed = result.returncode == 0

                return all_passed, quality_results, report

        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            return False, {"error": str(e)}, f"Error running quality checks: {e!s}"

    def _parse_precommit_output(self, stdout: str, stderr: str) -> dict[str, Any]:
        """Parse pre-commit output into structured results"""
        results = {
            "checks_run": [],
            "passed": [],
            "failed": [],
            "skipped": [],
            "details": {},
        }

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
        """Build human-readable quality report"""
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

        # Recommendations
        if results.get("failed"):
            report.append("\n💡 Recommendations:")
            if "ruff" in str(results.get("failed")):
                report.append("  • Run 'ruff check --fix' to auto-fix formatting issues")
            if "mypy" in str(results.get("failed")):
                report.append("  • Add type hints to resolve mypy errors")
            if "bandit" in str(results.get("failed")):
                report.append("  • Review security issues and add '# nosec' for false positives")
            if "complexity" in str(results.get("failed")):
                report.append("  • Refactor complex functions to reduce cyclomatic complexity")

        report.append("\n" + "=" * 60)
        return "\n".join(report)
