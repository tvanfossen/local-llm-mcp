# AGENT TODO

This file tracks issues and improvements needed across the local-llm-mcp system.

## CRITICAL Priority Issues
*Issues that could cause system failure or security breaches*

- [ ] **ASYNC TASK QUEUE HANGING**: Second MCP tool call for queuing tasks hangs indefinitely, indicating async task completion detection is malfunctioning. This blocks concurrent agent processing and makes the system unreliable for multi-agent workflows.
- [ ] **WORKSPACE WRITE TOOL STILL AVAILABLE**: Despite previous removal attempts, workspace write operations are still accessible, bypassing the metadata-first workflow enforcement. This allows agents to write files directly without structured validation.
- [ ] **SILENT FALLBACK FAILURE**: Agents generate generic template code when specific requirements fail, reporting "success" while actually failing to meet the task. This creates false positives where system appears to work but produces useless output. Must implement graceful failure with clear error reporting instead of fallback templates.
- [x] **COMPLETED**: Successfully converted entire system from XML to JSON for tool calls, metadata, and schema enforcement. JSON provides better model compliance and structured output.

## HIGH Priority Issues
*Issues that significantly impact functionality or user experience*

- [ ] **METADATA CONTEXT WINDOW OVERLOAD**: Local Qwen2.5-7B model (8192 context) loses track of JSON schema when generating large metadata structures, resulting in incomplete or malformed metadata. Need to break metadata generation into smaller, atomic operations.
- [ ] **RAW TEXT IN METADATA BODY FIELDS**: System allows raw Python code in metadata "body" fields, defeating the purpose of structured data and Jinja2 templates. This prevents proper validation and schema enforcement.
- [ ] **MISSING METADATA SCHEMA VALIDATION**: No JSON Schema validation exists to catch malformed metadata before it's written to files, allowing corrupted data to persist and break code generation.
- [ ] **INTERFACE REGISTRY CONTENT EMPTY**: Interface registry isn't extracting meaningful export information from classes/functions, leaving dependent agents without context about available interfaces.
- **Consider a change that allows us to use MCP protocols json rpc methodology to inform claude (or the orchestrator html) when a task has finished**
- **Orchestrator html page needs updates - queue refresh doesnt show active tasks, consider adding a chat window to replace claude code for entirely local generation**

## MEDIUM Priority Issues
*Issues that should be addressed for production readiness*

- [ ] **Authentication Security Gap**: The MCP server authentication accepts ANY non-empty string as a private key (src/core/security/manager/manager.py:create_session()). This is development-mode only behavior that needs proper key validation before production use.
- **Add additional supported code templates for Java, C/C++, C#**

## LOW Priority Issues
*Nice-to-have improvements and optimizations*

- [ ] **Consider adding some sort of sms notification system to allow remote prompting of the local model**
- [ ] **Template Architecture**: Replace monolithic python_file.j2 template with smaller, modular templates (class.j2, function.j2, etc.) as specified by the model for better maintainability
- [x] **COMPLETED**: Unified tool calling now uses JSON-only format with consistent "parameters" structure. XML parsing completely removed.
- [x] **COMPLETED**: All tool calling now uses structured JSON format with proper schema validation.

---
*File maintained by agents and developers - add issues as they are discovered*