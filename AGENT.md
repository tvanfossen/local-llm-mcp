# AGENT.md - File Writing Architecture Redesign

## Problem Statement

The current file writing system has a disconnect between agent workspaces (containerized) and deployment targets (host repository). This creates complexity in path management and deployment workflows.

## Current Architecture Issues

```
Current Flow:
Container: /app/workspaces/{agent_id}/files/{filename}
    ↓ (deployment step)
Host: /arbitrary/target/path/{filename}
```

**Problems:**
- Complex path resolution
- Disconnect between development and deployment
- Manual path specification required
- No direct file editing capability
- Deployment requires explicit target specification

## Proposed Architecture

```
New Flow:
Host Repo: ~/Projects/target-project/
Container Mount: /workspace/ -> ~/Projects/target-project/
Agent Workspace: /workspace/.mcp-agents/{agent_id}/{filename}
Direct File Access: /workspace/{filename} (symlinked or direct)
```

**Benefits:**
- Agents work directly with target files
- Simplified path management
- Real-time file updates
- No deployment step for development
- Direct integration with git workflows

## Implementation Plan

### Phase 1: Docker & Volume Management (tasks.py) ✅ COMPLETED
**File:** `tasks.py`
**Focus:** Update Docker volume mounting strategy

**Status:** ✅ COMPLETED
- Updated `run()` task to accept `--repo` parameter
- Changed volume mount to `/workspace`
- Ensured `.mcp-agents/` directory creation
- Updated backup/restore to handle new structure

### Phase 2: Agent Workspace Restructuring (core/agent.py) ✅ COMPLETED
**File:** `core/agent.py`
**Focus:** Modify agent file management to work with repo-relative paths

**Status:** ✅ COMPLETED
- Updated `get_managed_file_path()` to return `/workspace/{managed_file}`
- Modified `read_managed_file()` and `write_managed_file()` for direct access
- Updated context and history storage to `.mcp-agents/{agent_id}/`
- Implemented file creation/backup workflows

### Phase 3: Path Resolution Updates (core/agent_registry.py) ✅ COMPLETED
**File:** `core/agent_registry.py`
**Focus:** Update agent creation and file conflict detection

**Status:** ✅ COMPLETED
- File conflict detection based on repo-relative paths
- Agent workspace creation in `.mcp-agents/{agent_id}/`
- Registry persistence in `.mcp-agents/registry.json`
- File ownership tracking with repo-relative paths

### Phase 4: Configuration Management (core/config.py) ✅ COMPLETED
**File:** `core/config.py`
**Focus:** Add repository path configuration

**Status:** ✅ COMPLETED
- Added `repo_path` to SystemConfig
- Updated directory initialization for new structure
- Ensured `.mcp-agents/` is in .gitignore
- Implemented container vs host path resolution

### Phase 5: Deployment Simplification (core/deployment.py) ✅ COMPLETED
**File:** `core/deployment.py`
**Focus:** Simplify deployment since files are already in place

**Status:** ✅ COMPLETED
**Changes Implemented:**
- Replaced file-based deployment with git-based operations (add/commit/push)
- Implemented git diff generation instead of file copying
- Updated test coverage validation for direct file access in repository
- Git-based rollback using git checkout/revert instead of file backups
- Repository-context test execution and code quality validation
- Maintained security features and audit logging for git operations
- Simplified deployment workflow: validate tests → git add → commit → push
- **Fixed pre-commit violations:**
  - Reduced cognitive complexity in coverage validation functions
  - Consolidated return statements in validation functions
  - Maintained all functionality while meeting code quality requirements

### Phase 6: Deployment API Updates (api/orchestrator.py) ⏳ PENDING - CURRENT FOCUS
**File:** `api/orchestrator.py`
**Focus:** Update deployment API for simplified git workflow

**Changes Required:**
- Update deployment endpoints to use new GitDeploymentManager
- Replace file-copying deployment logic with git operations
- Simplify staging API since files are already in repository
- Update WebSocket messaging for git-based status updates
- Remove complex file path mapping since files are in place

### Phase 7: HTML Interface Updates (static/orchestrator.html) ⏳ PENDING
**File:** `static/orchestrator.html`
**Focus:** Update UI to reflect new git-based workflow

**Changes Required:**
- Update deployment UI to show git status and diffs
- Remove manual path specification UI (no longer needed)
- Add git commit message input fields
- Show real-time git status updates via WebSocket
- Display git-based deployment history and rollback options

## Updated File Change Summary

| File | Priority | Changes | Complexity | Status |
|------|----------|---------|------------|--------|
| `tasks.py` | HIGH | Volume mounting, repo parameter | LOW | ✅ COMPLETED |
| `core/config.py` | HIGH | Repository configuration | LOW | ✅ COMPLETED |
| `core/agent.py` | HIGH | Direct file access | MEDIUM | ✅ COMPLETED |
| `core/agent_registry.py` | MEDIUM | Workspace structure | MEDIUM | ✅ COMPLETED |
| `core/deployment.py` | HIGH | Git-based deployment | HIGH | ✅ COMPLETED |
| `api/orchestrator.py` | HIGH | API updates for git workflow | MEDIUM | ⏳ PENDING |
| `static/orchestrator.html` | MEDIUM | UI updates for git workflow | MEDIUM | ⏳ PENDING |

## Current Focus: Phase 6 - Deployment API Updates

**Objective:** Update the orchestrator API to use the new git-based deployment workflow instead of file-copying operations.

**Key Changes Needed in api/orchestrator.py:**
1. **Git Integration**: Use git commands for diff generation and status checking
2. **Simplified Validation**: Test coverage validation adapted for direct file access
3. **Remove File Copying**: Eliminate complex file staging since files are already in place
4. **Git-based Deployment**: Deploy = git add + commit + push workflow
5. **Rollback via Git**: Use git revert instead of file backup/restore

**Implementation Strategy:**
- Update deployment endpoints to use new GitDeploymentManager methods
- Maintain test coverage validation (100% requirement)
- Replace file diff generation with git diff from DeploymentManager
- Simplify deployment to git operations
- Update rollback to use git history
- Preserve security and audit logging

## Success Criteria

### Current Phase (5) Complete
- [x] Deployment uses git diff instead of file copying
- [x] Test validation works with direct file access
- [x] Deploy operation is git add/commit/push
- [x] Rollback uses git revert
- [x] All existing security features preserved
- [ ] **All pre-commit code quality checks pass**

### Final Success (All Phases)
- [x] Agent creates/edits files in target repository
- [x] Changes visible in git status immediately
- [x] Deployment uses simplified git workflow
- [x] No manual path specification required
- [x] Backward compatibility maintained

## Testing Strategy

### Current Phase Testing
- Test coverage validation with direct file access via DeploymentManager
- Git diff generation and status checking using DeploymentManager methods
- Git-based deployment workflow (add/commit/push) through API endpoints
- Git rollback functionality using DeploymentManager
- Security feature preservation with git operations

### Integration Testing
- End-to-end agent creation → file editing → git deployment
- Docker container with real repository and git operations
- HTML interface with git-based deployment workflow
- Complete test coverage validation in repository context

---

**Current Task:** Implement Phase 6 - Update `api/orchestrator.py` to use the new git-based DeploymentManager instead of file-copying operations, while maintaining test coverage requirements and security features.

**Previous Completion:** Phase 5 completed with git-based deployment implementation in `core/deployment.py`, including fixes for pre-commit cognitive complexity and return count violations.
