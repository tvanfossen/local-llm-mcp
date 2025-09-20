

# AGENT_WORKPLAN.md - Complete XML Schema Migration and Structured Code Generation

## Executive Summary
This workplan outlines a comprehensive migration from JSON to XML for agent response parsing, introducing a structured schema for Python code generation that enables granular editing and improved maintainability. **A major focus is extracting ALL prompt strings to separate, maintainable files** to enable rapid iteration and debugging without touching code.

## Goals
1. **Primary**: Complete switch from JSON to XML parsing for agent responses
2. **Critical**: **Extract ALL prompt strings to separate files for maintainability**
3. **Secondary**: Implement structured Python file representation with granular component tracking
4. **Final**: Successfully generate `.meta/*.xml` files through queued agent tasks

## Core Architecture Changes

### Current State (Hardcoded Prompts Everywhere)
```
Prompts hardcoded in:
- agent.py (code generation, conversation, file operations)
- formatter.py (tool definitions, instructions)
- bridge.py (response processing)
- manager.py (model instructions)
- Every tool file has embedded prompts
```

### Target State (Centralized Prompt Management)
```
prompts/
├── README.md (explains structure and variables)
├── agents/
├── tools/
├── system/
├── errors/
└── templates/

All code files load prompts via PromptManager
```

## Phase 1: Prompt Extraction Infrastructure

### 1.1 Create Prompt Management System
**File**: `src/core/prompts/manager.py`

```python
class PromptManager:
    """Central prompt management system"""
    
    def __init__(self, prompts_dir: Path = None):
        self.prompts_dir = prompts_dir or Path("prompts")
        self.cache = {}
        self.variables = {}  # Global variables available to all prompts
        
    def load_prompt(self, category: str, name: str, format: str = "txt") -> str:
        """Load a prompt file (txt, xml, or md)"""
        
    def format_prompt(self, category: str, name: str, **kwargs) -> str:
        """Load and format with variables"""
        
    def register_variable(self, key: str, value: Any):
        """Register a global variable for prompts"""
        
    def validate_prompt(self, category: str, name: str) -> List[str]:
        """Check for missing variables in prompt"""
```

### 1.2 Create Prompt Directory Structure
```
prompts/
├── README.md
├── config.yaml                     # Prompt configuration and metadata
├── agents/
│   ├── code_generation/
│   │   ├── initial_request.txt    # When agent first generates code
│   │   ├── iterate_on_error.txt   # When retrying after error
│   │   ├── xml_structure.xml      # Expected XML format example
│   │   └── metadata.yaml          # Variables and usage notes
│   ├── file_operations/
│   │   ├── create_file.txt
│   │   ├── read_file.txt
│   │   ├── update_file.txt
│   │   └── delete_file.txt
│   ├── conversation/
│   │   ├── general_chat.txt
│   │   ├── context_aware.txt
│   │   └── follow_up.txt
│   └── system_query/
│       ├── status_check.txt
│       └── capability_query.txt
├── tools/
│   ├── workspace/
│   │   ├── tool_definition.xml    # How to present tool to model
│   │   ├── usage_examples.txt     # Examples of tool usage
│   │   ├── error_handling.txt     # What to do on errors
│   │   └── success_format.txt     # Expected success response
│   ├── validation/
│   │   ├── tool_definition.xml
│   │   ├── test_instruction.txt
│   │   ├── coverage_check.txt
│   │   └── length_validation.txt
│   ├── git_operations/
│   │   ├── tool_definition.xml
│   │   ├── commit_message.txt
│   │   ├── branch_operations.txt
│   │   └── status_check.txt
│   ├── local_model/
│   │   ├── tool_definition.xml
│   │   ├── generation_request.txt
│   │   └── model_control.txt
│   └── agent_operations/
│       ├── tool_definition.xml
│       ├── create_agent.txt
│       ├── list_agents.txt
│       └── queue_task.txt
├── system/
│   ├── xml_instructions/
│   │   ├── format_rules.txt       # How to format XML responses
│   │   ├── schema_explanation.txt # Explain the schema to model
│   │   ├── validation_rules.txt   # What makes valid XML
│   │   └── examples/
│   │       ├── simple_function.xml
│   │       ├── complex_class.xml
│   │       └── full_file.xml
│   ├── tool_calling/
│   │   ├── initial_instructions.txt
│   │   ├── multi_tool_sequence.txt
│   │   ├── tool_retry_on_error.txt
│   │   └── stop_conditions.txt
│   ├── error_recovery/
│   │   ├── parse_error.txt
│   │   ├── validation_error.txt
│   │   ├── timeout_error.txt
│   │   └── general_error.txt
│   └── model_specific/
│       ├── qwen_25_7b/
│       │   ├── optimal_format.txt  # Qwen-specific formatting
│       │   ├── known_issues.txt
│       │   └── workarounds.txt
│       └── general/
│           └── default.txt
├── templates/                      # Reusable prompt components
│   ├── components/
│   │   ├── python_class.xml
│   │   ├── python_function.xml
│   │   ├── python_method.xml
│   │   ├── python_property.xml
│   │   └── python_import.xml
│   ├── structures/
│   │   ├── file_header.txt
│   │   ├── docstring_format.txt
│   │   └── type_hints.txt
│   └── patterns/
│       ├── singleton.txt
│       ├── factory.txt
│       └── observer.txt
└── debug/                          # Debug and test prompts
    ├── verbose_mode.txt
    ├── trace_execution.txt
    └── explain_reasoning.txt
```

