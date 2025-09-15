# Agent System Critical Fix Execution Plan

## Executive Summary
The async task queue is working, but three critical issues prevent the system from being production-ready:
1. **Code Output Formatting** - Generated files have invalid Python syntax due to markdown wrappers
2. **Task Queue UI** - Orchestrator visualization not updating properly
3. **Agent File Overwrite** - Agents completely overwrite files without checking existing content

## Phase 1: Fix Code Output Format (PRIORITY 1)
**Goal**: Ensure all generated code has valid Python syntax without markdown wrappers

### Step 1.1: Update Agent Code Generation Response Format
**File**: `src/core/agents/agent/agent.py`

**Changes Required**:
```python
# In _handle_code_generation method, around line 341-350
# REMOVE any markdown formatting from generated_code
# Ensure the LLM response is cleaned before writing

# Add this cleaning function:
def _clean_generated_code(self, code: str, filename: str) -> str:
    """Remove markdown wrappers and clean generated code"""
    # Remove filename header if present
    if code.startswith(filename):
        code = code[len(filename):].lstrip()

    # Remove markdown code blocks
    if code.startswith('```python'):
        code = code[9:]  # Remove ```python
    elif code.startswith('```'):
        code = code[3:]   # Remove ```

    # Remove trailing markdown
    if code.endswith('```'):
        code = code[:-3]

    return code.strip()
```

### Step 1.2: Implement Structured JSON Response Format
**File**: `src/schemas/agents/agents.py`

**Add New Schema**:
```python
@dataclass
class CodeGenerationResponse:
    """Structured response for code generation"""
    filename: str
    code: str
    language: str
    description: str
    line_count: int

    def to_file_content(self) -> str:
        """Get clean file content without any formatting"""
        return self.code
```

### Step 1.3: Update LLM Prompt for Clean Output
**File**: `src/core/agents/agent/agent.py`

**Update code_gen_prompt** (line ~325):
```python
code_gen_prompt = f"""Context: {context}

Task: Code Generation
Request: {request.message}
Target File: {filename}

CRITICAL INSTRUCTIONS:
1. Generate ONLY valid Python code
2. Do NOT include markdown formatting (no ```)
3. Do NOT include the filename at the start
4. Do NOT include any explanations outside of comments
5. Start directly with imports or docstrings
6. End with the last line of code

Generate the complete Python code:"""
```

## Phase 2: Implement File Content Awareness (PRIORITY 2)
**Goal**: Prevent agents from overwriting existing work

### Step 2.1: Add File Reading Before Writing
**File**: `src/core/agents/agent/agent.py`

**Add method**:
```python
async def _check_existing_file(self, filename: str) -> tuple[bool, str]:
    """Check if file exists and get its content"""
    if not self.tool_executor:
        return False, ""

    try:
        result = await self.tool_executor.execute_tool(
            "workspace",
            {"action": "read", "path": filename}
        )

        if result.get("success"):
            content = result.get("content", [{}])[0].get("text", "")
            return True, content
        return False, ""
    except:
        return False, ""
```

### Step 2.2: Implement Incremental vs Full Rewrite Detection
**Add to** `_handle_code_generation`:
```python
# Check existing file
exists, existing_content = await self._check_existing_file(filename)

if exists and len(existing_content) > 500:  # Substantial existing content
    # Analyze request for intent
    request_lower = request.message.lower()

    # Keywords suggesting incremental change
    incremental_keywords = ['add', 'update', 'modify', 'fix', 'change', 'append', 'insert']
    is_incremental = any(keyword in request_lower for keyword in incremental_keywords)

    if is_incremental:
        # Modify prompt to include existing content
        code_gen_prompt = f"""Existing file content:
{existing_content[:1000]}... (truncated)

Request: {request.message}

Generate ONLY the modified version of the complete file, preserving existing functionality:"""
    else:
        # Ask for confirmation
        return AgentResponse(
            success=False,
            content=f"⚠️ File {filename} exists with {len(existing_content)} characters. "
                   f"Add 'overwrite' to your request to replace it completely, "
                   f"or use 'update'/'modify' for incremental changes.",
            # ... other fields
        )
