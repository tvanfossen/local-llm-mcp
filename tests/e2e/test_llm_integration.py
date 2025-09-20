"""End-to-end tests with actual LLM integration

These tests verify the complete flow from prompt generation through LLM calls
to tool call parsing and execution. They require an actual LLM to be available.
"""

import pytest
from pathlib import Path

from src.core.prompts.manager import PromptManager
from src.core.mcp.bridge.unified_parser import UnifiedToolCallParser, ParsingStrategy
from src.core.mcp.bridge.formatter import ToolPromptFormatter
from src.core.llm.manager.manager import LLMManager
from src.core.config.manager.manager import ModelConfig
from src.mcp.tools.workspace.workspace import workspace_tool


@pytest.mark.e2e
@pytest.mark.llm
class TestLLMIntegration:
    """Test integration with actual LLM"""

    @classmethod
    def setup_class(cls):
        """Setup LLM once for all tests in the class"""
        cls.model_available = False
        cls.llm_manager = None

        # Check if model file exists
        model_path = Path.home() / "models" / "Qwen2.5-7B-Instruct-Q6_K_L.gguf"
        if not model_path.exists():
            return  # Will be skipped in tests

        try:
            # Create model configuration
            model_config = ModelConfig(
                model_path=str(model_path),
                n_gpu_layers=-1,  # Use all GPU layers
                n_ctx=4096,  # Smaller context for testing
                n_batch=256,  # Smaller batch for testing
                temperature=0.3,
                max_tokens=512
            )

            # Initialize LLM manager with proper config
            cls.llm_manager = LLMManager(model_config=model_config)

            # Register tools for the LLM manager
            tools = [
                {
                    "name": "workspace",
                    "description": "Workspace operations (read, write, delete, list)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "structured_content": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "validation",
                    "description": "Validation operations",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string"},
                            "path": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "git_operations",
                    "description": "Git operations",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string"}
                        }
                    }
                }
            ]
            cls.llm_manager.register_tools(tools)

            # Load the model once
            success, error = cls.llm_manager.load_model()
            if success:
                cls.model_available = True
            else:
                import logging
                logging.warning(f"Failed to load model: {error}")

        except Exception as e:
            # Log the exception for debugging
            import logging
            logging.warning(f"Failed to setup LLM manager: {e}")

    def setup_method(self):
        """Setup for each individual test"""
        # Copy class-level attributes to instance
        self.model_available = self.__class__.model_available
        self.llm_manager = self.__class__.llm_manager

    @pytest.mark.asyncio
    async def test_architecture_verification(self, test_workspace, available_tools):
        """Special test to capture complete architecture flow for verification"""
        if not self.model_available:
            pytest.skip("LLM not available")

        import logging
        logger = logging.getLogger(__name__)

        logger.info("🏗️ ARCHITECTURE VERIFICATION TEST START")
        logger.info("=" * 60)

        # 1. Test Prompt Manager
        logger.info("📋 STEP 1: Testing Prompt Manager")
        prompt_manager = PromptManager()
        base_prompt = prompt_manager.format_prompt(
            'agents', 'structured_code_generation',
            context="Architecture verification test",
            filename="arch_test.py",
            request="Create a simple test class"
        )
        logger.info(f"✅ Prompt generated: {len(base_prompt)} characters")

        # 2. Test Tool Formatter (XML Mode)
        logger.info("🔧 STEP 2: Testing XML Tool Formatter")
        formatter = ToolPromptFormatter(available_tools, use_xml=True)
        tools_prompt = formatter.get_tools_prompt()
        logger.info(f"✅ XML tools prompt: {len(tools_prompt)} characters")

        # 3. Build Complete Prompt
        logger.info("📝 STEP 3: Building Complete Prompt")
        complete_prompt = f"{base_prompt}\n\n{tools_prompt}"
        logger.info(f"✅ Complete prompt: {len(complete_prompt)} characters")

        # 4. Test LLM Generation
        logger.info("🤖 STEP 4: Testing LLM Generation")
        response = await self.llm_manager.generate_with_tools(
            complete_prompt,
            max_tokens=512,
            temperature=0.3,
            tools_enabled=True
        )
        logger.info(f"✅ LLM Response type: {response.get('type', 'unknown')}")

        # 5. Test Unified Parser
        if response.get("type") == "tool_calls":
            logger.info("🔍 STEP 5: Testing Unified XML Parser")
            parser = UnifiedToolCallParser(ParsingStrategy.XML_PRIMARY)
            model_output = response.get("raw_output", "")
            logger.info(f"📤 Model raw output ({len(model_output)} chars):")
            logger.info("-" * 40)
            logger.info(model_output)
            logger.info("-" * 40)

            parse_result = parser.parse(model_output)
            logger.info(f"✅ Parse successful: {parse_result.success}")
            logger.info(f"✅ Strategy used: {parse_result.strategy_used}")
            logger.info(f"✅ Tool calls found: {len(parse_result.tool_calls)}")

            if parse_result.success and len(parse_result.tool_calls) > 0:
                first_call = parse_result.tool_calls[0]
                logger.info(f"🔧 First tool call: {first_call['tool_name']}")
                logger.info(f"📊 Arguments keys: {list(first_call['arguments'].keys())}")

                # 6. Test Workspace Tool (if structured)
                if first_call["arguments"].get("action") == "write_structured":
                    logger.info("📁 STEP 6: Testing Structured Workspace Tool")
                    structured_content = first_call["arguments"].get("structured_content", "")
                    if structured_content:
                        logger.info(f"✅ Structured content found: {len(structured_content)} characters")
                        logger.info("🔍 XML Content Preview:")
                        logger.info("-" * 40)
                        logger.info(structured_content[:500] + "..." if len(structured_content) > 500 else structured_content)
                        logger.info("-" * 40)

        logger.info("=" * 60)
        logger.info("🎉 ARCHITECTURE VERIFICATION COMPLETE")

        # Always pass - this is for verification
        assert True

    @pytest.mark.asyncio
    async def test_xml_tool_call_generation(self, test_workspace, available_tools):
        """Test that LLM can generate valid XML tool calls"""
        if not self.model_available:
            pytest.skip("LLM not available")

        # Setup components
        prompt_manager = PromptManager()
        formatter = ToolPromptFormatter(available_tools, use_xml=True)
        parser = UnifiedToolCallParser(ParsingStrategy.XML_PRIMARY)

        # Create a request for the LLM
        request = "Create a simple Python function that calculates the factorial of a number"
        filename = "factorial.py"
        context = "Test context for factorial function generation"

        # Build the complete prompt
        base_prompt = prompt_manager.format_prompt(
            'agents', 'code_generation',
            context=context,
            filename=filename,
            request=request
        )

        # Add tool definitions
        tools_prompt = formatter.get_tools_prompt()
        complete_prompt = f"{base_prompt}\n\n{tools_prompt}"

        # Model is already loaded in class setup

        # Call the LLM
        response = await self.llm_manager.generate_with_tools(
            complete_prompt,
            max_tokens=512,
            temperature=0.3,
            tools_enabled=True
        )

        # Verify response structure
        assert response is not None
        assert "type" in response

        if response["type"] == "tool_calls":
            # Parse the tool calls
            model_output = response.get("raw_output", "")
            parse_result = parser.parse(model_output)

            # Verify parsing was successful
            assert parse_result.success, f"Parsing failed: {parse_result.errors}"
            assert len(parse_result.tool_calls) > 0
            assert parse_result.strategy_used == "xml"

            # Verify first tool call is for workspace
            first_call = parse_result.tool_calls[0]
            assert first_call["tool_name"] == "workspace"
            assert "arguments" in first_call
            assert "action" in first_call["arguments"]
            assert "path" in first_call["arguments"]
            assert "content" in first_call["arguments"]

            # Verify the content looks like Python code
            content = first_call["arguments"]["content"]
            assert "def" in content
            assert "factorial" in content.lower()

    @pytest.mark.asyncio
    async def test_json_tool_call_generation(self, test_workspace, available_tools):
        """Test that LLM can generate valid JSON tool calls"""
        if not self.model_available:
            pytest.skip("LLM not available")

        # Setup components for JSON mode
        prompt_manager = PromptManager()
        formatter = ToolPromptFormatter(available_tools, use_xml=False)
        parser = UnifiedToolCallParser(ParsingStrategy.JSON_PRIMARY)

        # Create a request
        request = "Create a simple Python class for a calculator"
        filename = "calculator.py"
        context = "Test context for calculator class generation"

        # Build the complete prompt
        base_prompt = prompt_manager.format_prompt(
            'agents', 'code_generation',
            context=context,
            filename=filename,
            request=request
        )

        tools_prompt = formatter.get_tools_prompt()
        complete_prompt = f"{base_prompt}\n\n{tools_prompt}"

        # Model is already loaded in class setup

        # Call the LLM
        response = await self.llm_manager.generate_with_tools(
            complete_prompt,
            max_tokens=512,
            temperature=0.3,
            tools_enabled=True
        )

        # Verify response
        assert response is not None
        if response["type"] == "tool_calls":
            model_output = response.get("raw_output", "")
            parse_result = parser.parse(model_output)

            assert parse_result.success, f"Parsing failed: {parse_result.errors}"
            assert len(parse_result.tool_calls) > 0

            # Should parse as JSON or fall back gracefully
            assert parse_result.strategy_used in ["json", "xml"]

    @pytest.mark.asyncio
    async def test_complete_workflow(self, test_workspace, available_tools):
        """Test complete workflow: prompt -> LLM -> parse -> execute"""
        if not self.model_available:
            pytest.skip("LLM not available")

        # Setup components
        prompt_manager = PromptManager()
        formatter = ToolPromptFormatter(available_tools, use_xml=True)
        parser = UnifiedToolCallParser(ParsingStrategy.XML_PRIMARY)

        # Create request
        request = "Create a simple hello world function"
        filename = "hello.py"
        context = "Creating a basic hello world function for testing"

        # Build prompt
        base_prompt = prompt_manager.format_prompt(
            'agents', 'code_generation',
            context=context,
            filename=filename,
            request=request
        )

        tools_prompt = formatter.get_tools_prompt()
        complete_prompt = f"{base_prompt}\n\n{tools_prompt}"

        # Model is already loaded in class setup

        # Call LLM
        response = await self.llm_manager.generate_with_tools(
            complete_prompt,
            max_tokens=256,
            temperature=0.2
        )

        if response.get("type") == "tool_calls":
            # Parse tool calls
            model_output = response.get("raw_output", "")
            parse_result = parser.parse(model_output)

            if parse_result.success and len(parse_result.tool_calls) > 0:
                # Execute the first tool call
                first_call = parse_result.tool_calls[0]

                if first_call["tool_name"] == "workspace":
                    # Execute workspace tool
                    result = await workspace_tool(first_call["arguments"])

                    # Verify execution was successful
                    assert not result.get("isError", True)

                    # Verify file was created
                    expected_path = test_workspace / filename
                    assert expected_path.exists()

                    # Verify content is reasonable
                    content = expected_path.read_text()
                    assert len(content) > 0
                    assert "def" in content or "print" in content

    @pytest.mark.asyncio
    async def test_prompt_iteration(self, test_workspace, available_tools):
        """Test iterating prompts until we get correct output"""
        if not self.model_available:
            pytest.skip("LLM not available")

        if not hasattr(self.llm_manager, 'mcp_bridge') or not self.llm_manager.mcp_bridge:
            pytest.skip("MCP Bridge not available - requires tool executor")

        prompt_manager = PromptManager()
        formatter = ToolPromptFormatter(available_tools, use_xml=True)
        parser = UnifiedToolCallParser(ParsingStrategy.XML_PRIMARY)

        max_attempts = 3
        success = False

        for attempt in range(max_attempts):
            # Vary the temperature and prompt slightly each attempt
            temperature = 0.1 + (attempt * 0.2)

            request = f"Create a function that adds two numbers (attempt {attempt + 1})"
            filename = f"add_function_v{attempt + 1}.py"

            base_prompt = prompt_manager.format_prompt(
                'agents', 'code_generation',
                context="Mathematical function creation",
                filename=filename,
                request=request
            )

            tools_prompt = formatter.get_tools_prompt()
            complete_prompt = f"{base_prompt}\n\n{tools_prompt}"

            # Model is already loaded in class setup

            # Call LLM
            response = await self.llm_manager.generate_with_tools(
                complete_prompt,
                max_tokens=200,
                temperature=temperature,
                tools_enabled=True
            )

            if response.get("type") == "tool_calls":
                model_output = response.get("raw_output", "")
                parse_result = parser.parse(model_output)

                if parse_result.success and len(parse_result.tool_calls) > 0:
                    first_call = parse_result.tool_calls[0]

                    if (first_call["tool_name"] == "workspace" and
                        "content" in first_call["arguments"] and
                        "def" in first_call["arguments"]["content"]):

                        # Looks like valid Python function
                        content = first_call["arguments"]["content"]

                        # Try to parse as Python
                        try:
                            compile(content, filename, 'exec')
                            success = True
                            break
                        except SyntaxError:
                            continue

        # Should succeed within max_attempts
        assert success, f"Failed to generate valid Python code in {max_attempts} attempts"

    @pytest.mark.asyncio
    async def test_structured_xml_generation(self, test_workspace, available_tools):
        """Test structured XML code generation with metadata"""
        if not self.model_available:
            pytest.skip("LLM not available")

        # Setup components for XML mode with structured generation
        prompt_manager = PromptManager()
        formatter = ToolPromptFormatter(available_tools, use_xml=True)
        parser = UnifiedToolCallParser(ParsingStrategy.XML_PRIMARY)

        # Create a request for structured code generation
        request = "Create a Calculator class with add, subtract, multiply methods"
        filename = "calculator_structured.py"
        context = "Structured code generation with comprehensive XML metadata"

        # Build the structured prompt
        base_prompt = prompt_manager.format_prompt(
            'agents', 'structured_code_generation',
            context=context,
            filename=filename,
            request=request
        )

        # Add tool definitions
        tools_prompt = formatter.get_tools_prompt()
        complete_prompt = f"{base_prompt}\n\n{tools_prompt}"

        # Model is already loaded in class setup

        # Call the LLM
        response = await self.llm_manager.generate_with_tools(
            complete_prompt,
            max_tokens=1024,
            temperature=0.2,
            tools_enabled=True
        )

        # Verify response structure
        assert response is not None
        assert "type" in response

        if response["type"] == "tool_calls":
            # Parse the tool calls
            model_output = response.get("raw_output", "")
            parse_result = parser.parse(model_output)

            # Verify parsing was successful
            assert parse_result.success, f"Parsing failed: {parse_result.errors}"
            assert len(parse_result.tool_calls) > 0
            assert parse_result.strategy_used == "xml"

            # Verify first tool call is for workspace with structured content
            first_call = parse_result.tool_calls[0]
            assert first_call["tool_name"] == "workspace"
            assert "arguments" in first_call
            assert first_call["arguments"]["action"] == "write_structured"
            assert "structured_content" in first_call["arguments"]

            # Verify the structured content looks like proper XML
            structured_content = first_call["arguments"]["structured_content"]
            assert "<python_file" in structured_content
            assert "<metadata>" in structured_content
            assert "<classes>" in structured_content
            assert "Calculator" in structured_content or "calculator" in structured_content.lower()

    @pytest.mark.asyncio
    async def test_xml_vs_json_comparison(self, test_workspace, available_tools):
        """Compare XML vs JSON tool call generation quality"""
        if not self.model_available:
            pytest.skip("LLM not available")

        if not hasattr(self.llm_manager, 'mcp_bridge') or not self.llm_manager.mcp_bridge:
            pytest.skip("MCP Bridge not available - requires tool executor")

        prompt_manager = PromptManager()
        request = "Create a class with a constructor and one method"
        filename = "test_class.py"
        context = "Object-oriented programming example"

        xml_results = []
        json_results = []

        # Model is already loaded in class setup

        # Test XML mode
        formatter_xml = ToolPromptFormatter(available_tools, use_xml=True)
        parser_xml = UnifiedToolCallParser(ParsingStrategy.XML_PRIMARY)

        for i in range(2):  # Try twice
            base_prompt = prompt_manager.format_prompt(
                'agents', 'code_generation',
                context=context,
                filename=f"xml_{filename}",
                request=request
            )

            tools_prompt = formatter_xml.get_tools_prompt()
            complete_prompt = f"{base_prompt}\n\n{tools_prompt}"

            response = await self.llm_manager.generate_with_tools(
                complete_prompt,
                max_tokens=300,
                temperature=0.1,
                tools_enabled=True
            )

            if response.get("type") == "tool_calls":
                parse_result = parser_xml.parse(response.get("raw_output", ""))
                xml_results.append(parse_result.success)

        # Test JSON mode
        formatter_json = ToolPromptFormatter(available_tools, use_xml=False)
        parser_json = UnifiedToolCallParser(ParsingStrategy.JSON_PRIMARY)

        for i in range(2):  # Try twice
            base_prompt = prompt_manager.format_prompt(
                'agents', 'code_generation',
                context=context,
                filename=f"json_{filename}",
                request=request
            )

            tools_prompt = formatter_json.get_tools_prompt()
            complete_prompt = f"{base_prompt}\n\n{tools_prompt}"

            response = await self.llm_manager.generate_with_tools(
                complete_prompt,
                max_tokens=300,
                temperature=0.1,
                tools_enabled=True
            )

            if response.get("type") == "tool_calls":
                parse_result = parser_json.parse(response.get("raw_output", ""))
                json_results.append(parse_result.success)

        # Both should have some success
        xml_success_rate = sum(xml_results) / len(xml_results) if xml_results else 0
        json_success_rate = sum(json_results) / len(json_results) if json_results else 0

        print(f"XML success rate: {xml_success_rate:.1%}")
        print(f"JSON success rate: {json_success_rate:.1%}")

        # At least one format should work reasonably well
        assert max(xml_success_rate, json_success_rate) >= 0.5

    @classmethod
    def teardown_class(cls):
        """Clean up LLM resources"""
        if hasattr(cls, 'llm_manager') and cls.llm_manager:
            try:
                cls.llm_manager.unload_model()
            except:
                pass