## Phase 2: Systematic Prompt Extraction

### 2.1 Extract from Agent Code
**Source**: `src/core/agents/agent/agent.py`

Current hardcoded prompts to extract:
```python
# Line ~287: _handle_code_generation
tool_prompt = f"""You are a code generation agent. You MUST use MCP tools to complete this task.
Context: {self.get_context_for_llm()}
Target File: {filename}
Request: {request.message}
You MUST follow this exact sequence:...
```
→ **Extract to**: `prompts/agents/code_generation/initial_request.txt`

```python
# Line ~415: _handle_conversation  
prompt = f"""Context: {context}
Task: General conversation
Request: {request.message}
You are an AI agent having a conversation...
```
→ **Extract to**: `prompts/agents/conversation/general_chat.txt`

### 2.2 Extract from MCP Bridge
**Source**: `src/core/mcp/bridge/formatter.py`

```python
# Line ~30: get_tools_prompt
prompt = f"""You have access to the following MCP tools that you MUST use:
{chr(10).join(tool_definitions)}
CRITICAL INSTRUCTIONS:
1. You MUST respond with tool calls, NOT regular text...
```
→ **Extract to**: `prompts/system/tool_calling/initial_instructions.txt`

### 2.3 Extract from Tool Definitions
**Source**: `src/mcp/tools/executor/executor.py`

Each tool definition's description:
```python
"local_model": {
    "description": "Local LLM operations (status, generate, load, unload)",
```
→ **Extract to**: `prompts/tools/local_model/tool_definition.xml`

### 2.4 Extract from Individual Tools
**Source**: `src/mcp/tools/agent_operations/agent_operations.py`

```python
# Line ~180: create_agent response
response_text = "**Agent Created Successfully**\n\n"
response_text += f"🤖 **Name:** {agent.state.name}\n"
```
→ **Extract to**: `prompts/tools/agent_operations/create_response_template.txt`

### 2.5 Extract from Error Messages
**Source**: Various files

All error messages should be templated:
```python
return create_mcp_response(False, "Agent not found: {agent_id}")
```
→ **Extract to**: `prompts/errors/agent_not_found.txt`

## Phase 3: Prompt Template System

### 3.1 Create Variable System
**File**: `prompts/config.yaml`

