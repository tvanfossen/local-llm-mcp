# File: ~/Projects/local-llm-mcp/core/llm_manager.py
"""LLM Manager

Responsibilities:
- Model loading and initialization with CUDA optimization
- Inference management and response generation
- Token usage tracking and performance metrics
- Model health monitoring and error handling
- Streaming response support
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llama_cpp import Llama

from core.config import ModelConfig
from schemas.agent_schemas import (
    AgentResponse,
    ResponseStatus,
    create_error_response,
    create_success_response,
)

logger = logging.getLogger(__name__)


@dataclass
class GenerationParams:
    """Parameters for response generation"""

    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    repeat_penalty: float | None = None
    stop_sequences: list | None = None


class LLMManager:
    """Manages the local LLM with optimized settings for RTX 1080ti + CUDA 12.9

    Handles model loading, inference, and performance monitoring while providing
    a clean interface for agent interactions.
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self.llm: Llama | None = None
        self.model_loaded = False
        self.total_tokens_generated = 0
        self.total_inference_time = 0.0
        self.inference_count = 0

        # Performance tracking
        self.avg_tokens_per_second = 0.0
        self.last_inference_time = 0.0

    def load_model(self) -> tuple[bool, str | None]:
        """Load the model with optimized settings for RTX 1080ti + CUDA 12.9"""
        model_path = Path(self.config.model_path)
        if not model_path.exists():
            error_msg = f"Model file not found: {self.config.model_path}"
            logger.error(error_msg)
            return False, error_msg

        # Log initialization info
        self._log_model_loading_info()

        start_time = time.time()

        try:
            # Initialize the model
            self.llm = Llama(
                model_path=self.config.model_path,
                n_gpu_layers=self.config.n_gpu_layers,
                n_ctx=self.config.n_ctx,
                n_batch=self.config.n_batch,
                n_threads=self.config.n_threads,
                use_mmap=self.config.use_mmap,
                use_mlock=self.config.use_mlock,
                verbose=self.config.verbose,
                f16_kv=self.config.f16_kv,
                logits_all=self.config.logits_all,
                tensor_split=self.config.tensor_split,
                main_gpu=self.config.main_gpu,
            )

            load_time = time.time() - start_time
            self.model_loaded = True
            logger.info(f"Model loaded successfully in {load_time:.2f} seconds!")

            # Test generation and return result
            return self._validate_model_loading()

        except Exception as e:
            error_msg = f"Failed to load model: {e!s}"
            logger.error(error_msg)
            return False, error_msg

    def _test_generation(self) -> bool:
        """Test model generation to ensure it's working properly"""
        try:
            test_prompt = "Hello"
            response = self.llm(
                test_prompt,
                max_tokens=5,
                temperature=0.1,
                echo=False,
            )

            if response and response["choices"]:
                test_text = response["choices"][0]["text"]
                logger.info(f"Model test successful: '{test_text.strip()}'")
                return True
            logger.error("Model test failed: No response generated")
            return False

        except Exception as e:
            logger.error(f"Model test failed: {e}")
            return False

    def generate_response(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        repeat_penalty: float | None = None,
    ) -> tuple[AgentResponse, dict[str, Any]]:
        """Generate response from the model with performance tracking"""
        if not self.model_loaded:
            error_response = create_error_response("Model not loaded")
            return error_response, {"error": "model_not_loaded"}

        # Use config defaults if not specified
        params = self._prepare_generation_params(temperature, max_tokens, top_p, repeat_penalty)

        try:
            start_time = time.time()

            response = self.llm(
                prompt,
                max_tokens=params["max_tokens"],
                temperature=params["temperature"],
                top_p=params["top_p"],
                repeat_penalty=params["repeat_penalty"],
                stop=params["stop_sequences"],
                echo=False,
            )

            processing_time = time.time() - start_time

            # Process response
            return self._process_llm_response(response, processing_time)

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            error_response = create_error_response(f"Generation failed: {e!s}")
            return error_response, {"error": str(e)}

    def _parse_agent_response(self, response_text: str) -> AgentResponse:
        """Parse agent response - Handle unescaped quotes in JSON strings"""
        try:
            logger.info(f"Attempting to parse response: {response_text[:200]!r}")

            # Clean the response - find JSON boundaries
            cleaned_text = response_text.strip()

            # Find first { and last }
            first_brace = cleaned_text.find("{")
            last_brace = cleaned_text.rfind("}")

            if first_brace >= 0 and last_brace > first_brace:
                json_text = cleaned_text[first_brace : last_brace + 1]

                # Try parsing with progressive fixes
                return self._try_parse_json_response(json_text)
            else:
                logger.error("No JSON boundaries found")
                return self._create_fallback_response(response_text)

        except Exception as e:
            logger.warning(f"JSON parsing completely failed: {e}, falling back to text analysis")
            return create_success_response(
                message=response_text[:300] + "..." if len(response_text) > 300 else response_text,
            )

    def _try_parse_json_response(self, json_text: str) -> AgentResponse:
        """Try parsing JSON with progressive fixes"""
        # First, try parsing as-is
        try:
            import json

            response_data = json.loads(json_text)
            logger.info("✅ JSON parsing succeeded without fixes")
            return self._create_response_from_json(response_data)
        except json.JSONDecodeError:
            pass

        # Try with quote fixing
        try:
            import json

            fixed_json_text = self._fix_unescaped_quotes(json_text)
            response_data = json.loads(fixed_json_text)
            logger.info("✅ JSON parsing succeeded after quote fixing")
            return self._create_response_from_json(response_data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed even after quote fixing: {e}")
            logger.error(f"Fixed JSON text was: {fixed_json_text[:500]!r}")

        # Manual extraction as last resort
        return self._manual_extract_response(json_text)

    def _fix_unescaped_quotes(self, text: str) -> str:
        """Fix unescaped quotes inside JSON string values"""
        import re

        def fix_string_value(match):
            key_part = match.group(1)  # "key": "
            content = match.group(2)  # the string content
            end_quote = match.group(3)  # the closing "

            # Escape any unescaped quotes in the content
            fixed_content = content.replace('"""', '\\"\\"\\"')
            fixed_content = fixed_content.replace('""', '\\"\\""')

            return key_part + fixed_content + end_quote

        # Match string values in JSON (handling multiline)
        pattern = r'("[\w_]+"\s*:\s*")((?:[^"\\]|\\.)*?)("(?:\s*[,}]))'
        result = re.sub(pattern, fix_string_value, text, flags=re.DOTALL | re.MULTILINE)
        return result

    def _create_response_from_json(self, response_data: dict) -> AgentResponse:
        """Create AgentResponse from parsed JSON data"""
        # Create FileContent from full_file_content field
        file_content = None
        if response_data.get("full_file_content"):
            from schemas.agent_schemas import FileContent

            content = response_data["full_file_content"]
            file_content = FileContent(
                filename="temp_filename",  # Will be set by the endpoint
                content=content,
                language="python",  # Will be inferred
                line_count=len(content.split("\n")) if content else 0,
            )

        return AgentResponse(
            status=ResponseStatus(response_data.get("status", "success")),
            message=response_data.get("message", "Task completed"),
            file_content=file_content,
            changes_made=(
                [response_data.get("changes_summary", "")]
                if response_data.get("changes_summary")
                else []
            ),
            warnings=([response_data.get("warnings", "")] if response_data.get("warnings") else []),
        )

    def _create_fallback_response(self, response_text: str) -> AgentResponse:
        """Create fallback response when no JSON found"""
        return create_success_response(
            message=response_text[:300] + "..." if len(response_text) > 300 else response_text,
        )

    def _manual_extract_response(self, json_text: str) -> AgentResponse:
        """Manually extract response when JSON parsing fails"""
        try:
            import re

            logger.info("Attempting manual extraction")

            # Extract key fields manually using regex
            status_match = re.search(r'"status"\s*:\s*"([^"]*)"', json_text)
            message_match = re.search(r'"message"\s*:\s*"([^"]*)"', json_text)

            # For file content, extract everything between the quotes (more complex)
            content_match = re.search(
                r'"full_file_content"\s*:\s*"(.*?)"(?=\s*,\s*"|\s*})', json_text, re.DOTALL
            )

            status = status_match.group(1) if status_match else "success"
            message = message_match.group(1) if message_match else "Manual extraction"

            file_content = None
            if content_match:
                # Unescape the content
                content = content_match.group(1)
                content = content.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")

                from schemas.agent_schemas import FileContent

                file_content = FileContent(
                    filename="temp_filename",
                    content=content,
                    language="python",
                    line_count=len(content.split("\n")),
                )

            logger.info("✅ Manual extraction succeeded")

            return AgentResponse(
                status=ResponseStatus(status),
                message=message,
                file_content=file_content,
                changes_made=["Manual extraction applied"],
                warnings=["Used manual extraction due to JSON parsing issues"],
            )

        except Exception as e:
            logger.error(f"Manual extraction also failed: {e}")

    async def generate_streaming_response(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop_sequences: list | None = None,
    ):
        """Generate streaming response from the model"""
        if not self.model_loaded:
            yield {"type": "error", "message": "Model not loaded"}
            return

        # Use config defaults if not specified
        temperature = temperature or self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens
        stop_sequences = stop_sequences or ["</s>", "<|im_end|>", "<|endoftext|>"]

        try:
            start_time = time.time()
            accumulated_text = ""
            tokens_generated = 0

            # Create streaming generator
            stream = self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop_sequences,
                stream=True,
                echo=False,
            )

            for output in stream:
                if output.get("choices"):
                    chunk_text = output["choices"][0].get("text", "")
                    if chunk_text:
                        accumulated_text += chunk_text
                        tokens_generated += 1

                        yield {
                            "type": "chunk",
                            "content": chunk_text,
                            "accumulated": accumulated_text,
                            "tokens_so_far": tokens_generated,
                        }

            # Final response
            end_time = time.time()
            processing_time = end_time - start_time

            # Parse final response
            agent_response = self._parse_agent_response(accumulated_text)
            agent_response.tokens_used = tokens_generated
            agent_response.processing_time = processing_time

            # Update performance tracking
            self._update_performance_metrics(tokens_generated, processing_time)

            metrics = {
                "tokens_generated": tokens_generated,
                "processing_time": processing_time,
                "tokens_per_second": self.avg_tokens_per_second,
            }

            yield {
                "type": "complete",
                "response": agent_response,
                "metrics": metrics,
            }

        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            yield {"type": "error", "message": f"Streaming failed: {e!s}"}

    def get_model_info(self) -> dict[str, Any]:
        """Get model information and configuration"""
        return {
            "model_loaded": self.model_loaded,
            "model_path": self.config.model_path if self.model_loaded else None,
            "configuration": {
                "gpu_layers": self.config.n_gpu_layers,
                "context_size": self.config.n_ctx,
                "batch_size": self.config.n_batch,
                "threads": self.config.n_threads,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            },
            "performance": {
                "total_inferences": self.inference_count,
                "total_tokens": self.total_tokens_generated,
                "avg_tokens_per_second": round(self.avg_tokens_per_second, 2),
                "total_inference_time": round(self.total_inference_time, 2),
            },
        }

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary"""
        return {
            "total_inferences": self.inference_count,
            "total_tokens": self.total_tokens_generated,
            "avg_tokens_per_second": round(self.avg_tokens_per_second, 2),
            "total_inference_time": round(self.total_inference_time, 2),
            "last_inference_time": round(self.last_inference_time, 2),
            "efficiency": (
                "high"
                if self.avg_tokens_per_second > 15
                else "moderate" if self.avg_tokens_per_second > 8 else "low"
            ),
        }

    def health_check(self) -> dict[str, Any]:
        """Perform health check on the model"""
        if not self.model_loaded:
            return {
                "status": "unhealthy",
                "message": "Model not loaded",
                "avg_performance": 0,
            }

        try:
            # Quick test generation
            test_start = time.time()
            test_response = self.llm("Hello", max_tokens=1, temperature=0.1)
            test_time = time.time() - test_start

            # Determine status based on response
            if test_response and test_response.get("choices"):
                status = "healthy"
                message = "Model responding normally"
            else:
                status = "degraded"
                message = "Model loaded but not responding properly"

            return {
                "status": status,
                "message": message,
                "avg_performance": round(self.avg_tokens_per_second, 2),
                "last_test_time": round(test_time, 3) if status == "healthy" else None,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Health check failed: {e!s}",
                "avg_performance": round(self.avg_tokens_per_second, 2),
            }

    def unload_model(self):
        """Unload the model and free GPU memory"""
        if self.llm:
            try:
                # llama-cpp-python doesn't have explicit unload, but we can delete the reference
                del self.llm
                self.llm = None
                self.model_loaded = False
                logger.info("Model unloaded successfully")
            except Exception as e:
                logger.error(f"Error unloading model: {e}")
        else:
            logger.info("No model to unload")

    def _log_model_loading_info(self):
        """Log model loading information"""
        logger.info(f"Loading model: {self.config.model_path}")
        logger.info("CUDA 12.9 optimization enabled")
        logger.info(f"GPU layers: {self.config.n_gpu_layers}")
        logger.info(f"Context size: {self.config.n_ctx}")
        logger.info(f"Batch size: {self.config.n_batch}")

    def _validate_model_loading(self) -> tuple[bool, str | None]:
        """Test generation to ensure model is working properly"""
        test_success = self._test_generation()
        return (True, None) if test_success else (False, "Model loaded but test generation failed")

    def _prepare_generation_params(self, temperature, max_tokens, top_p, repeat_penalty) -> dict:
        """Prepare generation parameters with defaults"""
        return {
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "top_p": top_p or self.config.top_p,
            "repeat_penalty": repeat_penalty or self.config.repeat_penalty,
            "stop_sequences": ["</s>", "<|im_end|>", "<|endoftext|>"],
        }

    def _process_llm_response(
        self, response, processing_time
    ) -> tuple[AgentResponse, dict[str, Any]]:
        """Process the LLM response and update metrics"""
        if not response or not response.get("choices"):
            error_response = create_error_response("No response generated from model")
            return error_response, {"error": "no_response"}

        response_text = response["choices"][0]["text"].strip()
        logger.info(f"🔍 RAW MODEL OUTPUT: {response_text!r}")
        tokens_used = response["usage"]["total_tokens"] if "usage" in response else None

        # Update performance tracking
        self._update_performance_metrics(tokens_used, processing_time)

        # Parse agent response from LLM output
        agent_response = self._parse_agent_response(response_text)
        agent_response.tokens_used = tokens_used
        agent_response.processing_time = processing_time

        # Build performance metrics
        performance_metrics = {
            "tokens_generated": tokens_used or 0,
            "processing_time": processing_time,
            "tokens_per_second": self.avg_tokens_per_second,
            "inference_count": self.inference_count,
            "model_efficiency": "high" if self.avg_tokens_per_second > 10 else "moderate",
        }

        return agent_response, performance_metrics

    def _update_performance_metrics(self, tokens_used, processing_time):
        """Update performance tracking metrics"""
        self.inference_count += 1
        self.total_inference_time += processing_time
        if tokens_used:
            self.total_tokens_generated += tokens_used
            self.avg_tokens_per_second = tokens_used / processing_time if processing_time > 0 else 0
        self.last_inference_time = processing_time