```

## Phase 3: Fix Task Queue UI (PRIORITY 3)
**Goal**: Make the orchestrator task queue panel functional

### Step 3.1: Fix Task Queue Data Structure
**File**: `src/core/agents/registry/task_queue.py`

**Update** `to_dict` method in `AgentTask`:
```python
def to_dict(self) -> dict[str, Any]:
    """Convert to dictionary for JSON serialization"""
    return {
        "task_id": self.task_id,
        "agent_id": self.agent_id,
        "status": self.status.value,  # Ensure enum is converted
        "created_at": self.created_at,
        "completed_at": self.completed_at,
        "request": self.request,
        "result": self.result,
        "error": self.error,
        # Add display-friendly fields
        "status_display": self.status.value.upper(),
        "elapsed_time": self._calculate_elapsed_time()
    }

def _calculate_elapsed_time(self) -> str:
    """Calculate elapsed time for display"""
    if not self.completed_at:
        return "Running..."
    # Calculate and format elapsed time
    return "Completed"
```

### Step 3.2: Fix JavaScript Task Parsing
**File**: `static/orchestrator.html`

**Update** `parseTasksFromResponse` function (around line 180):
```javascript
function parseTasksFromResponse(text) {
    const tasks = [];
    const lines = text.split('\n');
    let currentTask = null;

    for (const line of lines) {
        // Better parsing pattern
        if (line.includes('🎫')) {
            if (currentTask) tasks.push(currentTask);

            // Parse: "🎫 task_id - status"
            const parts = line.split('🎫')[1].trim().split('-');
            if (parts.length >= 2) {
                currentTask = {
                    id: parts[0].trim(),
                    status: parts[1].trim().toLowerCase()
                };
            }
        } else if (currentTask) {
            if (line.includes('Agent:')) {
                currentTask.agent = line.split('Agent:')[1].trim();
            } else if (line.includes('Created:')) {
                currentTask.created = line.split('Created:')[1].trim();
            }
        }
    }

    if (currentTask) tasks.push(currentTask);

    // Add debug logging
    console.log('Parsed tasks:', tasks);
    return tasks;
}
```

### Step 3.3: Add Real-time WebSocket Updates (Optional Enhancement)
**File**: `src/api/websocket/handler/message_handlers.py`

**Add handler**:
```python
async def _handle_task_queue_subscribe(self, websocket, connection_id: str, data: dict):
    """Subscribe to task queue updates"""
    # Implementation for real-time task updates
    pass
```

## Phase 2.5: Structured JSON File Management (PRIORITY 1)
**Goal**: Implement scalable incremental updates using JSON file representation and Jinja2 templates

### Overview
Replace current file overwrite approach with structured JSON-based system:
- **Agent Response**: JSON with specific function/class updates
- **MCP Server**: Maintains JSON representation of file structure
- **Template Engine**: Jinja2 templates for consistent code output
- **File Stitching**: Server assembles final Python file from JSON + template

### Step 2.5.1: Define JSON Schema for Python Files
**File**: `src/schemas/files/python_file.py`

**Create Schema**:
```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

class PythonElementType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    DATACLASS = "dataclass"
    IMPORT = "import"
    VARIABLE = "variable"

@dataclass
class PythonFunction:
    name: str
    docstring: Optional[str]
    parameters: list[dict[str, str]]  # [{"name": "x", "type": "int", "default": None}]
    return_type: Optional[str]
    body: str
    decorators: list[str] = None

@dataclass
class PythonClass:
    name: str
    docstring: Optional[str]
    base_classes: list[str]
    methods: list[PythonFunction]
    class_variables: list[dict[str, Any]]

@dataclass
class PythonDataclass:
    name: str
    docstring: Optional[str]
    fields: list[dict[str, str]]  # [{"name": "id", "type": "str", "default": None}]

@dataclass
class PythonFile:
    filename: str
    imports: list[str]
    module_docstring: Optional[str]
    classes: list[PythonClass]
    dataclasses: list[PythonDataclass]
    functions: list[PythonFunction]
    variables: list[dict[str, Any]]
```

### Step 2.5.2: Create Jinja2 Template
**File**: `templates/python_file.j2`

**Template Content**:
```python
{% if module_docstring %}"""{{ module_docstring }}"""

{% endif %}
{% for import_stmt in imports %}
{{ import_stmt }}
{% endfor %}
{% if imports %}

{% endif %}
{% for dataclass in dataclasses %}
@dataclass
class {{ dataclass.name }}:
    {% if dataclass.docstring %}"""{{ dataclass.docstring }}"""

    {% endif %}
    {% for field in dataclass.fields %}
    {{ field.name }}: {{ field.type }}{% if field.default %} = {{ field.default }}{% endif %}
    {% endfor %}