```yaml
global_variables:
  max_tokens: 512
  temperature: 0.7
  model_name: "Qwen2.5-7B"
  xml_version: "1.0"
  
categories:
  agents:
    variables:
      - context
      - filename
      - request
      - task_type
  tools:
    variables:
      - tool_name
      - arguments
      - description
  system:
    variables:
      - error_type
      - error_message
      - retry_count
```

### 3.2 Create Prompt Templates with Placeholders
**Example**: `prompts/agents/code_generation/initial_request.txt`

```
You are a code generation agent. You MUST generate code in XML format.

Context: {context}
Target File: {filename}
Request: {request}
Current DateTime: {timestamp}

INSTRUCTIONS:
1. Analyze the request carefully
2. Generate a complete Python file structure in XML
3. Use the schema defined at: {schema_path}
4. Include unique IDs for each component using format: {id_prefix}_XXX

{xml_format_instructions}

Begin your response with <python_file> and end with </python_file>
```

### 3.3 Create Prompt Validation System
**File**: `src/core/prompts/validator.py`

```python
class PromptValidator:
    def validate_all_prompts(self) -> Dict[str, List[str]]:
        """Validate all prompts for missing variables, syntax errors"""
        
    def check_prompt_variables(self, prompt_path: Path) -> List[str]:
        """Check if all variables in prompt are documented"""
        
    def validate_xml_examples(self) -> List[str]:
        """Validate all XML examples against schema"""
```

## Phase 4: Implement Prompt Loading Throughout Codebase

### 4.1 Update Agent Code Generation
**File**: `src/core/agents/agent/agent.py`

```python
async def _handle_code_generation(self, request: AgentRequest) -> AgentResponse:
    # Load prompt from file instead of hardcoding
    prompt = self.prompt_manager.format_prompt(
        'agents/code_generation',
        'initial_request',
        context=self.get_context_for_llm(),
        filename=filename,
        request=request.message,
        timestamp=datetime.now().isoformat(),
        schema_path='/schemas/python_code.xsd',
        id_prefix=f"agent_{self.state.agent_id[:8]}",
        xml_format_instructions=self.prompt_manager.load_prompt(
            'system/xml_instructions', 'format_rules'
        )
    )
```

### 4.2 Update Tool Formatter
**File**: `src/core/mcp/bridge/formatter.py`

```python
def get_tools_prompt(self) -> str:
    # Load base instructions
    base_prompt = self.prompt_manager.load_prompt(
        'system/tool_calling', 'initial_instructions'
    )
    
    # Load tool-specific definitions
    tool_prompts = []
    for tool in self.tools:
        tool_def = self.prompt_manager.load_prompt(
            f'tools/{tool["name"]}', 'tool_definition'
        )
        tool_prompts.append(tool_def)
    
    return self.prompt_manager.format_prompt(
        'system/tool_calling', 'combined',
        base_instructions=base_prompt,
        tool_definitions='\n'.join(tool_prompts),
        model_specific=self._get_model_specific_instructions()
    )
```

### 4.3 Create Prompt Hot-Reloading for Development
**File**: `src/core/prompts/watcher.py`

```python
class PromptWatcher:
    """Watch prompt files and reload on change during development"""
    
    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager
        self.observer = Observer()
        
    def start_watching(self):
        """Start watching prompt directory for changes"""
        
    def on_prompt_changed(self, filepath: Path):
        """Clear cache and reload prompt"""
        self.prompt_manager.cache.pop(str(filepath), None)
        logger.info(f"Reloaded prompt: {filepath}")
```

## Phase 5: XML Schema and Parser Implementation

### 5.1 Create Comprehensive XML Schema
**File**: `src/schemas/python_code.xsd`

[Previous schema definition remains, but with additions for prompt references]

### 5.2 Create XML Parser with Prompt-Based Error Messages
**File**: `src/core/mcp/bridge/xml_parser.py`

