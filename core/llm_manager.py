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
            
            response_