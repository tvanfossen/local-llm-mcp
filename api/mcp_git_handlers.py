import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MCPGitHandlers:
    """Git-specific MCP tool handlers"""

    @staticmethod
    def _create_success(text: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": text}], "isError": False}

    @staticmethod
    def _create_error(title: str, message: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}

    @staticmethod
    def _handle_exception(e: Exception, context: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": f"❌ **{context} Error:** {str(e)}"}], "isError": True}

    async def git_status(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Check git repository status and changes"""
        try:
            result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=Path.cwd())
            return self._process_git_status_result(result)
        except Exception as e:
            return self._handle_exception(e, "Git Status")

    def _process_git_status_result(self, result) -> dict[str, Any]:
        """Process git status command result"""
        if result.returncode != 0:
            return self._create_error("Git Status Failed", f"Git error: {result.stderr}")

        status_output = result.stdout.strip()
        if not status_output:
            return self._create_success("🌿 **Git Status:** Working directory clean")

        return self._create_success(self._format_git_status(status_output))

    def _format_git_status(self, status_output: str) -> str:
        """Format git status output"""
        lines = status_output.split("\n")
        modified, staged, untracked = [], [], []

        for line in lines:
            if len(line) < 3:
                continue
            status_code, filename = line[:2], line[3:]

            if status_code[0] not in [" ", "?"]:
                staged.append(f"  📝 {filename}")
            if status_code[1] != " ":
                modified.append(f"  ⚠️ {filename}")
            if status_code == "??":
                untracked.append(f"  ❓ {filename}")

        response = "🌿 **Git Status:**\n\n"
        if staged:
            response += "**Staged Changes:**\n" + "\n".join(staged) + "\n\n"
        if modified:
            response += "**Modified Files:**\n" + "\n".join(modified) + "\n\n"
        if untracked:
            response += "**Untracked Files:**\n" + "\n".join(untracked)
        return response

    async def git_diff(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Show git diff of changes"""
        try:
            file_path = args.get("file_path") if args else None
            staged = args.get("staged", False) if args else False

            cmd = ["git", "diff"]
            if staged:
                cmd.append("--cached")
            if file_path:
                cmd.append(file_path)

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
            return self._process_git_diff_result(result, file_path, staged)
        except Exception as e:
            return self._handle_exception(e, "Git Diff")

    def _process_git_diff_result(self, result, file_path: str, staged: bool) -> dict[str, Any]:
        """Process git diff command result"""
        if result.returncode != 0:
            return self._create_error("Git Diff Failed", f"Git error: {result.stderr}")

        diff_output = result.stdout.strip()
        if not diff_output:
            scope = "staged changes" if staged else "working directory"
            target = f" for {file_path}" if file_path else ""
            return self._create_success(f"📋 **Git Diff:** No changes in {scope}{target}")

        return self._create_success(self._format_git_diff(diff_output, file_path, staged))

    def _format_git_diff(self, diff_output: str, file_path: str, staged: bool) -> str:
        """Format git diff output"""
        if len(diff_output) > 2000:
            diff_output = diff_output[:2000] + "\n... (diff truncated)"

        scope_text = "Staged Changes" if staged else "Working Directory Changes"
        target_text = f" - {file_path}" if file_path else ""
        return f"📋 **Git Diff - {scope_text}{target_text}:**\n\n```diff\n{diff_output}\n```"

    async def git_commit(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create git commit with message"""
        try:
            message = args.get("message")
            if not message:
                return self._create_error("Missing Parameter", "commit message is required")

            files = args.get("files", [])
            add_result = self._add_files_to_git(files)
            if add_result:
                return add_result

            return self._create_git_commit(message, files)
        except Exception as e:
            return self._handle_exception(e, "Git Commit")

    def _add_files_to_git(self, files: list) -> dict[str, Any] | None:
        """Add files to git staging area"""
        if files:
            for file_path in files:
                result = subprocess.run(["git", "add", file_path], capture_output=True, text=True, cwd=Path.cwd())
                if result.returncode != 0:
                    return self._create_error("Git Add Failed", f"Failed to add {file_path}: {result.stderr}")
        else:
            result = subprocess.run(["git", "add", "."], capture_output=True, text=True, cwd=Path.cwd())
            if result.returncode != 0:
                return self._create_error("Git Add Failed", f"Failed to add files: {result.stderr}")
        return None

    def _create_git_commit(self, message: str, files: list) -> dict[str, Any]:
        """Create git commit"""
        result = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True, cwd=Path.cwd())

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            if "nothing to commit" in error_msg:
                return self._create_success("✅ **Git Commit:** Nothing to commit, working directory clean")
            return self._create_error("Git Commit Failed", f"Commit error: {error_msg}")

        commit_hash = self._extract_commit_hash(result.stdout.strip())
        return self._create_success(
            f"✅ **Git Commit Successful**\n\n"
            f"**Hash:** {commit_hash}\n"
            f"**Message:** {message}\n"
            f"**Files:** {'Specific files' if files else 'All changes'}"
        )

    def _extract_commit_hash(self, commit_output: str) -> str:
        """Extract commit hash from git commit output"""
        if not commit_output:
            return ""
        first_line = commit_output.split("\n")[0]
        if "[" in first_line and "]" in first_line:
            return first_line.split("[")[1].split("]")[0].split()[0]
        return ""

    async def git_log(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Show git commit history"""
        try:
            limit = args.get("limit", 10) if args else 10
            file_path = args.get("file_path") if args else None

            cmd = ["git", "log", "--oneline", f"-{limit}"]
            if file_path:
                cmd.append(file_path)

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
            return self._process_git_log_result(result, file_path)
        except Exception as e:
            return self._handle_exception(e, "Git Log")

    def _process_git_log_result(self, result, file_path: str) -> dict[str, Any]:
        """Process git log command result"""
        if result.returncode != 0:
            return self._create_error("Git Log Failed", f"Git error: {result.stderr}")

        log_output = result.stdout.strip()
        if not log_output:
            scope = f" for {file_path}" if file_path else ""
            return self._create_success(f"📜 **Git Log:** No commits found{scope}")

        target_text = f" - {file_path}" if file_path else ""
        return self._create_success(f"📜 **Git Log{target_text}:**\n\n```\n{log_output}\n```")