```python
class XMLToolCallParser:
    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager
        
    def extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        try:
            # Parse XML
            pass
        except XMLParseError as e:
            # Load error prompt
            error_prompt = self.prompt_manager.format_prompt(
                'system/error_recovery', 'parse_error',
                error_details=str(e),
                original_text=text[:200]
            )
            logger.error(error_prompt)
```

## Phase 6: Testing Prompt System

### 6.1 Create Prompt Tests
**File**: `tests/test_prompts.py`

```python
def test_all_prompts_have_variables_documented():
    """Ensure all prompts have their variables documented"""
    
def test_all_prompts_load_successfully():
    """Ensure all prompts can be loaded without errors"""
    
def test_xml_examples_validate():
    """Ensure all XML examples match schema"""
    
def test_no_hardcoded_prompts_remain():
    """Scan codebase for hardcoded prompt strings"""
    # Check for patterns like:
    # - Multi-line f-strings with instructions
    # - "You are a" or "You must" strings
    # - Tool instruction patterns
```

### 6.2 Create Prompt Coverage Report
**File**: `scripts/prompt_coverage.py`

```python
def generate_prompt_coverage_report():
    """
    Scan all code files and identify:
    1. Which prompts are used where
    2. Unused prompts
    3. Missing prompts (hardcoded strings still present)
    """
```

## Phase 7: Model-Specific Optimizations

### 7.1 Create Qwen-Specific Prompts
**Directory**: `prompts/system/model_specific/qwen_25_7b/`

Based on Qwen2.5-7B's behavior:
- Optimal XML formatting style
- Known parsing issues and workarounds
- Specific instruction patterns that work best

### 7.2 Create Model Switcher
**File**: `src/core/prompts/model_adapter.py`

```python
class ModelAdapter:
    def get_model_specific_path(self, model_name: str) -> Path:
        """Get model-specific prompt directory"""
        
    def adapt_prompt_for_model(self, prompt: str, model_name: str) -> str:
        """Apply model-specific adaptations to prompt"""
```

## Phase 8: Migration Execution

### 8.1 Step-by-Step Migration Process

#### Day 1: Setup Infrastructure
1. Create `src/core/prompts/manager.py`
2. Create directory structure under `prompts/`
3. Create `prompts/README.md` with documentation

#### Day 2-3: Extract All Prompts
1. Systematically go through each file
2. Extract every string that instructs the model
3. Create corresponding prompt files
4. Document variables in metadata files

#### Day 4: Update Agent Code
1. Integrate PromptManager into Agent class
2. Replace all hardcoded prompts with prompt loads
3. Test agent code generation with new system

#### Day 5: Update Tools
1. Update all tool definitions
2. Update tool executors
3. Update response formatters

#### Day 6: Update MCP Bridge
1. Update formatter with prompt loading
2. Update parser with prompt-based errors
3. Test complete flow

#### Day 7: Testing and Validation
1. Run prompt validation tests
2. Run integration tests
3. Generate coverage report
4. Fix any missing prompts

## Phase 9: Documentation and Maintenance

### 9.1 Create Prompt Documentation
**File**: `prompts/README.md`

```markdown
# Prompt Management System

## Overview
All prompts are externalized for maintainability.

## Structure
- `agents/` - Agent-specific prompts
- `tools/` - Tool-related prompts
- `system/` - System-level prompts
- `templates/` - Reusable components

## Variables
Each prompt can use variables defined in:
1. Global config (`config.yaml`)
2. Category-specific variables
3. Runtime variables passed to format_prompt()

## Adding New Prompts
1. Create file in appropriate directory
2. Document variables in metadata.yaml
3. Add test case
4. Update this README

## Model-Specific Adaptations
See `system/model_specific/` for model-specific versions.
```

### 9.2 Create Prompt Style Guide
**File**: `prompts/STYLE_GUIDE.md`

