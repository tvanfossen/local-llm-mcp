"""Git Operations Tool - Unified git operations

Responsibilities:
- All git operations (status, diff, commit, log, branch, etc.)
- Batch git operations
- Repository information
- Safe git command execution
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from src.core.utils.utils import create_mcp_response, create_response, get_workspace_root, handle_exception

logger = logging.getLogger(__name__)


class GitOperations:
    """Consolidated git operations handler"""

    def __init__(self, repo_path: Optional[Path] = None):
        """Initialize with repository path"""
        self.repo_path = repo_path or get_workspace_root()
        self.repo_path = self.repo_path.resolve()

        # Verify git repository
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")

    def _run_git_command(self, args: list[str], check: bool = True) -> dict:
        """Run a git command and return result"""
        try:
            result = subprocess.run(["git"] + args, cwd=self.repo_path, capture_output=True, text=True, check=check)

            return {
                "success": True,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            }

        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "stdout": e.stdout.strip() if e.stdout else "",
                "stderr": e.stderr.strip() if e.stderr else "",
                "returncode": e.returncode,
                "error": str(e),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Git Operations

    def status(self, short: bool = False, branch: bool = True) -> dict:
        """Get repository status"""
        args = ["status"]
        if short:
            args.append("--short")
        if branch:
            args.append("--branch")

        result = self._run_git_command(args)

        if result["success"]:
            # Parse status for structured output
            lines = result["stdout"].split("\n")
            status_data = {"branch": "", "staged": [], "modified": [], "untracked": [], "raw": result["stdout"]}

            if short:
                for line in lines:
                    if line.startswith("##"):
                        status_data["branch"] = line[3:].strip()
                    elif line.startswith("M "):
                        status_data["modified"].append(line[3:])
                    elif line.startswith("A "):
                        status_data["staged"].append(line[3:])
                    elif line.startswith("??"):
                        status_data["untracked"].append(line[3:])

            return create_response(True, status_data)
        else:
            return create_response(False, error=result.get("error", "Git status failed"))

    def diff(self, staged: bool = False, file_path: Optional[str] = None) -> dict:
        """Get repository diff"""
        args = ["diff"]
        if staged:
            args.append("--staged")
        if file_path:
            args.append(file_path)

        result = self._run_git_command(args)

        if result["success"]:
            diff_lines = result["stdout"].split("\n")

            # Parse diff for summary
            files_changed = []
            additions = 0
            deletions = 0

            for line in diff_lines:
                if line.startswith("+++") or line.startswith("---"):
                    if line[4:] and line[4:] != "/dev/null":
                        files_changed.append(line[4:])
                elif line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1

            return create_response(
                True,
                {
                    "files_changed": list(set(files_changed)),
                    "additions": additions,
                    "deletions": deletions,
                    "diff": result["stdout"],
                },
            )
        else:
            return create_response(False, error=result.get("error", "Git diff failed"))

    def commit(self, message: str, add_all: bool = False, files: Optional[list[str]] = None) -> dict:
        """Create a commit"""
        if not message:
            return create_response(False, error="Commit message required")

        # Stage files if needed
        if add_all:
            stage_result = self._run_git_command(["add", "-A"])
            if not stage_result["success"]:
                return create_response(False, error="Failed to stage files")
        elif files:
            stage_result = self._run_git_command(["add"] + files)
            if not stage_result["success"]:
                return create_response(False, error="Failed to stage specified files")

        # Create commit
        result = self._run_git_command(["commit", "-m", message])

        if result["success"]:
            # Get commit hash
            hash_result = self._run_git_command(["rev-parse", "HEAD"])
            commit_hash = hash_result["stdout"][:8] if hash_result["success"] else "unknown"

            return create_response(True, {"commit_hash": commit_hash, "message": message, "output": result["stdout"]})
        else:
            return create_response(False, error=result.get("stderr", "Commit failed"))

    def log(self, limit: int = 10, oneline: bool = True, author: Optional[str] = None) -> dict:
        """Get commit log"""
        args = ["log"]

        if limit:
            args.extend(["-n", str(limit)])
        if oneline:
            args.append("--oneline")
        if author:
            args.extend(["--author", author])

        result = self._run_git_command(args)

        if result["success"]:
            commits = []

            if oneline:
                for line in result["stdout"].split("\n"):
                    if line:
                        parts = line.split(" ", 1)
                        if len(parts) == 2:
                            commits.append({"hash": parts[0], "message": parts[1]})

            return create_response(True, {"commits": commits, "count": len(commits), "raw": result["stdout"]})
        else:
            return create_response(False, error=result.get("error", "Git log failed"))

    def branch(self, action: str = "list", name: Optional[str] = None, delete: bool = False) -> dict:
        """Manage branches"""
        if action == "list":
            result = self._run_git_command(["branch", "-a"])

            if result["success"]:
                branches = {"current": "", "local": [], "remote": []}

                for line in result["stdout"].split("\n"):
                    line = line.strip()
                    if line.startswith("*"):
                        branches["current"] = line[2:]
                        branches["local"].append(line[2:])
                    elif line.startswith("remotes/"):
                        branches["remote"].append(line)
                    elif line:
                        branches["local"].append(line)

                return create_response(True, branches)

        elif action == "create" and name:
            result = self._run_git_command(["branch", name])
            return create_response(
                result["success"], {"created": name} if result["success"] else None, result.get("stderr")
            )

        elif action == "checkout" and name:
            result = self._run_git_command(["checkout", name])
            return create_response(
                result["success"], {"checked_out": name} if result["success"] else None, result.get("stderr")
            )

        elif action == "delete" and name:
            flag = "-D" if delete else "-d"
            result = self._run_git_command(["branch", flag, name])
            return create_response(
                result["success"], {"deleted": name} if result["success"] else None, result.get("stderr")
            )

        else:
            return create_response(False, error=f"Invalid branch action: {action}")

    def stash(self, action: str = "list", message: Optional[str] = None) -> dict:
        """Manage stashes"""
        if action == "list":
            result = self._run_git_command(["stash", "list"])

            if result["success"]:
                stashes = []
                for line in result["stdout"].split("\n"):
                    if line:
                        stashes.append(line)

                return create_response(True, {"stashes": stashes, "count": len(stashes)})

        elif action == "save":
            args = ["stash", "save"]
            if message:
                args.append(message)

            result = self._run_git_command(args)
            return create_response(
                result["success"],
                {"message": message or "Stashed changes"} if result["success"] else None,
                result.get("stderr"),
            )

        elif action == "pop":
            result = self._run_git_command(["stash", "pop"])
            return create_response(
                result["success"], {"action": "Stash popped"} if result["success"] else None, result.get("stderr")
            )

        else:
            return create_response(False, error=f"Invalid stash action: {action}")

    def remote(self, action: str = "list") -> dict:
        """Manage remotes"""
        if action == "list":
            result = self._run_git_command(["remote", "-v"])

            if result["success"]:
                remotes = {}
                for line in result["stdout"].split("\n"):
                    if line:
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0]
                            url = parts[1]
                            if name not in remotes:
                                remotes[name] = {"url": url}

                return create_response(True, remotes)

        else:
            return create_response(False, error=f"Invalid remote action: {action}")


# MCP Tool Interface
async def git_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Unified git operations tool

    Operations:
    - status: Get repository status
    - diff: Show changes
    - commit: Create a commit
    - log: Show commit history
    - branch: Manage branches (list, create, checkout, delete)
    - stash: Manage stashes (list, save, pop)
    - remote: Manage remotes (list)
    """
    action = args.get("action")

    if not action:
        return create_mcp_response(
            False, "Action parameter required. Available: status, diff, commit, log, branch, stash, remote"
        )

    # Initialize git operations
    try:
        ops = GitOperations(args.get("repo_path"))
    except ValueError as e:
        return create_mcp_response(False, str(e))

    # Route to appropriate action
    try:
        if action == "status":
            result = ops.status(args.get("short", False), args.get("branch", True))

        elif action == "diff":
            result = ops.diff(args.get("staged", False), args.get("file_path"))

        elif action == "commit":
            result = ops.commit(args.get("message", ""), args.get("add_all", False), args.get("files"))

        elif action == "log":
            result = ops.log(args.get("limit", 10), args.get("oneline", True), args.get("author"))

        elif action == "branch":
            result = ops.branch(args.get("action", "list"), args.get("name"), args.get("delete", False))

        elif action == "stash":
            result = ops.stash(args.get("action", "list"), args.get("message"))

        elif action == "remote":
            result = ops.remote(args.get("action", "list"))

        else:
            return create_mcp_response(False, f"Unknown action '{action}'")

        # Convert internal response to MCP format
        return create_mcp_response(
            result["success"], result["data"] if result["success"] else result["error"], is_json=result["success"]
        )

    except Exception as e:
        return handle_exception(e, "Git Tool")
