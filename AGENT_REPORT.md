# Local LLM Agent Tool Call Generation Issues - Technical Report

## Executive Summary
Local model agents are generating incomplete workflows due to JSON output corruption and invalid tool call structures. While schema consolidation fixes eliminated "add_method" errors, the model now generates mixed content (tool calls + Python code) that gets filtered by the parser, resulting in incomplete implementations.

## Evidence: Working vs Broken Examples

### ✅ Expected Output (CalculatorClaude - 22 lines)
```python
from typing import Union

class Calculator:
    """A calculator class for performing basic arithmetic operations"""

    def add(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Add two numbers and return the result"""
        return a + b
    # ... 3 more complete methods
```

### ❌ Actual Output (CalculatorLocalModel - 4 lines)
```python
import typing

class Calculator:


```

---

## Log Analysis with Problem Identification

### Server Initialization - Schema Loading Success
```
2025-09-29 11:30:37,588 - src.mcp.tools.executor.executor - INFO - Building tool registry with dynamic schema loading...
2025-09-29 11:30:37,589 - src.mcp.tools.executor.schema_loader - INFO - Loaded 6 tool schemas dynamically
2025-09-29 11:30:37,589 - src.mcp.tools.executor.executor - INFO - ✅ Built tool registry with 7 tools (6 dynamic schemas)
```
**✅ GOOD**: Dynamic schema loading is working correctly. The DRY violation fixes are successful.

### Agent Task Initiation
```
2025-09-29 11:30:59,485 - agent.c7d55760 - INFO - Processing code_generation request: Create a complete Calculator class with add and multiply methods. Use proper array format for parameters like [{"name": "a", "type": "float"}, {"name": "b", "type": "float"}] and operations like [{"type": "return", "value": "a + b"}]. Use add_function action, not add_method.
2025-09-29 11:30:59,486 - src.core.llm.manager.manager - INFO - 🔧 TOOLS AVAILABLE: Enhanced prompt with 420 character tool definitions
```
**✅ GOOD**: Clear task specification with explicit format requirements sent to model.

---

## 🚨 CRITICAL ISSUE 1: JSON Output Corruption

### Model Output Analysis
```
2025-09-29 11:31:24,335 - src.core.llm.manager.manager - INFO - 🔍 Processing model output: 1219 characters
2025-09-29 11:31:24,336 - src.core.mcp.bridge.unified_parser.UnifiedToolCallParser - INFO - 🔍 JSON PARSER: Processing 1219 chars
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - INFO - Parsing strategy: json
```

### Parser Warnings - The Real Problem
```
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - WARNING - Parser warning: Failed to parse JSON fence block: invalid JSON syntax
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - WARNING - Parser warning: Invalid tool call in array: {'name': 'self', 'type': 'None'}
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - WARNING - Parser warning: Invalid tool call in array: {'type': 'return', 'value': 'self.add(a, b)'}
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - WARNING - Parser warning: Invalid tool call in array: {'name': 'a', 'type': 'float'}
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - WARNING - Parser warning: Invalid tool call in array: {'name': 'b', 'type': 'float'}
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - WARNING - Parser warning: Invalid tool call in array: class Calculator:
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - WARNING - Parser warning: Invalid tool call in array: {'type': 'def', 'name': 'add', 'parameters': [{'name': 'self', 'type': 'Calculator'}, {'name': 'a', 'type': 'float'}, {'name': 'b', 'type': 'float'}], 'operations': [{'type': 'return', 'value': 'a + b'}], 'docstring': 'Add two numbers.', 'type_annotations': []}
```

**🚨 PROBLEM ANALYSIS**:
- Model is generating **mixed content**: Valid tool calls AND raw Python class definitions
- Model thinks it should output `class Calculator:` directly instead of tool calls
- Model using wrong tool call structure: `{'type': 'def', 'name': 'add', ...}` instead of `{'tool_name': 'file_metadata', 'parameters': {...}}`

**📍 LIKELY SOURCE**: `src/core/prompts/manager.py` or `src/core/mcp/bridge/formatter.py` - system prompt contamination

---

## 🚨 CRITICAL ISSUE 2: Incomplete Workflow

