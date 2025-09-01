# File: ~/Projects/local-llm-mcp/core/deployment.py
"""
Deployment Manager

Responsibilities:
- Test coverage validation
- File diff generation
- Secure file deployment to host repositories
- Rollback capabilities
"""

import json
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timezone
import difflib
import tempfile

from core.agent import Agent
from core.security import SecurityManager

logger = logging.getLogger(__name__)

class DeploymentManager:
    """
    Manages the deployment pipeline from agent workspace to production repository
    
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
        self.pending_deployments: Dict[str, Dict[str, Any]] = {}
        
    def validate_test_coverage(self, agent: Agent) -> Tuple[bool, float, str]:
        """
        Validate test coverage for agent's file
        
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
                        "-v"
                    ],
                    cwd=temp_path,
                    capture_output=True,
                    text=True
                )
                
                # Parse coverage report
                coverage_file = temp_path / ".coverage"
                if coverage_file.exists():
                    coverage_json = temp_path / "coverage.json"
                    if coverage_json.exists():
                        with open(coverage_json, 'r') as f:
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
            return False, 0.0, f"Error: {str(e)}"
    
    def _parse_coverage_from_output(self, output: str) -> float:
        """Parse coverage percentage from pytest output"""
        try:
            lines = output.split('\n')
            for line in lines:
                if 'TOTAL' in line and '%' in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith('%'):
                            return float(part.rstrip('%'))
        except:
            pass
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
    
    def generate_diff(self, agent: Agent, target_repo: Path) -> Tuple[bool, str, str]:
        """
        Generate diff between agent's file and target repository
        
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
            with open(source_file, 'r') as f:
                source_content = f.readlines()
            
            # Read target content if exists
            target_content = []
            if target_file.exists():
                with open(target_file, 'r') as f:
                    target_content = f.readlines()
            
            # Generate unified diff
            diff = difflib.unified_diff(
                target_content,
                source_content,
                fromfile=f"a/{agent.state.managed_file}",
                tofile=f"b/{agent.state.managed_file}",
                lineterm=''
            )
            
            diff_text = '\n'.join(diff)
            has_changes = len(diff_text) > 0
            
            return has_changes, diff_text, str(target_file)
            
        except Exception as e:
            logger.error(f"Diff generation failed: {e}")
            return False, f"Error: {str(e)}", ""
    
    def stage_deployment(
        self,
        agent: Agent,
        target_repo: Path,
        session_token: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Stage a deployment for approval
        
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
                "status": "staged" if coverage_ok else "failed_coverage"
            }
            
            self.pending_deployments[deployment_id] = deployment_info
            
            return True, deployment_id, deployment_info
            
        except Exception as e:
            logger.error(f"Staging failed: {e}")
            return False, "", {"error": str(e)}
    
    def execute_deployment(
        self,
        deployment_id: str,
        session_token: str
    ) -> Tuple[bool, str]:
        """
        Execute a staged deployment
        
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
                Path(deployment["target_path"])
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
            return False, f"Deployment error: {str(e)}"
    
    def rollback_deployment(
        self,
        deployment_id: str,
        session_token: str
    ) -> Tuple[bool, str]:
        """
        Rollback a deployment
        
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
            return False, f"Rollback error: {str(e)}"
    
    def _save_deployment_history(self, deployment: Dict[str, Any]):
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
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save deployment history: {e}")
    
    def _load_deployment_history(self) -> List[Dict[str, Any]]:
        """Load deployment history"""
        if not self.history_file.exists():
            return []
        
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load deployment history: {e}")
            return []
    
    def get_deployment_status(self) -> Dict[str, Any]:
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
            "recent_deployments": history[-10:] if history else []
        }