{% endfor %}
{% for class in classes %}
class {{ class.name }}{% if class.base_classes %}({{ class.base_classes | join(', ') }}){% endif %}:
    {% if class.docstring %}"""{{ class.docstring }}"""

    {% endif %}
    {% for method in class.methods %}
    def {{ method.name }}({% for param in method.parameters %}{{ param.name }}{% if param.type %}: {{ param.type }}{% endif %}{% if param.default %} = {{ param.default }}{% endif %}{% if not loop.last %}, {% endif %}{% endfor %}){% if method.return_type %} -> {{ method.return_type }}{% endif %}:
        {% if method.docstring %}"""{{ method.docstring }}"""
        {% endif %}
        {{ method.body | indent(8, first=False) }}

    {% endfor %}

{% endfor %}
{% for function in functions %}
def {{ function.name }}({% for param in function.parameters %}{{ param.name }}{% if param.type %}: {{ param.type }}{% endif %}{% if param.default %} = {{ param.default }}{% endif %}{% if not loop.last %}, {% endif %}{% endfor %}){% if function.return_type %} -> {{ function.return_type }}{% endif %}:
    {% if function.docstring %}"""{{ function.docstring }}"""
    {% endif %}
    {{ function.body | indent(4, first=False) }}

{% endfor %}
```

### Step 2.5.3: Implement JSON File Manager
**File**: `src/core/files/json_file_manager.py`

**Implementation**:
```python
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from src.schemas.files.python_file import PythonFile, PythonFunction, PythonClass

class JsonFileManager:
    def __init__(self, workspace_path: str, templates_path: str = "templates"):
        self.workspace_path = Path(workspace_path)
        self.templates_path = Path(templates_path)
        self.jinja_env = Environment(loader=FileSystemLoader(self.templates_path))

    async def load_file_json(self, filename: str) -> Optional[PythonFile]:
        """Load existing JSON representation of file"""
        json_path = self.workspace_path / f".meta/{filename}.json"
        if json_path.exists():
            with open(json_path, 'r') as f:
                data = json.load(f)
                return PythonFile(**data)
        return None

    async def save_file_json(self, python_file: PythonFile):
        """Save JSON representation of file"""
        json_path = self.workspace_path / f".meta/{python_file.filename}.json"
        json_path.parent.mkdir(exist_ok=True)

        with open(json_path, 'w') as f:
            json.dump(asdict(python_file), f, indent=2)

    async def update_element(self, filename: str, element_type: str, element_data: dict):
        """Update a single element (function/class) in the file"""
        python_file = await self.load_file_json(filename) or PythonFile(
            filename=filename, imports=[], classes=[], dataclasses=[], functions=[], variables=[]
        )

        if element_type == "function":
            # Replace or add function
            func = PythonFunction(**element_data)
            python_file.functions = [f for f in python_file.functions if f.name != func.name]
            python_file.functions.append(func)

        elif element_type == "class":
            # Replace or add class
            cls = PythonClass(**element_data)
            python_file.classes = [c for c in python_file.classes if c.name != cls.name]
            python_file.classes.append(cls)

        await self.save_file_json(python_file)
        await self.render_file(python_file)

    async def render_file(self, python_file: PythonFile):
        """Render Python file from JSON using Jinja2 template"""
        template = self.jinja_env.get_template("python_file.j2")
        rendered = template.render(asdict(python_file))

        output_path = self.workspace_path / python_file.filename
        with open(output_path, 'w') as f:
            f.write(rendered)
```

### Step 2.5.4: Update Agent Response Format
**File**: `src/core/agents/agent/agent.py`

**Modify LLM Prompt**:
```python
code_gen_prompt = f"""Context: {context}

Task: Code Generation for {filename}
Request: {request.message}

You must respond with ONLY a valid JSON object representing a Python code element.

For a FUNCTION, use this format:
{{
    "element_type": "function",
    "element_data": {{
        "name": "function_name",
        "docstring": "Function description",
        "parameters": [
            {{"name": "param1", "type": "str", "default": null}},
            {{"name": "param2", "type": "int", "default": "0"}}
        ],
        "return_type": "bool",
        "body": "    return True",
        "decorators": []
    }}
}}

For a CLASS, use this format:
{{
    "element_type": "class",
    "element_data": {{
        "name": "ClassName",
        "docstring": "Class description",
        "base_classes": ["BaseClass"],
        "methods": [
            {{
                "name": "method_name",
                "docstring": "Method description",
                "parameters": [{{"name": "self", "type": null, "default": null}}],
                "return_type": "None",
                "body": "    pass",
                "decorators": []
            }}
        ],
        "class_variables": []
    }}
}}

Generate the JSON response:"""
```

### Step 2.5.5: Update File Writing Logic
**Replace current file writing with**:
```python
# Parse agent JSON response
json_response = json.loads(raw_response)
element_type = json_response.get("element_type")
element_data = json_response.get("element_data")

