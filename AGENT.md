# AGENT.md - File Writing Architecture Redesign

## Problem Statement

The current file writing system has a disconnect between agent workspaces (containerized) and deployment targets (host repository). This creates complexity in path management and deployment workflows.

## Current Architecture Issues

```
Old Flow:
Container: /app/workspaces/{agent_id}/files/{filename}
    ↓ (deployment step)
Host: /arbitrary/target/path/{filename}
```

**Problems Solved:**
- ✅ Complex path resolution eliminated
- ✅ Disconnect between development and deployment resolved
- ✅ Direct file editing capability implemented
- ✅ Git-based deployment workflow established

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

### Phase 6: Deployment API Updates (api/orchestrator.py) ✅ COMPLETED
**File:** `api/orchestrator.py`
**Focus:** Update deployment API for simplified git workflow

**Status:** ✅ COMPLETED
**Changes Implemented:**
- Updated deployment endpoints to use DeploymentManager git operations
- Replaced file-copying deployment logic with git add/commit/push workflow
- Simplified staging API since files are directly in repository workspace
- Updated WebSocket messaging for git-based status updates (git_test_update, git_deployment_complete, git_rollback_complete)
- Removed complex file path mapping (_process_target_path_mapping) since files are in place
- Enhanced git context in all responses and WebSocket broadcasts
- Streamlined validation logic for repository-direct approach
- Maintained all security features and audit logging with git operations

### Phase 7: HTML Interface Updates (static/orchestrator.html) ⏳ PENDING - CURRENT FOCUS
**File:** `static/orchestrator.html`
**Focus:** Update UI to reflect new git-based deployment workflow

**Changes Required:**
- Update deployment UI to show git status and diffs instead of file operations
- Remove manual path specification UI (no longer needed for direct repository access)
- Add git commit message input fields for deployment operations
- Show real-time git status updates via WebSocket (git operations instead of file copying)
- Display git-based deployment history and rollback options
- Update WebSocket message handling for new git-based message types
- Enhance deployment queue UI to show git context (staged, committed, pushed)
- Add git diff preview functionality before deployment

## Updated File Change Summary

| File | Priority | Changes | Complexity | Status |
|------|----------|---------|------------|--------|
| `tasks.py` | HIGH | Volume mounting, repo parameter | LOW | ✅ COMPLETED |
| `core/config.py` | HIGH | Repository configuration | LOW | ✅ COMPLETED |
| `core/agent.py` | HIGH | Direct file access | MEDIUM | ✅ COMPLETED |
| `core/agent_registry.py` | MEDIUM | Workspace structure | MEDIUM | ✅ COMPLETED |
| `core/deployment.py` | HIGH | Git-based deployment | HIGH | ✅ COMPLETED |
| `api/orchestrator.py` | HIGH | API updates for git workflow | MEDIUM | ✅ COMPLETED |
| `static/orchestrator.html` | MEDIUM | UI updates for git workflow | MEDIUM | ⏳ PENDING |

## Current Focus: Phase 7 - HTML Interface Updates

**Objective:** Update the orchestrator HTML interface to reflect the new git-based deployment workflow instead of file-copying operations.

**Key Changes Needed in static/orchestrator.html:**
1. **Git Operations UI**: Update deployment interface to show git status, diffs, and commit operations
2. **Remove Path Specification**: Eliminate manual target path input since files are directly in repository
3. **Git Commit Messages**: Add input fields for commit messages during deployment
4. **Real-time Git Updates**: Handle new WebSocket message types (git_test_update, git_deployment_complete, etc.)
5. **Git History Display**: Show git-based deployment history with commit information
6. **Git Diff Preview**: Add functionality to preview git diffs before deployment
7. **Git Status Integration**: Display current git status of repository and staged changes

**Implementation Strategy:**
- Update deployment queue UI to show git context (staged, committed, pushed)
- Replace file-copying status with git operation status
- Add git commit message input to deployment workflow
- Update WebSocket handlers for git-based message types
- Enhance deployment history to show git commits and rollback via git revert
- Remove complex file path inputs since agents work directly in repository

## Success Criteria

### Current Phase (6) Complete
- [x] Deployment uses DeploymentManager git operations instead of file copying
- [x] API endpoints simplified for repository-direct access
- [x] WebSocket messaging updated for git operations
- [x] Complex file path mapping eliminated
- [x] All existing security features preserved
- [x] **All pre-commit code quality checks pass**

### Final Success (All Phases)
- [x] Agent creates/edits files in target repository
- [x] Changes visible in git status immediately
- [x] Deployment uses simplified git workflow
- [x] No manual path specification required
- [x] Backward compatibility maintained

## Testing Strategy

### Current Phase Testing
- HTML interface integration with git-based API endpoints
- WebSocket message handling for git operation updates
- Git-based deployment workflow through UI
- Removal of file path specification requirements
- Git diff preview and commit message functionality

### Integration Testing
- End-to-end agent creation → file editing → git deployment through UI
- Docker container with real repository and git operations
- Complete HTML interface with git-based deployment workflow
- WebSocket real-time updates for git operations

---

**Current Task:** Implement Phase 7 - Update `static/orchestrator.html` to use the new git-based UI workflow instead of file-copying operations, while maintaining test coverage requirements and security features.

**Previous Completion:** Phase 6 completed with git-based orchestrator API integration in `api/orchestrator.py`, including simplified deployment workflow, updated WebSocket messaging for git operations, and removal of complex file path mapping.