### Successfully Filtered Output
```
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - INFO - Found 2 tool calls
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - INFO - Processing tool call 1: {'tool_name': 'file_metadata', 'parameters': {'action': 'create_file', 'path': 'test_calculator.py'}}
2025-09-29 11:31:24,336 - src.core.mcp.bridge.bridge.MCPBridge - INFO - Processing tool call 2: {'tool_name': 'file_metadata', 'parameters': {'action': 'add_import', 'path': 'test_calculator.py', 'module': 'typing'}}
```

**🚨 PROBLEM**: Only 2 valid tool calls extracted from 1219 characters of model output. Expected: 8-12 tool calls for complete class.

### Missing Critical Steps
```
2025-09-29 11:31:24,337 - agent.c7d55760 - INFO - ✅ All tool calls queued and validated - tools will execute asynchronously
```

**🚨 MISSING**:
- No `add_class` call for Calculator class
- No `add_function` calls for methods
- No `workspace.generate_from_metadata` call for completion

**📍 LIKELY SOURCE**: Agent workflow in `src/core/agents/agent/agent.py` doesn't detect incomplete generation

---

## File-Specific Problem Areas

### 1. JSON-Only System Prompt Issue
**File**: `src/core/mcp/bridge/formatter.py:17-38`
**Problem**: Tool prompt may be confusing model about output format
```python
def get_tools_prompt(self) -> str:
    # Use JSON-only prompt format
    prompt_format = 'tool_calling_json'
    prompt = self.prompt_manager.format_prompt(
        'system', prompt_format,
        tool_definitions=chr(10).join(tool_definitions)
    )
```

### 2. Parser Validation Logic
**File**: `src/core/mcp/bridge/unified_parser.py`
**Problem**: Parser correctly filters invalid content but doesn't provide feedback to model
**Evidence**: Model generates 1219 chars, only 2 valid tool calls extracted

### 3. Agent Workflow Completion
**File**: `src/core/agents/agent/agent.py`
**Problem**: Agent considers task "successful" with only 2 tool calls
```python
agent.c7d55760 - INFO - ✅ All tool calls queued and validated - tools will execute asynchronously
```

### 4. Tool Call Structure Template
**File**: `prompts/system/tool_calling_json.json`
**Problem**: Model may be seeing conflicting examples of tool call format

---

## Metadata Analysis

### Current State - Incomplete
```json
{
  "classes": [
    {
      "name": "Calculator",
      "methods": []  // ← EMPTY: No methods implemented
    }
  ]
}
```

### Expected State
```json
{
  "classes": [
    {
      "name": "Calculator",
      "methods": [
        {"name": "add", "parameters": [...], "operations": [...]},
        {"name": "multiply", "parameters": [...], "operations": [...]}
      ]
    }
  ]
}
```

---

## Recommended Fix Targets

### Priority 1: JSON Output Purity
- **Target**: `src/core/mcp/bridge/formatter.py` - Strengthen JSON-only instruction
- **Target**: `prompts/system/tool_calling_json.json` - Clean up conflicting examples

### Priority 2: Tool Call Structure Validation
- **Target**: `src/core/mcp/bridge/unified_parser.py` - Add feedback for malformed structures
- **Target**: Enhanced validation for `{'type': 'def', ...}` vs `{'tool_name': 'file_metadata', ...}`

### Priority 3: Workflow Completion Detection
- **Target**: `src/core/agents/agent/agent.py` - Add completion validation
- **Target**: Auto-queue `workspace.generate_from_metadata` when metadata building complete

---

## Success Metrics for Validation
1. **Model Output Purity**: Zero parser warnings for mixed content
2. **Tool Call Count**: 8-12 calls for typical class generation
3. **Workflow Completion**: 100% automatic completion with workspace.generate_from_metadata
4. **Code Generation**: Files with 15+ lines of functional methods

## Context Files for Analysis
- `/home/tvanfossen/Projects/local-llm-mcp/src/core/mcp/bridge/formatter.py`
- `/home/tvanfossen/Projects/local-llm-mcp/src/core/mcp/bridge/unified_parser.py`
- `/home/tvanfossen/Projects/local-llm-mcp/prompts/system/tool_calling_json.json`
- `/home/tvanfossen/Projects/local-llm-mcp/src/core/agents/agent/agent.py`
- `/home/tvanfossen/Projects/local-llm-mcp/examples/CalculatorClaude/calculator.py` (reference)
- `/home/tvanfossen/Projects/local-llm-mcp/examples/CalculatorLocalModel/calculator.py` (broken)