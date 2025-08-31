# File: ~/Projects/local-llm-mcp/core/llm_manager.py
"""
LLM Manager

Responsibilities:
- Model loading and initialization with CUDA optimization
- Inference management and response generation
- Token usage tracking and performance metrics
- Model health monitoring and error handling
- Streaming response support
"""

import logging
import time
from typing import Dict, Any, Optional, Iterator, Tuple
from pathlib import Path

from llama_cpp import Llama
from core.config import ModelConfig
from schemas.agent_schemas import AgentResponse, ResponseStatus, create_success_response, create_error_response

logger = logging.getLogger(__name__)

class LLMManager:
    """
    Manages the local LLM with optimized settings for RTX 1080ti + CUDA 12.9
    
    Handles model loading, inference, and performance monitoring while providing
    a clean interface for agent interactions.
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.llm: Optional[Llama] = None
        self.model_loaded = False
        self.total_tokens_generated = 0
        self.total_inference_time = 0.0
        self.inference_count = 0
        
        # Performance tracking
        self.avg_tokens_per_second = 0.0
        self.last_inference_time = 0.0
        
    def load_model(self) -> Tuple[bool, Optional[str]]:
        """
        Load the model with optimized settings for RTX 1080ti + CUDA 12.9
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            if not Path(self.config.model_path).exists():
                error_msg = f"Model file not found: {self.config.model_path}"
                logger.error(error_msg)
                return False, error_msg
            
            logger.info(f"Loading model: {self.config.model_path}")
            logger.info("CUDA 12.9 optimization enabled")
            logger.info(f"GPU layers: {self.config.n_gpu_layers}")
            logger.info(f"Context size: {self.config.n_ctx}")
            logger.info(f"Batch size: {self.config.n_batch}")
            
            start_time = time.time()
            
            self.llm = Llama(
                model_path=self.config.model_path,
                n_gpu_layers=self.config.n_gpu_layers,
                n_ctx=self.config.n_ctx,
                n_batch=self.config.n_batch,
                n_threads=self.config.n_threads,
                use_mmap=self.config.use_mmap,
                use_mlock=self.config.use_mlock,
                verbose=self.config.verbose,
                
                # CUDA 12.9 + RTX 1080ti optimizations
                f16_kv=self.config.f16_kv,
                logits_all=self.config.logits_all,
                tensor_split=self.config.tensor_split,
                main_gpu=self.config.main_gpu,
            )
            
            load_time = time.time() - start_time
            self.model_loaded = True
            
            logger.info(f"Model loaded successfully in {load_time:.2f} seconds!")
            
            # Test generation to ensure everything works
            test_success = self._test_generation()
            if not test_success:
                return False, "Model loaded but test generation failed"
            
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to load model: {str(e)}"
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
                echo=False
            )
            
            if response and response["choices"]:
                test_text = response["choices"][0]["text"]
                logger.info(f"Model test successful: '{test_text.strip()}'")
                return True
            else:
                logger.error("Model test failed: No response generated")
                return False
                
        except Exception as e:
            logger.error(f"Model test failed: {e}")
            return False
    
    def generate_response(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        stop_sequences: Optional[list] = None
    ) -> Tuple[AgentResponse, Dict[str, Any]]:
        """
        Generate response from the model with performance tracking
        
        Args:
            prompt: Input prompt for generation
            temperature: Sampling temperature (overrides config default)
            max_tokens: Maximum tokens to generate (overrides config default)
            top_p: Nucleus sampling parameter
            repeat_penalty: Repetition penalty
            stop_sequences: Stop sequences for generation
            
        Returns:
            Tuple of (AgentResponse, performance_metrics)
        """
        if not self.model_loaded:
            error_response = create_error_response("Model not loaded")
            return error_response, {"error": "model_not_loaded"}
        
        # Use config defaults if not specified
        temperature = temperature or self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens
        top_p = top_p or self.config.top_p
        repeat_penalty = repeat_penalty or self.config.repeat_penalty
        stop_sequences = stop_sequences or ["</s>", "<|im_end|>", "<|endoftext|>"]
        
        try:
            start_time = time.time()
            
            response = self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                repeat_penalty=repeat_penalty,
                stop=stop_sequences,
                echo=False
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            if not response or not response.get("choices"):
                error_response = create_error_response("No response generated from model")
                return error_response, {"error": "no_response"}
            
            response_text = response["choices"][0]["text"].strip()  # Fixed variable name
            tokens_used = response["usage"]["total_tokens"] if "usage" in response else None
            
            # Update performance tracking
            self.inference_count += 1
            self.total_inference_time += processing_time
            if tokens_used:
                self.total_tokens_generated += tokens_used
                self.avg_tokens_per_second = tokens_used / processing_time if processing_time > 0 else 0
            
            self.last_inference_time = processing_time
            
            # Parse agent response from LLM output
            agent_response = self._parse_agent_response(response_text)
            
            # Update tokens and timing
            agent_response.tokens_used = tokens_used
            agent_response.processing_time = processing_time
            
            # Performance metrics
            performance_metrics = {
                "tokens_generated": tokens_used or 0,
                "processing_time": processing_time,
                "tokens_per_second": self.avg_tokens_per_second,
                "inference_count": self.inference_count,
                "model_efficiency": "high" if self.avg_tokens_per_second > 10 else "moderate"
            }
            
            return agent_response, performance_metrics
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            error_response = create_error_response(f"Generation failed: {str(e)}")
            return error_response, {"error": str(e)}
    
    def _parse_agent_response(self, response_text: str) -> AgentResponse:
        """
        Parse agent response from LLM output, extracting JSON when possible
        
        Args:
            response_text: Raw text output from LLM
            
        Returns:
            AgentResponse object
        """
        try:
            import json
            import re
            
            # Try to extract JSON from response
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            json_matches = re.findall(json_pattern, response_text, re.DOTALL)
            
            if json_matches:
                # Try to parse the last (most complete) JSON match
                for json_str in reversed(json_matches):
                    try:
                        response_data = json.loads(json_str)
                        
                        # Validate required fields
                        if "status" in response_data and "message" in response_data:
                            # Create FileContent if file_content is present
                            file_content = None
                            if "file_content" in response_data and response_data["file_content"]:
                                from schemas.agent_schemas import FileContent
                                fc_data = response_data["file_content"]
                                if isinstance(fc_data, dict) and "filename" in fc_data and "content" in fc_data:
                                    file_content = FileContent(
                                        filename=fc_data["filename"],
                                        content=fc_data["content"],
                                        language=fc_data.get("language"),
                                        line_count=len(fc_data["content"].split('\n')) if fc_data["content"] else 0
                                    )
                            
                            # Create AgentResponse
                            agent_response = AgentResponse(
                                status=ResponseStatus(response_data["status"]),
                                message=response_data["message"],
                                file_content=file_content,
                                changes_made=response_data.get("changes_made", []),
                                warnings=response_data.get("warnings", [])
                            )
                            
                            return agent_response
                            
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.debug(f"Failed to parse JSON: {e}")
                        continue
            
            # Fallback: Create response from raw text
            logger.warning("Could not parse JSON response, creating text-based response")
            
            # Determine status from text content
            status = ResponseStatus.SUCCESS
            if any(word in response_text.lower() for word in ["error", "failed", "cannot", "unable"]):
                status = ResponseStatus.ERROR
            elif any(word in response_text.lower() for word in ["warning", "caution", "note"]):
                status = ResponseStatus.WARNING
            
            return create_success_response(
                message=response_text[:500] + "..." if len(response_text) > 500 else response_text
            )
            
        except Exception as e:
            logger.error(f"Failed to parse agent response: {e}")
            return create_error_response(f"Response parsing failed: {str(e)}")
    
    async def generate_streaming_response(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[list] = None
    ):
        """
        Generate streaming response from the model
        
        Args:
            prompt: Input prompt for generation
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop_sequences: Stop sequences for generation
            
        Yields:
            Dictionary with streaming data
        """
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
                echo=False
            )
            
            for output in stream:
                if "choices" in output and output["choices"]:
                    chunk_text = output["choices"][0].get("text", "")
                    if chunk_text:
                        accumulated_text += chunk_text
                        tokens_generated += 1
                        
                        yield {
                            "type": "chunk",
                            "content": chunk_text,
                            "accumulated": accumulated_text,
                            "tokens_so_far": tokens_generated
                        }
            
            # Final response
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Parse final response
            agent_response = self._parse_agent_response(accumulated_text)
            agent_response.tokens_used = tokens_generated
            agent_response.processing_time = processing_time
            
            # Update performance tracking
            self.inference_count += 1
            self.total_inference_time += processing_time
            self.total_tokens_generated += tokens_generated
            if processing_time > 0:
                self.avg_tokens_per_second = tokens_generated / processing_time
            
            metrics = {
                "tokens_generated": tokens_generated,
                "processing_time": processing_time,
                "tokens_per_second": self.avg_tokens_per_second
            }
            
            yield {
                "type": "complete",
                "response": agent_response,
                "metrics": metrics
            }
            
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            yield {"type": "error", "message": f"Streaming failed: {str(e)}"}
    
    def get_model_info(self) -> Dict[str, Any]:
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
                "max_tokens": self.config.max_tokens
            },
            "performance": {
                "total_inferences": self.inference_count,
                "total_tokens": self.total_tokens_generated,
                "avg_tokens_per_second": round(self.avg_tokens_per_second, 2),
                "total_inference_time": round(self.total_inference_time, 2)
            }
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        return {
            "total_inferences": self.inference_count,
            "total_tokens": self.total_tokens_generated,
            "avg_tokens_per_second": round(self.avg_tokens_per_second, 2),
            "total_inference_time": round(self.total_inference_time, 2),
            "last_inference_time": round(self.last_inference_time, 2),
            "efficiency": "high" if self.avg_tokens_per_second > 15 else 
                         "moderate" if self.avg_tokens_per_second > 8 else "low"
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the model"""
        if not self.model_loaded:
            return {
                "status": "unhealthy",
                "message": "Model not loaded",
                "avg_performance": 0
            }
        
        try:
            # Quick test generation
            test_start = time.time()
            test_response = self.llm("Hello", max_tokens=1, temperature=0.1)
            test_time = time.time() - test_start
            
            if test_response and test_response.get("choices"):
                return {
                    "status": "healthy",
                    "message": "Model responding normally",
                    "avg_performance": round(self.avg_tokens_per_second, 2),
                    "last_test_time": round(test_time, 3)
                }
            else:
                return {
                    "status": "degraded",
                    "message": "Model loaded but not responding properly",
                    "avg_performance": round(self.avg_tokens_per_second, 2)
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Health check failed: {str(e)}",
                "avg_performance": round(self.avg_tokens_per_second, 2)
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