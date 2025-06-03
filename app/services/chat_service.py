from typing import Dict, Optional, Any
import os
import re
from langchain_ollama.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.base import BaseLanguageModel

from app.configs.config import APIResponse
from app.logger import logger
from app.config import settings

class ChatService:
    def __init__(self):
        self.models: Dict[str, BaseLanguageModel] = {}
        self.model_mapping = {
            "ollama_qwen": "qwen3:8b",
            "gemini_2o_flash": "gemini-2.0-flash"
        }

    async def initialize(self):
        """Initialize models on startup"""
        logger.info("Initializing chat service...")
        
        # Validate required environment variables
        if not settings.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY not found in environment variables")
        
        # Pre-initialize models that don't require API keys
        try:
            self.models["ollama_qwen"] = ChatOllama(
                model=self.model_mapping["ollama_qwen"]
            )
            logger.info("Ollama model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama model: {str(e)}")

        logger.info("Chat service initialization complete")

    async def cleanup(self):
        """Cleanup resources on shutdown"""
        logger.info("Cleaning up chat service...")
        self.models.clear()

    def _get_or_create_model(self, model_name: str) -> BaseLanguageModel:
        """Get cached model or create new one"""
        if model_name not in self.model_mapping:
            raise ValueError(f"Invalid model name. Must be one of: {list(self.model_mapping.keys())}")
        
        actual_model_name = self.model_mapping[model_name]
        
        # Return cached model if available
        if model_name in self.models:
            return self.models[model_name]
        
        # Create new model
        if 'gemini' in actual_model_name:
            if not settings.GOOGLE_API_KEY:
                raise ValueError("Google API key not configured")
            
            self.models[model_name] = ChatGoogleGenerativeAI(
                model=actual_model_name,
                google_api_key=settings.GOOGLE_API_KEY,
                timeout=30
            )
            logger.info(f"Created new Gemini model: {actual_model_name}")
        else:
            self.models[model_name] = ChatOllama(
                model=actual_model_name
            )
            logger.info(f"Created new Ollama model: {actual_model_name}")
        
        return self.models[model_name]

    def _extract_final_answer(self, output: str) -> Dict[str, Optional[str]]:
        """Extract reasoning and answer from model output"""
        if not output:
            return {'reasoning': None, 'answer': ''}
        
        # Look for thinking tags
        reasoning_match = re.search(r'<think>(.*?)</think>', output, flags=re.DOTALL)
        
        # Remove thinking tags from answer
        answer = re.sub(r'<think>.*?</think>', '', output, flags=re.DOTALL).strip()
        
        return {
            'reasoning': reasoning_match.group(1).strip() if reasoning_match else None,
            'answer': answer if answer else output  # Fallback to original output
        }

    async def get_ai_response(self, model_name: str, user_prompt: str) -> APIResponse:
        """Get AI response with proper error handling"""
        api_response = APIResponse()
        
        try:
            model = self._get_or_create_model(model_name)
            
            logger.info(f"Invoking model {model_name} with prompt length: {len(user_prompt)}")
            
            # Invoke the model
            response = model.invoke(user_prompt)
            
            # Log the raw response for debugging (truncated)
            content_preview = response.content[:200] + "..." if len(response.content) > 200 else response.content
            logger.debug(f"Model response preview: {content_preview}")
            
            # Extract the final answer
            extracted = self._extract_final_answer(response.content)
            api_response.data = {
                "answer": extracted['answer'],
                "model_used": model_name,
                "has_reasoning": extracted['reasoning'] is not None
            }
            
            # Optionally include reasoning in response for debugging
            if extracted['reasoning'] and settings.INCLUDE_REASONING:
                api_response.data["reasoning"] = extracted['reasoning']
            
            api_response.msg = "Response generated successfully"
            return api_response
            
        except ValueError as e:
            logger.warning(f"Validation error in get_ai_response: {str(e)}")
            api_response.code = -1
            api_response.data = None
            api_response.msg = str(e)
            return api_response
            
        except Exception as e:
            logger.error(f"Error in get_ai_response: {str(e)}")
            api_response.code = -1
            api_response.data = None
            api_response.msg = "Failed to generate AI response"
            return api_response