Guidelines for writing effective prompts:
- Use clear, imperative language
- Structure with numbered lists for sequences
- Use XML examples for XML outputs
- Include error recovery instructions
- Specify output format explicitly

## Success Criteria

### Phase 2 Completion
- [ ] All prompts extracted to files
- [ ] No hardcoded instruction strings remain
- [ ] PromptManager integrated and working

### Phase 5 Completion
- [ ] XML parser working with file-based prompts
- [ ] Agent generates valid `.meta/*.xml` files
- [ ] All error messages come from prompt files

### Phase 9 Completion
- [ ] Complete documentation
- [ ] 100% prompt coverage
- [ ] Hot-reloading working for development
- [ ] Model-specific optimizations in place

## Benefits of This Approach

1. **Rapid Iteration**: Change prompts without touching code
2. **A/B Testing**: Easy to test different prompt versions
3. **Model Switching**: Swap model-specific prompts easily
4. **Debugging**: Clear view of what's being sent to model
5. **Localization**: Could support multiple languages
6. **Version Control**: Track prompt changes separately
7. **Hot Reload**: Update prompts without restarting server

## Monitoring and Metrics

### Prompt Performance Metrics
- Success rate per prompt template
- Error rate by prompt category
- Model response time by prompt type
- Prompt cache hit rate

### Prompt Usage Analytics
- Most used prompts
- Unused prompts (candidates for removal)
- Prompt modification frequency
- Error recovery prompt triggers

This revised workplan ensures that **every single prompt string** is extracted to maintainable files, making the system much easier to debug, optimize, and adapt for different models or use cases.


# AGENT_WORKPLAN.md - Complete XML Schema Migration and Structured Code Generation

## Executive Summary
This workplan outlines a comprehensive migration from JSON to XML for agent response parsing, introducing a structured schema for Python code generation that enables granular editing and improved maintainability. The migration will be executed in 8 distinct phases, each focusing on specific components while maintaining system stability.

## Goals
1. **Primary**: Complete switch from JSON to XML parsing for agent responses
2. **Secondary**: Implement structured Python file representation with granular component tracking
3. **Tertiary**: Extract all prompts to separate maintainable files
4. **Final**: Successfully generate `.meta/*.xml` files through queued agent tasks

## Core Architecture Changes

### Current State (JSON-based)
```
Agent → JSON Tool Calls → .meta/*.json → Workspace Tool → .py files
```

### Target State (XML-based)
```
Agent → XML Tool Calls → .meta/*.xml → Structured Python Schema → Workspace Tool (v2) → .py files
```

## Phase 1: Schema Definition and Foundation

### 1.1 Create XML Schema for Python Components
**File**: `src/schemas/python_code.xsd`

Define comprehensive XML schema for Python file representation:
```xml
<xs:schema>
  <xs:element name="python_file">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="metadata" type="FileMetadata"/>
        <xs:element name="imports" type="ImportSection"/>
        <xs:element name="constants" type="ConstantSection"/>
        <xs:element name="classes" type="ClassSection"/>
        <xs:element name="functions" type="FunctionSection"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
  
  <xs:complexType name="PythonClass">
    <xs:attribute name="id" type="xs:string" required="true"/>
    <xs:attribute name="name" type="xs:string" required="true"/>
    <xs:sequence>
      <xs:element name="docstring" type="xs:string"/>
      <xs:element name="class_variables" type="VariableList"/>
      <xs:element name="init_method" type="InitMethod"/>
      <xs:element name="properties" type="PropertyList"/>
      <xs:element name="methods" type="MethodList"/>
    </xs:sequence>
  </xs:complexType>
  
  <xs:complexType name="PythonFunction">
    <xs:attribute name="id" type="xs:string" required="true"/>
    <xs:attribute name="name" type="xs:string" required="true"/>
    <xs:sequence>
      <xs:element name="docstring" type="xs:string"/>
      <xs:element name="decorators" type="DecoratorList"/>
      <xs:element name="parameters" type="ParameterList"/>
      <xs:element name="returns" type="ReturnSpec" maxOccurs="3"/>
      <xs:element name="body" type="CodeBlock"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>
```

