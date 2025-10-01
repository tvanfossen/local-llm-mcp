# OPUS_REPORT.md - Targeted Fixes for Agent Code Generation Issues

## Executive Summary
The local model is generating mixed Python/JSON content because it's confused about the output format. The model outputs Python class definitions alongside tool calls, causing the parser to filter out most content. Only 2 of ~12 expected tool calls succeed.

## Root Cause Analysis

### Issue 1: Model Output Confusion
**Problem**: Model generates `class Calculator:` and `{'type': 'def', ...}` instead of proper tool calls
**Cause**: The prompt doesn't emphasize JSON-ONLY output strongly enough
**Evidence**: Parser warnings show Python code mixed with tool calls

### Issue 2: Wrong Tool Call Structure  
**Problem**: Model uses `{'type': 'def', 'name': 'add', ...}` instead of `{'tool_name': 'file_metadata', ...}`
**Cause**: Model confuses metadata content structure with tool call structure
**Evidence**: Parser rejects valid-looking JSON because it lacks `tool_name` field

### Issue 3: Incomplete Workflow
**Problem**: Only 2 tool calls extracted from 1219 chars of output
**Cause**: Most output is filtered as invalid, but agent still reports success
**Evidence**: Agent says "✅ All tool calls queued" with only 2 calls

## Targeted Fixes

### Fix 1: Strengthen JSON-Only Instructions in tool_calling_json.json
**File**: `prompts/system/tool_calling_json.json`
**Change**: Add explicit warnings against Python code generation

```json
{
  "prompt_type": "system",
  "category": "tool_calling", 
  "format": "json",
  "description": "JSON tool calling format prompt with strict output requirements",
  "template": [
    "CRITICAL: Output ONLY JSON tool calls. Do NOT output Python code, class definitions, or any other format.",
    "Every response must be pure JSON tool calls with this exact structure:",
    "```json",
    "[",
    "  {\"tool_name\": \"file_metadata\", \"parameters\": {\"action\": \"create_file\", \"path\": \"example.py\"}},",
    "  {\"tool_name\": \"file_metadata\", \"parameters\": {\"action\": \"add_import\", \"path\": \"example.py\", \"module\": \"typing\"}},",
    "  {\"tool_name\": \"file_metadata\", \"parameters\": {\"action\": \"add_class\", \"path\": \"example.py\", \"name\": \"MyClass\", \"methods\": []}}",
    "]",
    "```",
    "NEVER output: class definitions, def statements, Python code, or mixed content.",
    "Tool calls build metadata that generates code - you don't write code directly."
  ],
  "placeholders": [
    {
      "name": "tool_definitions",
      "description": "Dynamic tool definitions to be inserted"
    }
  ],
  "instructions": [
    "Output JSON tool calls ONLY - no other text or code",
    "Every tool call must have 'tool_name' and 'parameters' fields",
    "For file_metadata add_function: parameters go in the parameters array, not as tool call fields",
    "Build incrementally: create_file → add_imports → add_class → add_function (multiple times) → generate_from_metadata",
    "Complete workflow with workspace.generate_from_metadata as final step"
  ]
}
```

### Fix 2: Add Structure Clarification in formatter.py
**File**: `src/core/mcp/bridge/formatter.py`
**Change**: Add clearer examples in the prompt generation

```python
def get_tools_prompt(self) -> str:
    """Generate tool definitions prompt optimized for Qwen2.5"""
    self.logger.debug(f"ENTRY get_tools_prompt: {len(self.tools)} tools")
    
    if not self.tools:
        return ""
    
    tool_definitions = []
    for tool in self.tools:
        definition = self._format_single_tool(tool)
        if definition:
            tool_definitions.append(definition)
    
    # Add structure clarification before using prompt manager
    structure_clarification = """
IMPORTANT: Tool calls have this structure:
{"tool_name": "file_metadata", "parameters": {"action": "...", "path": "...", ...}}

NOT this structure:
{"type": "def", "name": "add", "parameters": [...]}  # WRONG - this is metadata content

The 'parameters' field contains the arguments TO the tool, not the function parameters."""
    
    # Use JSON-only prompt format with clarification
    prompt_format = 'tool_calling_json'
    base_prompt = self.prompt_manager.format_prompt(
        'system', prompt_format,
        tool_definitions=chr(10).join(tool_definitions)
    )
    
    # Prepend clarification
    prompt = structure_clarification + "\n\n" + base_prompt
    
    self.logger.debug(f"EXIT get_tools_prompt: {len(prompt)} characters")
    return prompt
