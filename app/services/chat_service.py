from typing import Dict, Optional, Any, List
import os
import re
import json
from langchain_ollama.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages import (
    SystemMessage, 
    HumanMessage, 
    AIMessage, 
    trim_messages,
    RemoveMessage
)

from app.configs.config import APIResponse
from app.logger import logger
from app.config import settings
from app.configs.constants import SYSTEM_PROMPT

class ChatService:
    def __init__(self):
        self.models: Dict[str, BaseLanguageModel] = {}
        self.model_mapping = {
            "ollama_qwen": "qwen3:8b",
            "ollama_llama": "llama3.2:latest",
            "gemini_2o_flash": "gemini-2.0-flash",
            "openai_gpt4": "gpt-4o",
        }
        self.system_prompt = self._get_system_prompt()
        
        # Centralized history management - one history per session, not per model
        self.conversations: Dict[str, List[Any]] = {}  # session_id -> list of messages
        self.max_history_length = getattr(settings, 'MAX_HISTORY_LENGTH', 10)
        self.enable_summarization = getattr(settings, 'ENABLE_SUMMARIZATION', True)
        self.summary_threshold = getattr(settings, 'SUMMARY_THRESHOLD', 10)

    def _get_system_prompt(self) -> str:
        """Define the system prompt for all models"""
        system_prompt = SYSTEM_PROMPT
        return system_prompt
    
    async def initialize(self):
        """Initialize models on startup"""
        logger.info("Initializing chat service...")
        
        # Validate required environment variables
        if not settings.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY not found in environment variables")
        
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
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
        self.conversations.clear()

    def _get_or_create_model(self, model_name: str) -> BaseLanguageModel:
        """Get cached model or create new one"""
        if model_name not in self.model_mapping:
            raise ValueError(f"Invalid model name. Must be one of: {list(self.model_mapping.keys())}")
        
        actual_model_name = self.model_mapping[model_name]
        
        # Return cached model if available
        if model_name in self.models:
            return self.models[model_name]
        
        # Create new model based on provider
        if 'gemini' in actual_model_name:
            if not settings.GOOGLE_API_KEY:
                raise ValueError("Google API key not configured")
            
            self.models[model_name] = ChatGoogleGenerativeAI(
                model=actual_model_name,
                google_api_key=settings.GOOGLE_API_KEY,
                timeout=30
            )
            logger.info(f"Created new Gemini model: {actual_model_name}")
            
        elif 'openai' in model_name or 'gpt' in actual_model_name:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")
            
            # Configure OpenAI model parameters
            openai_config = {
                'model': actual_model_name,
                'api_key': settings.OPENAI_API_KEY,
                'timeout': getattr(settings, 'OPENAI_TIMEOUT', 60),
                'temperature': getattr(settings, 'OPENAI_TEMPERATURE', 0.7),
                'max_tokens': getattr(settings, 'OPENAI_MAX_TOKENS', None),
            }
            
            self.models[model_name] = ChatOpenAI(**openai_config)
            logger.info(f"Created new OpenAI model: {actual_model_name}")
            
        else:  # Ollama models
            self.models[model_name] = ChatOllama(
                model=actual_model_name
            )
            logger.info(f"Created new Ollama model: {actual_model_name}")
        
        return self.models[model_name]

    def _get_session_history(self, session_id: str) -> List[Any]:
        """Get conversation history for a session"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        return self.conversations[session_id]

    def _add_message_to_history(self, session_id: str, message: Any):
        """Add a message to session history"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        self.conversations[session_id].append(message)

    def _prepare_messages_for_model(self, session_id: str, current_message: str) -> List[Any]:
        """Prepare message chain for model, handling history management"""
        history = self._get_session_history(session_id)
        
        logger.debug(f"[{session_id}] Preparing messages. History length: {len(history)}")
        
        # Handle summarization if history is too long
        if self.enable_summarization and len(history) >= self.summary_threshold:
            logger.debug(f"[{session_id}] Triggering summarization (threshold: {self.summary_threshold})")
            return self._handle_summarization_for_session(session_id, current_message)
        
        # Handle trimming if history exceeds max length
        elif len(history) > self.max_history_length:
            logger.debug(f"[{session_id}] Trimming messages (max length: {self.max_history_length})")
            trimmed_history = self._trim_messages(history)
            messages = [SystemMessage(self.system_prompt)] + trimmed_history + [HumanMessage(current_message)]
        else:
            logger.debug(f"[{session_id}] Using full history (no trimming/summarization needed)")
            messages = [SystemMessage(self.system_prompt)] + history + [HumanMessage(current_message)]
        
        return messages

    def _handle_summarization_for_session(self, session_id: str, current_message: str) -> List[Any]:
        """Handle conversation summarization when history gets too long"""
        try:
            history = self._get_session_history(session_id)
            
            # Use the first available model for summarization (or you could make this configurable)
            model_name = list(self.model_mapping.keys())[0]
            model = self._get_or_create_model(model_name)
            
            # Create summary prompt
            summary_prompt = (
                "Distill the above chat messages into a single summary message. "
                "Include as many specific details as you can, especially user preferences, "
                "context, and important information that should be remembered."
            )
            
            # Generate summary
            summary_message = model.invoke(
                history + [HumanMessage(summary_prompt)]
            )
            
            # Replace history with summary
            self.conversations[session_id] = [AIMessage(content=f"[Summary of previous conversation]: {summary_message.content}")]
            
            # Return messages for current request
            return [
                SystemMessage(self.system_prompt + "\n\nThe conversation history includes a summary of the earlier conversation."),
                self.conversations[session_id][0],  # Summary message
                HumanMessage(current_message)
            ]
            
        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}, falling back to trimming")
            # Fallback to trimming
            history = self._get_session_history(session_id)
            trimmed_history = self._trim_messages(history)
            return [SystemMessage(self.system_prompt)] + trimmed_history + [HumanMessage(current_message)]

    def _trim_messages(self, messages: List) -> List:
        """Trim messages to fit within max history length"""
        if len(messages) <= self.max_history_length:
            return messages
        
        # Use LangChain's trim_messages utility
        trimmer = trim_messages(
            strategy="last",
            max_tokens=self.max_history_length,
            token_counter=len  # Count each message as 1 token
        )
        
        return trimmer.invoke(messages)

    def _extract_final_answer(self, output: str) -> Dict[str, Any]:
        """Extract reasoning and answer from model output"""
        if not output:
            return {'reasoning': None, 'answer': ''}
        
        # Look for <think> tags for reasoning (separate from JSON "thought" field)
        reasoning_match = re.search(r'<think>(.*?)</think>', output, flags=re.DOTALL)
        
        # Remove <think> tags from answer but keep everything else including JSON with "thought" field
        answer_text = re.sub(r'<think>.*?</think>', '', output, flags=re.DOTALL).strip()
        
        # Try to parse the answer as JSON
        parsed_answer = self._try_parse_json_answer(answer_text)
        
        return {
            'reasoning': reasoning_match.group(1).strip() if reasoning_match else None,
            'answer': parsed_answer if parsed_answer is not None else (answer_text if answer_text else output)
        }

    def _try_parse_json_answer(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to parse the answer text as JSON, return None if not valid JSON"""
        if not text:
            return None
        
        # Try to extract JSON from markdown code blocks first
        json_match = re.search(r'```json\s*\n(.*?)\n```', text, flags=re.DOTALL)
        if json_match:
            json_text = json_match.group(1).strip()
            try:
                parsed_json = json.loads(json_text)
                
                # Check if there's additional text after the JSON block
                remaining_text = re.sub(r'```json\s*\n.*?\n```', '', text, flags=re.DOTALL).strip()
                
                if remaining_text:
                    # If there's additional text, include it in the response
                    return {
                        "structured_response": parsed_json,
                        "additional_text": remaining_text
                    }
                else:
                    # Return just the JSON if that's all there is
                    return parsed_json
                    
            except json.JSONDecodeError:
                logger.debug("Failed to parse JSON from markdown code block")
        
        # Try to parse the entire text as JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            logger.debug("Text is not valid JSON, returning as string")
            return None

    async def get_ai_response(
        self, 
        model_name: str, 
        user_prompt: str, 
        session_id: str = "default"
    ) -> APIResponse:
        """Get AI response with shared conversation history across models"""
        api_response = APIResponse()
        
        try:
            logger.debug(f"=== AI RESPONSE START ===")
            logger.debug(f"Model: {model_name}, Session: {session_id}")
            logger.debug(f"User prompt: '{user_prompt}'")
            
            # Get the model
            model = self._get_or_create_model(model_name)
            
            # Prepare messages with shared history
            messages = self._prepare_messages_for_model(session_id, user_prompt)
            
            # DEBUG: Log final message chain being sent to model
            logger.debug(f"[{model_name}] Final message chain length: {len(messages)}")
            for i, msg in enumerate(messages):
                msg_type = type(msg).__name__
                content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                logger.debug(f"[{model_name}] Final Message {i}: {msg_type} - '{content_preview}'")
            
            # Invoke model
            logger.debug(f"[{model_name}] Invoking model with {len(messages)} messages")
            response = model.invoke(messages)
            
            # Add user message and AI response to shared history
            self._add_message_to_history(session_id, HumanMessage(user_prompt))
            self._add_message_to_history(session_id, AIMessage(response.content))
            
            # DEBUG: Log model response
            response_preview = response.content[:100] + "..." if len(response.content) > 100 else response.content
            logger.debug(f"[{model_name}] Model response: '{response_preview}'")
            
            # Extract the final answer
            extracted = self._extract_final_answer(response.content)
            
            # Set up the API response data structure
            api_response.code = 0  # Ensure success code is set
            api_response.data = {
                "answer": extracted['answer'],
                "model_used": model_name,
                "session_id": session_id,
                "has_reasoning": extracted['reasoning'] is not None,
                "message_count": len(self._get_session_history(session_id))
            }
            
            # Optionally include reasoning in response for debugging
            if extracted['reasoning'] and hasattr(settings, 'INCLUDE_REASONING') and settings.INCLUDE_REASONING:
                api_response.data["reasoning"] = extracted['reasoning']
            
            logger.debug(f"=== AI RESPONSE END ===")
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

    async def get_conversation_history(self, session_id: str, model_name: str = "") -> APIResponse:
        """Get conversation history for a session"""
        api_response = APIResponse()
        
        try:
            messages = self._get_session_history(session_id)
            
            # Convert messages to serializable format
            history = []
            for msg in messages:
                if isinstance(msg, (HumanMessage, AIMessage)):
                    history.append({
                        "type": "human" if isinstance(msg, HumanMessage) else "ai",
                        "content": msg.content,
                        "timestamp": getattr(msg, 'timestamp', None)
                    })
            
            api_response.code = 0
            api_response.data = {
                "session_id": session_id,
                "messages": history,
                "message_count": len(history)
            }
            api_response.msg = "Conversation history retrieved successfully"
            return api_response
            
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            api_response.code = -1
            api_response.data = None
            api_response.msg = "Failed to retrieve conversation history"
            return api_response

    async def clear_conversation_history(self, session_id: str) -> APIResponse:
        """Clear conversation history for a session"""
        api_response = APIResponse()
        
        try:
            if session_id in self.conversations:
                del self.conversations[session_id]
            
            api_response.code = 0
            api_response.data = {"session_id": session_id}
            api_response.msg = "Conversation history cleared successfully"
            return api_response
            
        except Exception as e:
            logger.error(f"Error clearing conversation history: {str(e)}")
            api_response.code = -1
            api_response.data = None
            api_response.msg = "Failed to clear conversation history"
            return api_response

    def update_system_prompt(self, new_prompt: str):
        """Update system prompt"""
        logger.info("Updating system prompt...")
        self.system_prompt = new_prompt
        logger.info("System prompt updated.")

    def get_current_system_prompt(self) -> str:
        """Get the current system prompt"""
        return self.system_prompt

    def update_history_settings(
        self,
        max_history_length: Optional[int] = None,
        enable_summarization: Optional[bool] = None,
        summary_threshold: Optional[int] = None
    ):
        """Update history management settings"""
        if max_history_length is not None:
            self.max_history_length = max_history_length
        if enable_summarization is not None:
            self.enable_summarization = enable_summarization
        if summary_threshold is not None:
            self.summary_threshold = summary_threshold
        
        logger.info(f"History settings updated: max_length={self.max_history_length}, "
                   f"summarization={self.enable_summarization}, threshold={self.summary_threshold}")

    def update_openai_settings(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ):
        """Update OpenAI-specific settings (requires model recreation)"""
        if temperature is not None:
            settings.OPENAI_TEMPERATURE = temperature
        if max_tokens is not None:
            settings.OPENAI_MAX_TOKENS = max_tokens
        if timeout is not None:
            settings.OPENAI_TIMEOUT = timeout
        
        # Clear cached OpenAI models to force recreation with new settings
        openai_models = [k for k in self.models.keys() if 'openai' in k]
        for model_key in openai_models:
            del self.models[model_key]
        
        logger.info(f"OpenAI settings updated. Affected models will be recreated on next use.")

    def get_available_models(self) -> List[str]:
        """Get list of available model names"""
        return list(self.model_mapping.keys())

    def get_model_info(self) -> Dict[str, Dict[str, str]]:
        """Get detailed information about available models"""
        model_info = {}
        for key, value in self.model_mapping.items():
            provider = "Ollama"
            if 'gemini' in value:
                provider = "Google"
            elif 'openai' in key or 'gpt' in value:
                provider = "OpenAI"
            
            model_info[key] = {
                "actual_model": value,
                "provider": provider,
                "status": "initialized" if key in self.models else "not_initialized"
            }
        
        return model_info

    def switch_model_mid_conversation(self, session_id: str, new_model: str) -> bool:
        """
        Switch to a different model while preserving conversation history.
        Returns True if successful, False otherwise.
        """
        try:
            if new_model not in self.model_mapping:
                logger.error(f"Invalid model name: {new_model}")
                return False
            
            # Ensure the new model is initialized
            self._get_or_create_model(new_model)
            
            logger.info(f"Model switched to {new_model} for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error switching model: {str(e)}")
            return False