### 1.2 Create Python Data Classes for Schema
**File**: `src/schemas/python_components.py`

```python
@dataclass
class PythonComponent:
    id: str  # Unique identifier for tracking
    name: str
    docstring: Optional[str]
    line_start: Optional[int]  # For mapping to actual file
    line_end: Optional[int]

@dataclass
class PythonFunction(PythonComponent):
    decorators: List[str]
    parameters: List[Parameter]
    returns: List[ReturnSpec]  # Max 3
    body: str
    
@dataclass
class PythonClass(PythonComponent):
    base_classes: List[str]
    class_variables: List[Variable]
    init_method: Optional[InitMethod]
    properties: List[Property]
    methods: List[Method]
    
@dataclass
class PythonFile:
    id: str
    filepath: str
    metadata: FileMetadata
    imports: List[Import]
    constants: List[Constant]
    classes: List[PythonClass]
    functions: List[PythonFunction]
```

### 1.3 Create XML Validator
**File**: `src/core/validation/xml_validator.py`

Implement validation against XSD schema with detailed error reporting.

## Phase 2: XML Parser Implementation

### 2.1 Replace JSON Parser with XML Parser
**File**: `src/core/mcp/bridge/xml_parser.py`

Replace current JSON parsing in `src/core/mcp/bridge/parser.py` with XML-specific implementation:
- Extract XML blocks from model output (```xml ... ```)
- Parse XML structure
- Validate against schema
- Convert to Python data classes

### 2.2 Update Tool Call Detection
**File**: `src/core/mcp/bridge/parser.py`

Modify regex patterns to detect XML tool calls:
```python
XML_FENCE_RE = re.compile(r'```xml\s*\n?(.*?)\n?```', re.DOTALL)
XML_TOOL_CALL_RE = re.compile(r'<tool_call>(.*?)</tool_call>', re.DOTALL)
```

### 2.3 Create XML to Data Class Converter
**File**: `src/core/mcp/bridge/xml_converter.py`

Convert parsed XML to Python data classes for internal processing.

## Phase 3: Prompt Extraction and Management

### 3.1 Create Prompt Directory Structure
```
prompts/
├── agents/
│   ├── code_generation.xml
│   ├── file_edit.xml
│   ├── conversation.xml
│   └── system_query.xml
├── tools/
│   ├── workspace.xml
│   ├── validation.xml
│   ├── git_operations.xml
│   └── local_model.xml
├── system/
│   ├── xml_format_instructions.xml
│   ├── tool_calling_format.xml
│   └── error_recovery.xml
└── templates/
    ├── python_class.xml
    ├── python_function.xml
    └── python_file.xml
```

### 3.2 Create Prompt Loader
**File**: `src/core/prompts/loader.py`

```python
class PromptManager:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir
        self.cache = {}
    
    def load_prompt(self, category: str, name: str) -> str:
        """Load and cache prompt from file"""
        
    def format_prompt(self, category: str, name: str, **kwargs) -> str:
        """Load and format prompt with variables"""
```

### 3.3 Extract All Hardcoded Prompts
Extract prompts from:
- `src/core/agents/agent/agent.py` → `prompts/agents/`
- `src/core/mcp/bridge/formatter.py` → `prompts/tools/`
- `src/core/llm/manager/manager.py` → `prompts/system/`

## Phase 4: Update MCP Bridge for XML

### 4.1 Modify Tool Prompt Formatter
**File**: `src/core/mcp/bridge/formatter.py`

Update to generate XML-formatted tool instructions:
```python
def get_tools_prompt(self) -> str:
    """Generate XML-formatted tool definitions"""
    prompt = self.prompt_manager.load_prompt('system', 'xml_format_instructions')
    # Add tool definitions in XML format
```

