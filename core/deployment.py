# File: ~/Projects/local-llm-mcp/core/deployment.py
"""Git-Based Deployment Manager

Responsibilities:
- Test coverage validation for direct file access in repository
- Git-based diff generation and status checking
- Simplified deployment via git operations (add/commit/push)
- Git-based rollback capabilities using git history
- Security audit logging for all git operations
- Code quality validation in repository context
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.agent import Agent
from core.security import SecurityManager

logger = logging.getLogger(__name__)


@dataclass
class GitDeploymentInfo:
    """Container for git deployment information"""

    agent_id: str
    agent_name: str
    managed_file: str
    repo_path: Path
    has_changes: bool
    git_status: str
    diff_text: str
    coverage_percent: float
    coverage_ok: bool
    coverage_report: str
    staged_by: str


@dataclass
class ValidationResult:
    """Container for validation results"""

    success: bool
    error_message: str = ""
    data: dict = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class DeploymentManager:
    """Git-based deployment manager for agents working directly in repository"""

    def __init__(self, security_manager: SecurityManager, workspace_root: Path):
        self.security_manager = security_manager
        self.workspace_root = workspace_root
        self.deployments_dir = workspace_root / ".mcp-agents" / "deployments"
        self.deployments_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.deployments_dir / "git_deployment_history.json"
        self.pending_deployments: dict[str, dict[str, Any]] = {}

    def validate_test_coverage(self, agent: Agent) -> tuple[bool, float, str]:
        """Validate test coverage for agent's file using direct repository access"""
        main_file = agent.get_managed_file_path()
        if not main_file.exists():
            return False, 0.0, "Managed file not found in repository"

        test_file = self._find_test_file(agent)
        return self._execute_coverage_validation(test_file, main_file)

    def _find_test_file(self, agent: Agent) -> Path:
        """Find test file for agent's managed file"""
        managed_file = Path(agent.state.managed_file)
        test_name = f"test_{managed_file.stem}{managed_file.suffix}"

        locations = [
            self.workspace_root / "tests" / test_name,
            self.workspace_root / "test" / test_name,
            self.workspace_root / test_name,
        ]

        for test_path in locations:
            if test_path.exists():
                return test_path

        return self.workspace_root / "tests" / test_name

    def _execute_coverage_validation(self, test_file: Path, main_file: Path) -> tuple[bool, float, str]:
        """Execute coverage test with simplified logic to reduce complexity"""
        if not test_file.exists():
            return False, 0.0, f"Test file not found: {test_file}"

        try:
            # Run pytest with coverage
            result = self._run_pytest_coverage(test_file, main_file)
            coverage_data = self._process_coverage_results(result)
            return coverage_data
        except Exception as e:
            return False, 0.0, f"Coverage test error: {e!s}"

    def _run_pytest_coverage(self, test_file: Path, main_file: Path):
        """Run pytest with coverage in simplified form"""
        return subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                str(test_file.relative_to(self.workspace_root)),
                f"--cov={main_file.stem}",
                "--cov-report=json",
                "--cov-report=term",
                "-v",
            ],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

    def _process_coverage_results(self, result) -> tuple[bool, float, str]:
        """Process coverage results with simplified logic"""
        coverage_json = self.workspace_root / "coverage.json"

        # Try JSON coverage first
        if coverage_json.exists():
            coverage_data = self._extract_json_coverage(coverage_json, result.stdout)
            return coverage_data

        # Fall back to stdout parsing
        coverage_percent = self._parse_coverage_from_stdout(result.stdout)
        return coverage_percent == 100, coverage_percent, result.stdout

    def _extract_json_coverage(self, coverage_json: Path, stdout: str) -> tuple[bool, float, str]:
        """Extract coverage from JSON file"""
        try:
            with open(coverage_json) as f:
                coverage_data = json.load(f)

            coverage_json.unlink()  # Clean up
            coverage_percent = coverage_data.get("totals", {}).get("percent_covered", 0)
            report = self._build_coverage_report(stdout, coverage_percent, coverage_data)
            return coverage_percent == 100, coverage_percent, report
        except Exception as e:
            logger.error(f"JSON coverage parse failed: {e}")
            coverage_percent = self._parse_coverage_from_stdout(stdout)
            return coverage_percent == 100, coverage_percent, stdout

    def _parse_coverage_from_stdout(self, output: str) -> float:
        """Parse coverage percentage from pytest output - max 3 returns"""
        lines = output.split("\n")
        total_lines = [line for line in lines if "TOTAL" in line and "%" in line]

        if not total_lines:
            return 0.0

        parts = total_lines[0].split()
        percent_parts = [part for part in parts if part.endswith("%")]

        if percent_parts:
            try:
                return float(percent_parts[0].rstrip("%"))
            except (ValueError, IndexError):
                pass

        return 0.0

    def _build_coverage_report(self, stdout: str, coverage_percent: float, coverage_data: dict) -> str:
        """Build detailed coverage report with minimal complexity"""
        report = f"Repository Test Results:\n{stdout}\n\nCoverage: {coverage_percent:.1f}%\n"

        if coverage_percent == 100:
            return report + "✅ 100% coverage achieved!"

        # Show uncovered lines if available
        uncovered_info = self._extract_uncovered_lines(coverage_data)
        return report + uncovered_info

    def _extract_uncovered_lines(self, coverage_data: dict) -> str:
        """Extract uncovered lines information"""
        uncovered_info = ""
        for filename, file_data in coverage_data.get("files", {}).items():
            uncovered = file_data.get("missing_lines", [])
            if uncovered:
                uncovered_info += f"\nUncovered lines in {filename}: {uncovered}"
        return uncovered_info

    def generate_diff(self, agent: Agent, target_repo: Path) -> tuple[bool, str, str]:
        """Generate git diff for agent's managed file"""
        try:
            return self._get_git_diff(agent.state.managed_file)
        except Exception as e:
            logger.error(f"Git diff failed: {e}")
            return False, f"Git diff error: {e!s}", f"Error checking {agent.state.managed_file}"

    def _get_git_diff(self, managed_file: str) -> tuple[bool, str, str]:
        """Get git diff for managed file"""
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", managed_file],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            has_changes = bool(result.stdout.strip())
            return has_changes, result.stdout, f"git diff for {managed_file}"

        return self._handle_untracked_file(managed_file)

    def _handle_untracked_file(self, managed_file: str) -> tuple[bool, str, str]:
        """Handle untracked file diff generation"""
        status_result = subprocess.run(
            ["git", "status", "--porcelain", managed_file],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if not status_result.stdout.strip():
            return False, "", f"No changes detected for {managed_file}"

        return self._create_new_file_diff(managed_file)

    def _create_new_file_diff(self, managed_file: str) -> tuple[bool, str, str]:
        """Create diff for new file"""
        file_path = self.workspace_root / managed_file
        if not file_path.exists():
            return False, "", f"File not found: {managed_file}"

        content = file_path.read_text()
        diff_text = f"New file: {managed_file}\n+++ {managed_file}\n"
        for line_num, line in enumerate(content.split("\n"), 1):
            diff_text += f"+{line_num:4d}: {line}\n"

        return True, diff_text, f"New file: {managed_file}"

    def get_git_status(self, agent: Agent = None) -> dict[str, Any]:
        """Get git status for repository or specific agent file"""
        try:
            if agent:
                return self._get_agent_git_status(agent)
            return self._get_repo_git_status()
        except Exception as e:
            logger.error(f"Git status check failed: {e}")
            return {"error": str(e), "has_changes": False}

    def _get_agent_git_status(self, agent: Agent) -> dict[str, Any]:
        """Get git status for specific agent file"""
        result = subprocess.run(
            ["git", "status", "--porcelain", agent.state.managed_file],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "file": agent.state.managed_file,
            "status": result.stdout.strip(),
            "has_changes": bool(result.stdout.strip()),
        }

    def _get_repo_git_status(self) -> dict[str, Any]:
        """Get overall repository git status"""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        changes = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return {
            "total_changes": len(changes),
            "changes": changes,
            "has_changes": bool(changes),
        }

    def stage_deployment(self, agent: Agent, target_repo: Path, session_token: str) -> tuple[bool, str, dict[str, Any]]:
        """Stage a git-based deployment for approval"""
        valid, session = self.security_manager.validate_session(session_token)
        if not valid:
            return False, "", {"error": "Invalid session"}

        try:
            deployment_data = self._gather_deployment_data(agent, session)
            deployment_record = self._create_deployment_record(deployment_data)
            deployment_id = deployment_record["deployment_id"]
            self.pending_deployments[deployment_id] = deployment_record
            return True, deployment_id, deployment_record
        except Exception as e:
            logger.error(f"Deployment staging failed: {e}")
            return False, "", {"error": str(e)}

    def _gather_deployment_data(self, agent: Agent, session: dict) -> GitDeploymentInfo:
        """Gather all data needed for git deployment"""
        coverage_ok, coverage_percent, coverage_report = self.validate_test_coverage(agent)
        git_status_info = self.get_git_status(agent)
        has_changes, diff_text, diff_summary = self.generate_diff(agent, self.workspace_root)

        return GitDeploymentInfo(
            agent_id=agent.state.agent_id,
            agent_name=agent.state.name,
            managed_file=agent.state.managed_file,
            repo_path=self.workspace_root,
            has_changes=has_changes,
            git_status=git_status_info.get("status", ""),
            diff_text=diff_text,
            coverage_percent=coverage_percent,
            coverage_ok=coverage_ok,
            coverage_report=coverage_report,
            staged_by=session["client_name"],
        )

    def _create_deployment_record(self, info: GitDeploymentInfo) -> dict[str, Any]:
        """Create git deployment record"""
        deployment_id = f"git_{info.agent_id}_{int(datetime.now().timestamp())}"
        return {
            "deployment_id": deployment_id,
            "deployment_type": "git",
            "agent_id": info.agent_id,
            "agent_name": info.agent_name,
            "managed_file": info.managed_file,
            "repo_path": str(info.repo_path),
            "has_changes": info.has_changes,
            "git_status": info.git_status,
            "diff": info.diff_text,
            "coverage_percent": info.coverage_percent,
            "coverage_ok": info.coverage_ok,
            "coverage_report": info.coverage_report,
            "staged_by": info.staged_by,
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "status": "staged" if info.coverage_ok else "failed_coverage",
            "commit_message": f"Update {info.managed_file} via agent {info.agent_name}",
        }

    def execute_deployment(self, deployment_id: str, session_token: str) -> tuple[bool, str]:
        """Execute git deployment: add -> commit -> push"""
        validation_result = self._validate_deployment_request(deployment_id, session_token)
        if not validation_result.success:
            return False, validation_result.error_message

        deployment = validation_result.data["deployment"]
        session = validation_result.data["session"]

        try:
            success, message = self._execute_git_workflow(deployment, session)
            if success:
                self._finalize_deployment(deployment, session)
            return success, message
        except Exception as e:
            logger.error(f"Deployment execution failed: {e}")
            return False, f"Git deployment failed: {e!s}"

    def _validate_deployment_request(self, deployment_id: str, session_token: str) -> ValidationResult:
        """Validate deployment prerequisites with consolidated returns"""
        valid, session = self.security_manager.validate_session(session_token)
        if not valid:
            return ValidationResult(False, "Invalid session")

        if deployment_id not in self.pending_deployments:
            return ValidationResult(False, "Deployment not found")

        deployment = self.pending_deployments[deployment_id]
        success = deployment["coverage_ok"]
        error_msg = "" if success else f"Coverage requirement not met: {deployment['coverage_percent']}%"
        data = {"deployment": deployment, "session": session} if success else {}

        return ValidationResult(success, error_msg, data=data)

    def _execute_git_workflow(self, deployment: dict, session: dict) -> tuple[bool, str]:
        """Execute the git add -> commit -> push workflow"""
        managed_file = deployment["managed_file"]
        commit_message = deployment["commit_message"]

        try:
            self._git_add_file(managed_file)
            commit_hash = self._git_commit_changes(commit_message, session)
            push_result = self._git_push_changes()

            message = f"Git deployment successful: {managed_file}"
            if commit_hash:
                message += f" (commit: {commit_hash[:8]})"
            if push_result:
                message += " - pushed to remote"

            logger.info(message)
            return True, message
        except Exception as e:
            logger.error(f"Git workflow failed: {e}")
            return False, f"Git workflow failed: {e!s}"

    def _finalize_deployment(self, deployment: dict, session: dict):
        """Finalize deployment record"""
        deployment["status"] = "deployed"
        deployment["deployed_at"] = datetime.now(timezone.utc).isoformat()
        deployment["deployed_by"] = session["client_name"]
        self._save_deployment_history(deployment)

    def _git_add_file(self, managed_file: str):
        """Add file to git staging area"""
        subprocess.run(
            ["git", "add", managed_file],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"Git add successful: {managed_file}")

    def _git_commit_changes(self, commit_message: str, session: dict) -> str:
        """Commit staged changes"""
        env = {
            "GIT_AUTHOR_NAME": session.get("client_name", "MCP Agent"),
            "GIT_AUTHOR_EMAIL": f"{session.get('client_name', 'agent')}@mcp-local",
            "GIT_COMMITTER_NAME": "MCP Deployment System",
            "GIT_COMMITTER_EMAIL": "mcp-deployment@local",
        }

        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, **env},
            check=True,
        )

        commit_hash = self._get_latest_commit_hash()
        logger.info(f"Git commit successful: {commit_hash}")
        return commit_hash

    def _get_latest_commit_hash(self) -> str:
        """Get the latest commit hash"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()[:8]
        except Exception:
            return ""

    def _git_push_changes(self) -> bool:
        """Push changes to remote if available"""
        try:
            if not self._has_git_remote():
                return False

            push_result = subprocess.run(
                ["git", "push"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            success = push_result.returncode == 0
            if success:
                logger.info("Git push successful")
            else:
                logger.warning(f"Git push failed: {push_result.stderr}")

            return success
        except Exception as e:
            logger.warning(f"Git push failed: {e}")
            return False

    def _has_git_remote(self) -> bool:
        """Check if git remote exists"""
        result = subprocess.run(
            ["git", "remote"],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

        has_remote = bool(result.stdout.strip())
        if not has_remote:
            logger.info("No git remote configured, skipping push")

        return has_remote

    def rollback_deployment(self, deployment_id: str, session_token: str) -> tuple[bool, str]:
        """Rollback deployment using git revert"""
        valid, session = self.security_manager.validate_session(session_token)
        if not valid:
            return False, "Invalid session"

        try:
            return self._process_rollback_request(deployment_id, session)
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False, f"Rollback failed: {e!s}"

    def _process_rollback_request(self, deployment_id: str, session: dict) -> tuple[bool, str]:
        """Process rollback request with consolidated logic"""
        deployment = self._find_deployment_in_history(deployment_id)
        if not deployment:
            return False, "Deployment not found in history"

        if deployment.get("status") != "deployed":
            return False, "Only deployed commits can be rolled back"

        # Execute rollback workflow
        managed_file = deployment.get("managed_file", "")
        success = self._perform_git_rollback(managed_file)

        if success:
            self._finalize_rollback(managed_file, deployment, session)

        message = f"Successfully rolled back {managed_file}" if success else "Git rollback operation failed"
        return success, message

    def _perform_git_rollback(self, managed_file: str) -> bool:
        """Perform git rollback operation"""
        try:
            revert_result = subprocess.run(
                ["git", "checkout", "HEAD~1", "--", managed_file],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )

            success = revert_result.returncode == 0
            if not success:
                logger.error(f"Git rollback failed: {revert_result.stderr}")

            return success
        except Exception as e:
            logger.error(f"Git rollback operation failed: {e}")
            return False

    def _finalize_rollback(self, managed_file: str, deployment: dict, session: dict):
        """Finalize rollback by committing and updating records"""
        revert_commit_message = f"Revert: {deployment.get('commit_message', '')}"
        self._git_add_file(managed_file)
        self._git_commit_changes(revert_commit_message, session)

        deployment["status"] = "rolled_back"
        deployment["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        deployment["rolled_back_by"] = session["client_name"]

        self._save_deployment_history(deployment)
        logger.info(f"Rollback finalized: {managed_file}")

    def _find_deployment_in_history(self, deployment_id: str) -> dict | None:
        """Find deployment in history"""
        history = self._load_deployment_history()
        for entry in history:
            if entry.get("deployment_id") == deployment_id:
                return entry
        return None

    def _save_deployment_history(self, deployment: dict[str, Any]):
        """Save deployment to history"""
        history = self._load_deployment_history()

        # Update existing or add new
        updated = False
        for i, entry in enumerate(history):
            if entry.get("deployment_id") == deployment["deployment_id"]:
                history[i] = deployment
                updated = True
                break

        if not updated:
            history.append(deployment)

        # Keep last 1000 entries
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
        status_counts = self._count_statuses(history)
        repo_status = self.get_git_status()

        return {
            "deployment_type": "git-based",
            "pending_deployments": len(self.pending_deployments),
            "total_git_deployments": len(history),
            "status_breakdown": status_counts,
            "recent_deployments": history[-10:] if history else [],
            "repository_status": repo_status,
            "git_enabled": self._check_git_repository(),
        }

    def _count_statuses(self, history: list) -> dict[str, int]:
        """Count deployments by status"""
        status_counts = {}
        for entry in history:
            status = entry.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts

    def _check_git_repository(self) -> bool:
        """Check if workspace is a git repository"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def validate_code_quality(self, agent: Agent) -> tuple[bool, dict[str, Any], str]:
        """Run code quality checks in repository"""
        file_path = agent.get_managed_file_path()
        if not file_path.exists():
            return False, {}, "File not found in repository"

        try:
            quality_results = self._run_quality_checks(agent.state.managed_file)
            report = self._build_quality_report(quality_results)
            all_passed = quality_results.get("returncode", 1) == 0
            return all_passed, quality_results, report
        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            return False, {"error": str(e)}, f"Error running quality checks: {e!s}"

    def _run_quality_checks(self, managed_file: str) -> dict[str, Any]:
        """Run quality checks on file"""
        precommit_config = self.workspace_root / ".pre-commit-config.yaml"

        if precommit_config.exists():
            result = subprocess.run(
                ["pre-commit", "run", "--files", managed_file],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )
            tool = "pre-commit"
        else:
            result = subprocess.run(
                ["python", "-m", "py_compile", managed_file],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )
            tool = "py_compile"

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "quality_tool": tool,
        }

    def _build_quality_report(self, results: dict[str, Any]) -> str:
        """Build quality report"""
        tool = results.get("quality_tool", "unknown")
        returncode = results.get("returncode", 1)

        if returncode == 0:
            return f"✅ All {tool} checks passed!"

        report = f"❌ {tool} checks failed:\n"
        if results.get("stderr"):
            report += f"\nErrors:\n{results['stderr']}\n"
        if results.get("stdout"):
            report += f"\nOutput:\n{results['stdout']}\n"

        return report
