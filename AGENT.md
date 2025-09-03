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

### Phase 1: Docker & Volume Management (tasks.py)
**File:** `tasks.py`
**Focus:** Update Docker volume mounting strategy

**Current:**
```python
inv run --project_path=relative/path
```

**Target:**
```python
inv run --repo=/absolute/path/to/target/repo
# Mounts: /absolute/path/to/target/repo:/workspace
# Creates: /workspace/.mcp-agents/ for agent metadata
```

**Changes Required:**
- Update `run()` task to accept `--repo` parameter
- Change volume mount from `/host/repo` to `/workspace`
- Ensure `.mcp-agents/` directory creation
- Update backup/restore to handle new structure

### Phase 2: Agent Workspace Restructuring (core/agent.py)
**File:** `core/agent.py`
**Focus:** Modify agent file management to work with repo-relative paths

**Current Structure:**
```
workspaces/{agent_id}/files/{managed_file}
```

**Target Structure:**
```
/workspace/{managed_file}  (actual file)
/workspace/.mcp-agents/{agent_id}/  (agent metadata)
```

**Changes Required:**
- Update `get_managed_file_path()` to return `/workspace/{managed_file}`
- Modify `read_managed_file()` and `write_managed_file()` for direct access
- Update context and history storage to `.mcp-agents/{agent_id}/`
- Handle file creation/backup workflows

### Phase 3: Path Resolution Updates (core/agent_registry.py)
**File:** `core/agent_registry.py`
**Focus:** Update agent creation and file conflict detection

**Changes Required:**
- File conflict detection based on repo-relative paths
- Agent workspace creation in `.mcp-agents/{agent_id}/`
- Registry persistence in `.mcp-agents/registry.json`
- File ownership tracking with repo-relative paths

### Phase 4: Configuration Management (core/config.py)
**File:** `core/config.py`
**Focus:** Add repository path configuration

**Changes Required:**
- Add `repo_path` to SystemConfig
- Update directory initialization for new structure
- Ensure `.mcp-agents/` is in .gitignore
- Handle container vs host path resolution

### Phase 5: Deployment Simplification (core/deployment.py, api/orchestrator.py)
**Files:** `core/deployment.py`, `api/orchestrator.py`
**Focus:** Simplify deployment since files are already in place

**Changes Required:**
- Deployment becomes a git commit/push operation
- Remove complex file copying logic
- Focus on validation and testing workflows
- Update diff generation for git-based changes

### Phase 6: HTML Interface Updates (static/orchestrator.html)
**File:** `static/orchestrator.html`
**Focus:** Update UI to reflect new workflow

**Changes Required:**
- Remove manual path specification
- Show git status integration
- Update deployment UI to focus on commit/push
- Add real-time file change detection

## Implementation Order

### Sprint 1: Core Infrastructure
1. **tasks.py** - Docker volume mounting
2. **core/config.py** - Repository path configuration
3. **Test basic volume mounting and path resolution**

### Sprint 2: Agent File Management
1. **core/agent.py** - Direct file access
2. **core/agent_registry.py** - New workspace structure
3. **Test agent creation and file operations**

### Sprint 3: Deployment & Interface
1. **core/deployment.py** - Simplified deployment
2. **static/orchestrator.html** - UI updates
3. **Integration testing**

## File Change Summary

| File | Priority | Changes | Complexity | Status |
|------|----------|---------|------------|--------|
| `tasks.py` | HIGH | Volume mounting, repo parameter | LOW | ✅ COMPLETED |
| `core/config.py` | HIGH | Repository configuration | LOW | 🔄 NEXT |
| `core/agent.py` | HIGH | Direct file access | MEDIUM | ⏳ PENDING |
| `core/agent_registry.py` | MEDIUM | Workspace structure | MEDIUM | ⏳ PENDING |
| `core/deployment.py` | LOW | Simplified deployment | HIGH | ⏳ PENDING |
| `api/orchestrator.py` | LOW | Deployment API updates | MEDIUM | ⏳ PENDING |
| `static/orchestrator.html` | LOW | UI workflow updates | MEDIUM | ⏳ PENDING |

## Testing Strategy

### Unit Tests (Per Sprint)
- File path resolution
- Agent workspace creation
- Direct file read/write operations
- Registry persistence

### Integration Tests (Final)
- End-to-end agent creation → file editing → git status
- Docker container with real repository
- HTML interface with real workflows

## Migration Strategy

### Backward Compatibility
1. Support both old and new workspace structures during transition
2. Migration script for existing agent workspaces
3. Gradual rollout with feature flags

### Data Preservation
1. Agent conversation history
2. Agent configurations
3. File ownership mappings

## Risk Mitigation

### High Risk Areas
1. **File path resolution** - Extensive testing required
2. **Container volume mounting** - Docker expertise needed
3. **File ownership conflicts** - Robust conflict detection

### Rollback Plan
1. Keep current Docker image as fallback
2. Backup all agent state before migration
3. Quick rollback script for volume mounting

## Communication Protocol

When working on a specific component, provide:
1. **Component focus**: Which file(s) and phase
2. **Dependencies**: What other components are affected
3. **Testing approach**: How to validate changes
4. **Integration points**: How this connects to other phases

Example:
```
COMPONENT: Phase 1 - tasks.py Docker volume mounting
DEPENDENCIES: Requires core/config.py updates for repo_path
TESTING: Docker run with real repository, verify file access
INTEGRATION: Must work with Phase 2 agent file operations
```

## Success Criteria

### Phase 1 Complete
- [ ] `inv run --repo=/path/to/repo` works
- [ ] Container can access host files
- [ ] `.mcp-agents/` directory created

### Phase 2 Complete
- [ ] Agents can read/write files directly
- [ ] Agent metadata stored in `.mcp-agents/`
- [ ] File conflict detection works

### Final Success
- [ ] Agent creates/edits files in target repository
- [ ] Changes visible in git status immediately
- [ ] Deployment is simplified git workflow
- [ ] No manual path specification required
- [ ] Backward compatibility maintained

---

**Next Step:** Choose Phase 1 component (tasks.py) and implement Docker volume mounting with repository parameter.
