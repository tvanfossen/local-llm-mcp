# AGENT_TODO.md - Local LLM MCP Agent System

## 🔥 CRITICAL - Model Output Issues (Priority 1)
- [ ] Fix JSON-only output confusion in `tool_calling_json.json`
- [ ] Add structure clarification to formatter.py prompt generation  
- [ ] Implement minimum tool call validation in agent.py
- [ ] Enhance parser error detection for Python code contamination
- [ ] Add auto-completion with generate_from_metadata

## 🎯 HIGH - Workflow Improvements (Priority 2)
- [ ] Add tool call retry mechanism when model outputs wrong format
- [ ] Implement progressive prompting (simpler instructions for confused models)
- [ ] Create tool call validation middleware before execution
- [ ] Add metrics tracking for successful vs failed tool call patterns
- [ ] Build tool call sequence validator (ensures proper order)

## 📊 MEDIUM - Monitoring & Diagnostics (Priority 3)
- [ ] Create dashboard for tool call success rates
- [ ] Add model confusion detection (track when model outputs code vs JSON)
- [ ] Build prompt effectiveness analyzer
- [ ] Implement A/B testing for different prompt formats
- [ ] Add telemetry for token usage per tool call

## 🔧 LOW - Quality of Life (Priority 4)
- [ ] Create example gallery of successful tool call sequences
- [ ] Build prompt template library for common tasks
- [ ] Add tool call history viewer in UI
- [ ] Create debugging mode with verbose model output
- [ ] Implement prompt caching for frequently used patterns

## Recently Completed ✅
- [x] Phase 1: MCP Bridge Infrastructure created
- [x] Phase 2: Agent metadata workflow fixed (no direct file creation)
- [x] Phase 3: Removed placeholder success returns
- [x] Phase 4: Task queue integration with MCP tools
- [x] Phase 5: Comprehensive logging throughout system
- [x] Unified parser with JSON-only strategy
- [x] Tool prompt formatter with prompt manager integration

## Known Issues 🐛
1. **Model Confusion**: Qwen2.5-7B outputs Python code mixed with JSON tool calls
2. **Incomplete Workflows**: Only 2 tool calls generated when 8-12 expected
3. **Wrong Structure**: Model uses metadata structure instead of tool call structure
4. **Silent Partial Success**: Agent reports success with incomplete tool calls
5. **No Retry Logic**: Single attempt even when model is clearly confused

## Test Cases Needed 🧪
- [ ] Calculator class with multiple methods
- [ ] File with complex imports and dependencies
- [ ] Class with inheritance and decorators
- [ ] Module with multiple classes
- [ ] Async function implementations

## Performance Targets 📈
- Tool call success rate: >90%
- Average tool calls per task: 8-12
- Parser warning rate: <5%
- Workflow completion rate: >95%
- Model confusion incidents: <10%

## Next Sprint Focus 🏃
1. Implement all Priority 1 fixes from OPUS_REPORT.md
2. Test with Calculator example
3. Measure improvement in success metrics
4. Document successful prompt patterns
5. Create troubleshooting guide for common failures

## Long-term Vision 🔭
- Self-improving prompt system based on success patterns
- Automatic model confusion detection and correction
- Multi-model support with format adaptation
- Tool call optimization for token efficiency
- Automated testing of prompt effectiveness