# Agent Workplan: Refactor File Metadata Tool for Incremental Operations

## Overview
Refactor the `file_metadata` tool to support incremental file building operations, allowing local models with limited context windows to build files piece by piece. Merge the `interface_registry` tool functionality into the metadata tool to track dependencies and exports automatically.

## Current State
- **file_metadata tool**: Currently writes complete metadata files in one operation
- **interface_registry tool**: Separate tool for tracking module dependencies and exports
- **Problem**: Local models can't generate complete files in one inference due to context limitations

## Target State
- Single `file_metadata` tool with incremental operations
- Automatic dependency and export tracking integrated
- Support for piece-by-piece file construction
- Low cognitive complexity (<7) with focused single-responsibility files

## Implementation Plan

### Phase 1: Create New File Structure
Create the following new files with low cognitive complexity:

#### 1.1 Base Infrastructure
```
src/mcp/tools/file_metadata/
├── file_metadata.py          # Main router (keep <100 lines)
├── operations/
│   ├── __init__.py
│   ├── base.py               # Base class with common functionality
│   ├── create_file.py        # Create initial file structure
│   ├── add_import.py         # Add import statements
│   ├── add_variable.py       # Add variables/constants
│   ├── add_class.py          # Add class definitions
│   ├── add_function.py       # Add functions/methods
│   ├── add_field.py          # Add dataclass fields
│   ├── complete_file.py      # Mark file as complete
│   ├── read_metadata.py      # Read existing metadata
│   └── list_metadata.py      # List all metadata files
└── registry/
    ├── __init__.py
    └── dependency_tracker.py # Merged interface registry functionality
```

#### 1.2 Key Design Principles
- **Each operation file**: Single responsibility, <100 lines, cognitive complexity <7
- **Maximum 2 returns per function**: Early return for validation, final return for result
- **Router pattern**: Main file only routes to operation handlers
- **Inheritance**: Use base class for common metadata loading/saving

### Phase 2: Implement Core Operations

#### 2.1 Base Operation Class (`operations/base.py`)
```python
class BaseMetadataOperation:
    def __init__(self, workspace_root: str = "/workspace"):
        self.workspace_root = Path(workspace_root)
    
    def _load_or_create_metadata(self, path: str) -> Tuple[Dict, Path]:
        # Load existing or create new metadata structure
        pass
    
    def _save_metadata(self, metadata: Dict, meta_file: Path) -> Dict:
        # Save metadata with validation
        pass
    
    async def execute(self, arguments: Dict) -> Dict:
        # Must be implemented by subclasses
        raise NotImplementedError
```

#### 2.2 Operation Flow Example
```python
# User calls file_metadata tool multiple times:
1. {"action": "create_file", "path": "src/calculator.py", "description": "Calculator module"}
2. {"action": "add_import", "path": "src/calculator.py", "module": "typing", "items": ["List", "Dict"]}
3. {"action": "add_class", "path": "src/calculator.py", "name": "Calculator"}
4. {"action": "add_function", "path": "src/calculator.py", "name": "add", "class_name": "Calculator", ...}
5. {"action": "complete_file", "path": "src/calculator.py"}
```

### Phase 3: Merge Interface Registry

#### 3.1 Integrate Dependency Tracking
- Move `interface_registry` logic into `registry/dependency_tracker.py`
- Automatically update when adding imports (track dependencies)
- Automatically update when adding classes/functions (track exports)
- Store in `.meta/registry.yaml` instead of separate file

#### 3.2 Delete Old Interface Registry
```bash
# Files to delete:
src/mcp/tools/interface_registry/
prompts/tools/interface_registry.json
```

#### 3.3 Update Executor
Remove interface_registry from `src/mcp/tools/executor/executor.py`

### Phase 4: Update Tool Definitions

#### 4.1 Update `prompts/tools/file_metadata.json`
```json
{
  "tool_name": "file_metadata",
  "description": "Incrementally build JSON metadata files for structured code generation",
  "parameters": [
    {
      "name": "action",
      "allowed_values": [
        "create_file",
        "add_import",
        "add_variable", 
        "add_class",
        "add_function",
        "add_field",
        "complete_file",
        "read",
        "list"
      ]
    }
  ]
}
```