```

### Fix 3: Add Validation for Minimum Tool Calls
**File**: `src/core/agents/agent/agent.py`  
**Change**: Check for minimum expected tool calls in code generation

```python
# After line 381 (after tool_calls extraction)
if result.get("type") == "tool_calls":
    tool_calls = result.get("tool_calls", [])
    
    # CRITICAL: Validate minimum tool calls for code generation
    MIN_EXPECTED_CALLS = 6  # create_file, add_import, add_class, 2x add_function, generate_from_metadata
    if len(tool_calls) < MIN_EXPECTED_CALLS:
        self.logger.warning(f"⚠️ Only {len(tool_calls)} tool calls generated, expected at least {MIN_EXPECTED_CALLS}")
        
        # Check if it's trying to use wrong structure
        if "class " in str(result.get("content", "")):
            error = "Model generated Python code instead of tool calls - prompt confusion detected"
            self.logger.error(f"❌ {error}")
            return AgentResponse(
                success=False,
                content=f"❌ {error}. Model must output JSON tool calls only.",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        
        # Warn but continue - might be a simple task
        self.logger.warning("Proceeding with fewer tool calls than expected")
```

### Fix 4: Enhanced Parser Error Detection
**File**: `src/core/mcp/bridge/unified_parser.py`
**Change**: Add specific detection for common model confusion patterns

```python
def _extract_json_fences(self, text: str) -> tuple[List[Dict[str, Any]], List[str]]:
    """Extract JSON tool calls from code fences with enhanced error detection"""
    calls = []
    errors = []
    
    # Detect Python code contamination early
    if "class " in text or "\ndef " in text or "import " in text.split('\n')[0]:
        errors.append("Python code detected in output - model should output JSON tool calls only")
    
    # Existing fence extraction...
    for match in self.FENCE_RE.finditer(text):
        json_content = match.group(1).strip()
        
        # Check for metadata structure confused as tool call
        if '"type": "def"' in json_content or '"type": "return"' in json_content:
            errors.append("Model using metadata structure instead of tool call structure")
            continue
            
        parsed_call = self._parse_json_safely(json_content)
        # ... rest of existing logic
```

### Fix 5: Add Workflow Completion Helper
**File**: `src/core/agents/agent/agent.py`
**Change**: Auto-append generate_from_metadata if missing

```python
# After successful tool call validation (around line 420)
# Check if workflow is complete
has_generate_call = any(
    call.get('tool_name') == 'workspace' and 
    call.get('parameters', {}).get('action') == 'generate_from_metadata'
    for call in tool_calls
)

if not has_generate_call and any(
    call.get('tool_name') == 'file_metadata'
    for call in tool_calls
):
    # Auto-add completion call
    self.logger.info("📝 Auto-adding workspace.generate_from_metadata for workflow completion")
    tool_calls.append({
        "tool_name": "workspace",
        "parameters": {
            "action": "generate_from_metadata", 
            "path": filename
        }
    })
```

## Testing After Implementation

### Test Command
```bash
# Create calculator test
curl -X POST http://localhost:8000/api/agent/task -H "Content-Type: application/json" -d '{
  "agent_id": "test_agent",
  "task_type": "code_generation", 
  "message": "Create a Calculator class with add and multiply methods"
}'
```

### Success Criteria
1. **No parser warnings** about mixed content or invalid structures
2. **8-12 tool calls** for complete class generation
3. **Tool call sequence**: create_file → add_import → add_class → add_function(s) → generate_from_metadata
4. **Generated file** has 15+ lines with implemented methods
5. **Logs show**: "Found N tool calls" where N >= 6

## Implementation Order
1. **First**: Fix `tool_calling_json.json` (immediate impact on model behavior)
2. **Second**: Update `formatter.py` (clarifies structure for model)  
3. **Third**: Add validation in `agent.py` (catches incomplete generation)
4. **Fourth**: Enhance parser error detection (better diagnostics)
5. **Fifth**: Add workflow completion helper (ensures full execution)

## Files to Update
1. `/home/tvanfossen/Projects/local-llm-mcp/prompts/system/tool_calling_json.json`
2. `/home/tvanfossen/Projects/local-llm-mcp/src/core/mcp/bridge/formatter.py` 
3. `/home/tvanfossen/Projects/local-llm-mcp/src/core/agents/agent/agent.py`
4. `/home/tvanfossen/Projects/local-llm-mcp/src/core/mcp/bridge/unified_parser.py`

## Expected Impact
- **Immediate**: Model outputs pure JSON tool calls (no Python contamination)
- **Short-term**: 90%+ success rate for code generation tasks
- **Long-term**: Stable incremental file building with full method implementations