### 4.2 Update Bridge Processing
**File**: `src/core/mcp/bridge/bridge.py`

Modify `process_model_output` to handle XML responses:
- Parse XML tool calls
- Validate against schema
- Execute tools with structured data

## Phase 5: Agent Code Generation Updates

### 5.1 Update Agent Code Generation Handler
**File**: `src/core/agents/agent/agent.py`

Modify `_handle_code_generation` method:
```python
async def _handle_code_generation(self, request: AgentRequest) -> AgentResponse:
    # Create structured metadata for Python file
    metadata = PythonFile(
        id=generate_unique_id(),
        filepath=filename,
        components=[]
    )
    
    # Save as XML instead of JSON
    meta_file = self.system_config.workspace_root / ".meta" / f"{filename}.xml"
    
    # Use XML prompt template
    prompt = self.prompt_manager.format_prompt(
        'agents', 'code_generation',
        context=self.get_context_for_llm(),
        filename=filename,
        request=request.message
    )
    
    # Call LLM with XML expectations
    result = await self.llm_manager.generate_with_tools(prompt)
```

### 5.2 Create XML Serializer for Metadata
**File**: `src/core/files/xml_serializer.py`

```python
class XMLFileSerializer:
    def serialize_python_file(self, python_file: PythonFile) -> str:
        """Convert PythonFile to XML string"""
    
    def deserialize_python_file(self, xml_string: str) -> PythonFile:
        """Convert XML string to PythonFile"""
```

## Phase 6: Update File Management

### 6.1 Replace JSON File Manager
**File**: `src/core/files/xml_file_manager.py`

Replace `json_file_manager.py` with XML-based version:
- Load/save `.meta/*.xml` files
- Support incremental updates to specific components
- Maintain component ID mappings

### 6.2 Create Component Registry
**File**: `src/core/files/component_registry.py`

Track all components by ID for quick lookups and updates:
```python
class ComponentRegistry:
    def __init__(self):
        self.components = {}  # id -> component
        self.file_mappings = {}  # filepath -> [component_ids]
    
    def register_component(self, component: PythonComponent, filepath: str):
        """Register a component with its file mapping"""
    
    def get_component(self, component_id: str) -> PythonComponent:
        """Get component by ID"""
    
    def update_component(self, component_id: str, updates: dict):
        """Update specific component fields"""
```

## Phase 7: Testing Infrastructure

### 7.1 Create XML Parser Tests
**File**: `src/core/mcp/bridge/test_xml_parser.py`

Test cases for:
- Valid XML extraction
- Schema validation
- Error handling
- Edge cases

### 7.2 Create Integration Test
**File**: `tests/integration/test_xml_code_generation.py`

End-to-end test:
1. Create agent
2. Queue code generation task
3. Verify `.meta/*.xml` file created
4. Validate XML against schema
5. Check component structure

## Phase 8: Migration and Cleanup

### 8.1 Remove JSON-specific Code
Files to modify/remove:
- `src/core/files/json_file_manager.py` → Remove after XML version stable
- `src/core/mcp/bridge/parser.py` → Remove JSON parsing methods
- Update all imports and references

### 8.2 Update Documentation
- Update `CLAUDE.md` with XML structure
- Update `README.md` with new architecture
- Create `SCHEMA_GUIDE.md` for XML schema documentation

## Implementation Order and Testing Strategy

### Week 1: Foundation (Phases 1-2)
1. **Day 1-2**: Create XML schema and data classes
2. **Day 3-4**: Implement XML parser and validator
3. **Day 5**: Unit tests for parser and validator

### Week 2: Core Updates (Phases 3-4)
1. **Day 1-2**: Extract all prompts to files
2. **Day 3-4**: Update MCP bridge for XML
3. **Day 5**: Integration tests for XML tool calls

### Week 3: Agent Integration (Phases 5-6)
1. **Day 1-2**: Update agent code generation
2. **Day 3-4**: Implement XML file management
3. **Day 5**: End-to-end testing