### Phase 5: Update Templates

#### 5.1 Ensure Jinja2 Template Compatibility
- Verify `templates/python_file.j2` works with incremental metadata
- Test with partially populated metadata structures
- Ensure graceful handling of empty sections

### Phase 6: Testing Strategy

#### 6.1 Create Test File
```python
# test/test_incremental_metadata.py
def test_incremental_file_building():
    # Test building a file piece by piece
    # Verify each operation updates metadata correctly
    # Ensure final generation matches expected output
```

#### 6.2 Validation Points
- Each operation saves valid JSON
- Registry tracking works automatically
- Complete files generate valid Python
- Cognitive complexity stays below 7

## File Modifications Checklist

### Files to Create:
- [ ] `src/mcp/tools/file_metadata/operations/__init__.py`
- [ ] `src/mcp/tools/file_metadata/operations/base.py`
- [ ] `src/mcp/tools/file_metadata/operations/create_file.py`
- [ ] `src/mcp/tools/file_metadata/operations/add_import.py`
- [ ] `src/mcp/tools/file_metadata/operations/add_variable.py`
- [ ] `src/mcp/tools/file_metadata/operations/add_class.py`
- [ ] `src/mcp/tools/file_metadata/operations/add_function.py`
- [ ] `src/mcp/tools/file_metadata/operations/add_field.py`
- [ ] `src/mcp/tools/file_metadata/operations/complete_file.py`
- [ ] `src/mcp/tools/file_metadata/operations/read_metadata.py`
- [ ] `src/mcp/tools/file_metadata/operations/list_metadata.py`
- [ ] `src/mcp/tools/file_metadata/registry/__init__.py`
- [ ] `src/mcp/tools/file_metadata/registry/dependency_tracker.py`

### Files to Modify:
- [ ] `src/mcp/tools/file_metadata/file_metadata.py` - Refactor to router pattern
- [ ] `prompts/tools/file_metadata.json` - Update with new operations
- [ ] `src/mcp/tools/executor/executor.py` - Remove interface_registry references

### Files to Delete:
- [ ] `src/mcp/tools/interface_registry/` (entire directory)
- [ ] `prompts/tools/interface_registry.json`

## Success Criteria
1. **Incremental Building**: Can build a complete file through multiple small operations
2. **Low Complexity**: No function exceeds cognitive complexity of 7
3. **Clean Returns**: Maximum 3 returns per function (validation, success, error)
4. **Automatic Tracking**: Dependencies and exports tracked without explicit registry calls
5. **Backward Compatible**: Existing `workspace generate_from_metadata` still works

## Implementation Order
1. Create base operation class and router
2. Implement create_file and add_import operations
3. Implement add_class and add_function operations
4. Implement remaining operations
5. Integrate dependency tracking
6. Delete old interface registry
7. Update tool definitions
8. Test end-to-end workflow

## Example Usage After Implementation
```python
# Agent with limited context can build files incrementally:
await file_metadata_tool({"action": "create_file", "path": "game.py"})
await file_metadata_tool({"action": "add_import", "path": "game.py", "module": "pygame"})
await file_metadata_tool({"action": "add_class", "path": "game.py", "name": "Game"})
await file_metadata_tool({"action": "add_function", "path": "game.py", "name": "__init__", "class_name": "Game"})
# ... continue adding pieces ...
await file_metadata_tool({"action": "complete_file", "path": "game.py"})

# Then generate the actual Python file:
await workspace_tool({"action": "generate_from_metadata", "path": "game.py"})
```

## Notes for Claude Code
- Keep each operation focused and simple
- Use early returns for validation failures
- Log each operation clearly for debugging
- Ensure metadata structure is always valid JSON
- Test with partial metadata to ensure robustness
- Consider memory usage with large metadata files
- Maintain compatibility with existing jinja2 templates