# Update file using JSON manager
await self.json_file_manager.update_element(filename, element_type, element_data)
```

## PHASE 3 1/2
Update to allow an agent to manage two files - its main file and its test file (always located at test/test_*main file name*.py) - they should be maintained as separate histories, but this should prevent the explosion of agent #s and keep focus isolated.

## Phase 4: Testing & Validation

### Test Script for Code Generation
```python
# test_code_generation.py
import asyncio
from src.core.agents.agent.agent import Agent
from src.schemas.agents.agents import AgentRequest, TaskType

async def test_clean_output():
    # Create test agent
    agent = create_test_agent()

    # Test code generation
    request = AgentRequest(
        message="Create a simple hello world function",
        task_type=TaskType.CODE_GENERATION,
        agent_id=agent.state.agent_id
    )

    response = await agent.process_request(request)

    # Verify no markdown in output
    assert '```' not in response.content
    assert not response.content.startswith('test.py')

    # Verify valid Python
    try:
        compile(response.content, 'test.py', 'exec')
        print("✅ Generated valid Python code")
    except SyntaxError as e:
        print(f"❌ Invalid Python: {e}")
```

### Test Script for File Awareness
```python
# test_file_awareness.py
async def test_overwrite_protection():
    agent = create_test_agent()

    # First, create a file
    request1 = AgentRequest(
        message="Create a complex chess engine",
        task_type=TaskType.CODE_GENERATION,
        agent_id=agent.state.agent_id
    )
    response1 = await agent.process_request(request1)

    # Try to overwrite without explicit permission
    request2 = AgentRequest(
        message="Create a hello world function",
        task_type=TaskType.CODE_GENERATION,
        agent_id=agent.state.agent_id
    )
    response2 = await agent.process_request(request2)

    # Should get warning, not overwrite
    assert "exists" in response2.content.lower()
    assert "overwrite" in response2.content.lower()
```

## Phase 5: Deployment & Verification

### Step 5.1: Update Docker Container
```bash
# Rebuild with fixes
inv docker-build

# Test with PyChess repo
inv docker-run --repo ~/Projects/PyChess
```

### Step 5.2: Verify All Fixes
```bash
# Test code generation
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "agent_operations",
      "arguments": {
        "operation": "queue_task",
        "agent_id": "YOUR_AGENT_ID",
        "message": "Create a test file",
        "task_type": "code_generation"
      }
    }
  }'

# Check generated file has no syntax errors
python3 ~/Projects/PyChess/generated_file.py

# Verify UI updates
# Open http://localhost:8000/orchestrator
# Queue a task and verify it appears in Task Queue panel
```

## Success Metrics

### Must Pass:
- [ ] Generated Python files compile without syntax errors
- [ ] No markdown wrappers in output files
- [ ] Agents warn before overwriting substantial files
- [ ] Task queue UI shows queued/running tasks
- [ ] Auto-refresh works for active tasks

### Should Pass:
- [ ] Incremental edits preserve existing code
- [ ] Task status updates in real-time
- [ ] File backup before major changes
- [ ] Context preservation across agent interactions

## Rollback Plan

If issues arise:
1. Keep original `agent.py` as `agent_backup.py`
2. Revert to synchronous processing if queue issues persist
3. Use fallback text generation if LLM formatting fails

## Timeline

- **Hour 1-2**: Implement Phase 1 (Code Output Format)
- **Hour 3-4**: Implement Phase 2 (File Awareness)
- **Hour 5**: Implement Phase 3 (UI Fix)
- **Hour 6**: Testing & Validation
- **Hour 7**: Deployment & Documentation
- **Hour 8**: Buffer for issues

## Notes for Claude Code

When implementing:
1. Test each phase independently before moving to next
2. Keep detailed logs of changes for rollback
3. Use mock data to test UI changes before full integration
4. Ensure backwards compatibility with existing agents
5. Document any new agent request parameters

## Critical Files to Backup First

Before making changes, backup:
- `src/core/agents/agent/agent.py`
- `src/core/agents/registry/task_queue.py`
- `static/orchestrator.html`
- `src/schemas/agents/agents.py`

```bash
# Backup command
for file in agent.py task_queue.py orchestrator.html agents.py; do
  cp $file ${file}.backup.$(date +%Y%m%d)
done
```