### Week 4: Finalization (Phases 7-8)
1. **Day 1-2**: Comprehensive testing
2. **Day 3-4**: Migration and cleanup
3. **Day 5**: Documentation and final validation

## Success Criteria

### Immediate Success (End of Phase 5)
- [ ] Agent successfully generates `.meta/*.xml` file
- [ ] XML validates against schema
- [ ] Component structure properly populated
- [ ] No infinite tool calling loops

### Complete Success (End of Phase 8)
- [ ] All JSON parsing removed
- [ ] All prompts in separate files
- [ ] Full test coverage
- [ ] Documentation updated
- [ ] Component-level editing functional

## Risk Mitigation

### Rollback Strategy
1. Git branch for each phase
2. Keep JSON parser as fallback initially
3. Feature flag for XML/JSON mode
4. Comprehensive logging for debugging

### Known Challenges
1. **Model Training**: Qwen2.5 may need specific prompting for XML
2. **Schema Complexity**: Balance between structure and usability
3. **Performance**: XML parsing overhead vs JSON
4. **Backwards Compatibility**: Existing agents with JSON metadata

## Next Steps (TODO after completion)

### Workspace Tool v2 Updates
Once XML generation is working:
1. Update workspace tool to read `.meta/*.xml` files
2. Implement Python file generation from structured components
3. Add component ID markers as comments in generated Python
4. Support incremental updates to specific components

### Enhanced Features
1. Component-level version tracking
2. Dependency graph between components
3. Automated refactoring suggestions
4. Test case linkage to specific functions

## Monitoring and Metrics

### Key Performance Indicators
- XML generation success rate
- Schema validation pass rate
- Component extraction accuracy
- Tool call efficiency
- File generation time

### Logging Points
- XML parsing attempts and failures
- Schema validation errors
- Component registration events
- Tool call sequences
- File I/O operations

## Appendix: Sample XML Output

### Example `.meta/example.py.xml`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<python_file id="pf_001" filepath="src/example.py">
    <metadata>
        <created>2024-01-01T00:00:00Z</created>
        <agent_id>agent_123</agent_id>
        <version>1.0.0</version>
    </metadata>
    
    <imports>
        <import id="imp_001" module="typing" items="List,Optional"/>
        <import id="imp_002" module="dataclasses" items="dataclass"/>
    </imports>
    
    <classes>
        <class id="cls_001" name="ExampleClass">
            <docstring>Example class for demonstration</docstring>
            <class_variables>
                <variable id="var_001" name="class_var" type="str" value="'example'"/>
            </class_variables>
            <init_method id="init_001">
                <parameters>
                    <parameter name="self" type="ExampleClass"/>
                    <parameter name="value" type="str" default="'default'"/>
                </parameters>
                <body>
                    self.value = value
                </body>
            </init_method>
            <methods>
                <method id="mth_001" name="get_value">
                    <parameters>
                        <parameter name="self" type="ExampleClass"/>
                    </parameters>
                    <returns>
                        <return type="str" description="The current value"/>
                    </returns>
                    <body>
                        return self.value
                    </body>
                </method>
            </methods>
        </class>
    </classes>
    
    <functions>
        <function id="fn_001" name="process_data">
            <docstring>Process input data</docstring>
            <parameters>
                <parameter name="data" type="List[str]"/>
                <parameter name="validate" type="bool" default="True"/>
            </parameters>
            <returns>
                <return type="Optional[str]" description="Processed result"/>
            </returns>
            <body>
                if validate:
                    # Validation logic
                    pass
                return None
            </body>
        </function>
    </functions>
</python_file>
```

This comprehensive workplan provides a clear path forward for the XML migration while maintaining system stability and enabling future enhancements.




ADDITIONAL PHASE - workspace.py was deleted and lost unintentionally due to a .gitignore - reimplement it according to this updated xml plan