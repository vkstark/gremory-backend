from typing import Dict, Optional, Any, List, Union, Tuple
import os
import re
import json
import httpx
import time
from langchain_ollama.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages import (
    SystemMessage, 
    HumanMessage, 
    AIMessage, 
    ToolMessage,
    trim_messages,
    RemoveMessage
)

from common_utils.schema.response_schema import APIResponse
from common_utils.schema.user_history_schema import SendMessageRequest, MessageType
from common_utils.logger import logger
from common_utils.main_setting import settings
from .SYSTEM_PROMPT import SAFETY_CORE_PROMPT, PERSONA_ROUTER_PROMPT, RESPONSE_FORMAT_PROMPT, USER_PERSONALIZATION_PROMPT, TOOL_REGISTRY_PROMPT#, SYSTEM_PROMPT 

SYSTEM_PROMPT = (
    SAFETY_CORE_PROMPT + "\n---\n" +
    PERSONA_ROUTER_PROMPT + "\n---\n" +
    USER_PERSONALIZATION_PROMPT + "\n---\n" +
    TOOL_REGISTRY_PROMPT + "\n---\n" +
    RESPONSE_FORMAT_PROMPT
)

# Import for database integration
from user_history.user_history_service import UserHistoryService

from .models import SUPPORTED_MODELS
from .ext_tools_init.tool_compile import ALL_TOOLS

class ChatService:
    def __init__(self):
        self.models: Union[Dict[str, ChatGoogleGenerativeAI], Dict[str,ChatOllama], Dict[str,ChatOpenAI]] = {}
        self.model_mapping = SUPPORTED_MODELS
        self.system_prompt = self._get_system_prompt()
        
        # Database integration for persistent history
        self.history_service: Optional[UserHistoryService] = None
        
        # Centralized history management - one history per session, not per model
        self.conversations: Dict[str, List[Any]] = {}  # session_id -> list of messages
        self.max_history_length = getattr(settings, 'MAX_HISTORY_LENGTH', 10)
        self.enable_summarization = getattr(settings, 'ENABLE_SUMMARIZATION', True)
        self.summary_threshold = getattr(settings, 'SUMMARY_THRESHOLD', 10)
        
        # Personalization service configuration
        self.personalization_service_url = os.getenv("PERSONALIZATION_SERVICE_URL", "http://personalization:8004")
        
        # External tools service configuration
        self.ext_tools_service_url = os.getenv("EXT_TOOLS_SERVICE_URL", "http://ext-tools:8005")
        
        # TTL cache for personalized system prompts (user_id -> {system_prompt, timestamp})
        self.personalized_prompts_cache: Dict[int, Dict[str, Any]] = {}
        self.cache_ttl = 5 * 60  # 5 minutes in seconds

    def _get_system_prompt(self) -> str:
        """Define the system prompt for all models"""
        system_prompt = SYSTEM_PROMPT
        return system_prompt
    
    async def initialize(self):
        """Initialize models on startup"""
        logger.info("Initializing chat service...")
        
        # Initialize history service for database integration
        self.history_service = UserHistoryService()
        await self.history_service.initialize()
        
        # Validate required environment variables
        if not settings.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY not found in environment variables")
        
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        # Pre-initialize models that don't require API keys
        try:
            self.models["ollama_qwen"] = ChatOllama(
                model=self.model_mapping["ollama_qwen"],
                base_url="http://host.docker.internal:11434"
            )
            logger.info("Ollama model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama model: {str(e)}")

        # Start periodic cache cleanup task
        # Note: In production, you might want to use a proper task scheduler
        logger.info(f"Personalization cache TTL set to {self.cache_ttl} seconds")
        
        logger.info("Chat service initialization complete")

    async def cleanup(self):
        """Cleanup resources on shutdown"""
        logger.info("Cleaning up chat service...")
        self.models.clear()
        self.conversations.clear()
        
        # Cleanup personalization cache
        self.personalized_prompts_cache.clear()
        
        # Cleanup history service
        if self.history_service:
            await self.history_service.cleanup()

    def _get_or_create_model(self, model_name: str) -> Union[ChatOllama, ChatGoogleGenerativeAI, ChatOpenAI]:
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
            ).bind_tools(ALL_TOOLS)
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
            
            self.models[model_name] = ChatOpenAI(**openai_config).bind_tools(ALL_TOOLS)
            logger.info(f"Created new OpenAI model: {actual_model_name}")
            
        else:  # Ollama models
            self.models[model_name] = ChatOllama(
                model=actual_model_name,
                base_url="http://host.docker.internal:11434"
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

    async def get_ai_response_with_conversation(
        self, 
        model_name: str, 
        user_prompt: str, 
        user_id: int,
        conversation_id: Optional[int] = None
    ) -> APIResponse:
        """Get AI response with database conversation integration"""
        api_response = APIResponse()
        
        try:
            logger.debug(f"=== AI RESPONSE WITH CONVERSATION START ===")
            logger.debug(f"Model: {model_name}, User: {user_id}, Conversation: {conversation_id}")
            logger.debug(f"User prompt: '{user_prompt}'")
            
            # Validate inputs
            if not user_prompt or not user_prompt.strip():
                api_response.code = -1
                api_response.data = None
                api_response.msg = "User prompt cannot be empty"
                return api_response
            
            if user_id <= 0:
                api_response.code = -1
                api_response.data = None
                api_response.msg = "Invalid user ID"
                return api_response
            
            # Ensure history service is available
            if not self.history_service:
                api_response.code = -1
                api_response.data = None
                api_response.msg = "History service not initialized"
                return api_response
            
            # If no conversation_id provided, create a new conversation
            if conversation_id is None:
                # Generate conversation title from user prompt
                title = await self._generate_conversation_title(user_prompt)
                
                conversation_result = await self.history_service.create_chat_history(
                    user_id=user_id,
                    title=title,
                    conversation_type="bot",
                    description=f"AI conversation using {model_name}"
                )
                
                if not conversation_result.success or not conversation_result.data:
                    api_response.code = -1
                    api_response.data = None
                    api_response.msg = f"Failed to create conversation: {conversation_result.message}"
                    return api_response
                
                conversation_id = conversation_result.data.id
                logger.info(f"Created new conversation {conversation_id} for user {user_id}")
            
            # Store user message in database
            user_message_request = SendMessageRequest(
                conversation_id=conversation_id,
                sender_id=user_id,
                content=user_prompt,
                message_type=MessageType.TEXT,
                reply_to_id=None,
                message_metadata={}
            )
            
            user_message_result = await self.history_service.send_message(user_message_request)
            if not user_message_result.success:
                logger.warning(f"Failed to store user message: {user_message_result.message}")
            
            # Get conversation history from database
            conversation_history = await self.history_service.get_conversation_details(conversation_id, user_id)
            
            # Get personalized system prompt for this user
            personalized_system_prompt = await self._get_personalized_system_prompt(user_id)
            
            # Log whether we're using personalized or default prompt
            is_personalized = personalized_system_prompt != self.system_prompt
            logger.info(f"Using {'personalized' if is_personalized else 'default'} system prompt for user {user_id}")
            
            # Prepare messages for the model
            messages: List[Any] = [SystemMessage(personalized_system_prompt)]
            
            if conversation_history.success and conversation_history.data and conversation_history.data.messages:
                # Convert database messages to LangChain messages
                for msg in conversation_history.data.messages[:-1]:  # Exclude the just-added user message
                    if msg.message_type in ['text', 'TEXT']:
                        if msg.sender_id == user_id:
                            messages.append(HumanMessage(msg.content))
                        else:
                            messages.append(AIMessage(msg.content))
                    elif msg.message_type == 'ai_response':
                        json_match = re.search(r'```json\s*\n(.*?)\n```', msg.content, flags=re.DOTALL)
                        if json_match:
                            parsed_msg = json.loads(json_match.group(1).strip())
                            messages.append(AIMessage(str(parsed_msg)))
                        else:
                            messages.append(AIMessage(msg.content))
            
            # Add current user message
            messages.append(HumanMessage(user_prompt))
            
            # Get the model
            model = self._get_or_create_model(model_name)
            
            # DEBUG: Log final message chain being sent to model
            logger.debug(f"[{model_name}] Final message chain length: {len(messages)}")
            for i, msg in enumerate(messages):
                msg_type = type(msg).__name__
                content = msg.content
                if isinstance(content, str):
                    content_preview = content[:100] + "..." if len(content) > 100 else content
                else:
                    content_preview = str(content)[:100] + "..."
                logger.debug(f"[{model_name}] Final Message {i}: {msg_type} - '{content_preview}'")
            
            # Invoke model with error handling
            logger.debug(f"[{model_name}] Invoking model with {len(messages)} messages")
            try:
                ai_response_with_tools = model.invoke(messages)
            except Exception as model_error:
                logger.error(f"Model invocation failed: {str(model_error)}")
                api_response.code = -1
                api_response.data = None
                api_response.msg = f"Model failed to generate response: {str(model_error)}"
                return api_response

            # Validate model response
            if not ai_response_with_tools:
                logger.error("Model returned empty response")
                api_response.code = -1
                api_response.data = None
                api_response.msg = "Model returned empty response"
                return api_response

            # Handle tool calls if present with robust error handling
            tool_calls = getattr(ai_response_with_tools, 'tool_calls', None) or []
            tool_execution_results = None
            
            if tool_calls and len(tool_calls) > 0:
                logger.info(f"[{model_name}] Tool calls detected: {len(tool_calls)} calls")
                
                # Validate tool calls structure
                valid_tool_calls = self._validate_tool_calls(tool_calls)
                if not valid_tool_calls:
                    logger.warning("All tool calls failed validation, proceeding without tools")
                    response = ai_response_with_tools
                else:
                    try:
                        # Call external tools service
                        tool_response = await self._call_ext_tools_service(valid_tool_calls)
                        
                        if tool_response.get('success', False):
                            # Process successful tool response
                            tool_execution_results = tool_response
                            tool_data = tool_response.get('data', {})
                            tool_messages = tool_data.get('tool_messages', [])
                            
                            if tool_messages:
                                # Validate tool messages before adding to conversation
                                valid_tool_messages = self._validate_tool_messages(tool_messages)
                                
                                messages.append(ai_response_with_tools)
                                for tool_message in valid_tool_messages:
                                    try:
                                        messages.append(ToolMessage(**tool_message))
                                    except Exception as tm_error:
                                        logger.warning(f"Failed to create ToolMessage: {tm_error}")
                                        continue
                                
                                # Generate follow-up response with tool results
                                try:
                                    response = model.invoke(messages)
                                except Exception as followup_error:
                                    logger.error(f"Follow-up model invocation failed: {followup_error}")
                                    # Fallback to original response
                                    response = ai_response_with_tools
                            else:
                                logger.warning("No valid tool messages returned")
                                response = ai_response_with_tools
                        else:
                            # Tool execution failed, log but continue with original response
                            logger.warning(f"Tool execution failed: {tool_response.get('error', 'Unknown error')}")
                            tool_execution_results = tool_response  # Include failure info
                            response = ai_response_with_tools
                            
                    except Exception as tool_error:
                        logger.error(f"Tool execution error: {str(tool_error)}")
                        # Continue with original response if tools fail
                        response = ai_response_with_tools
            else:
                response = ai_response_with_tools

            # Validate final response
            if not response or not hasattr(response, 'content'):
                logger.error("Final response is invalid")
                api_response.code = -1
                api_response.data = None
                api_response.msg = "Generated response is invalid"
                return api_response

            # Store AI response in database with error handling
            try:
                ai_message_request = SendMessageRequest(
                    conversation_id=conversation_id,
                    sender_id=user_id,
                    content=str(response.content) if response.content else "",
                    message_type=MessageType.AI_RESPONSE,
                    reply_to_id=None,
                    message_metadata={"model_used": model_name}
                )
                
                ai_message_result = await self.history_service.send_message(ai_message_request)
                if not ai_message_result.success:
                    logger.warning(f"Failed to store AI message: {ai_message_result.message}")
            except Exception as db_error:
                logger.error(f"Database storage error: {str(db_error)}")
                # Continue with response even if storage fails
            
            # DEBUG: Log model response
            response_content = response.content
            if isinstance(response_content, str):
                response_preview = response_content[:100] + "..." if len(response_content) > 100 else response_content
            else:
                response_preview = str(response_content)[:100] + "..."
            logger.debug(f"[{model_name}] Model response: '{response_preview}'")
            
            # Extract the final answer
            extracted = self._extract_final_answer(response.content)
            
            # Set up the API response data structure
            tool_calls_count = 0
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_calls_count = len(response.tool_calls)
            
            api_response.code = 0
            api_response.data = {
                "answer": extracted['answer'],
                "model_used": model_name,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "has_reasoning": extracted['reasoning'] is not None,
                "message_count": len(conversation_history.data.messages) + 1 if (conversation_history.success and conversation_history.data and conversation_history.data.messages) else 2,
                "tool_calls_executed": tool_calls_count
            }
            
            # Include tool execution results if tools were called
            if tool_execution_results is not None:
                api_response.data["tool_results"] = tool_execution_results
            
            # Optionally include reasoning in response for debugging
            if extracted['reasoning'] and hasattr(settings, 'INCLUDE_REASONING') and settings.INCLUDE_REASONING:
                api_response.data["reasoning"] = extracted['reasoning']
            
            logger.debug(f"=== AI RESPONSE WITH CONVERSATION END ===")
            api_response.msg = "Response generated successfully"
            return api_response
            
        except ValueError as e:
            logger.warning(f"Validation error in get_ai_response_with_conversation: {str(e)}")
            api_response.code = -1
            api_response.data = None
            api_response.msg = str(e)
            return api_response
            
        except Exception as e:
            logger.error(f"Error in get_ai_response_with_conversation: {str(e)}", exc_info=True)
            api_response.code = -1
            api_response.data = None
            api_response.msg = "Failed to generate AI response"
            return api_response

    def _validate_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """Validate and sanitize tool calls"""
        valid_tool_calls = []
        
        for i, tool_call in enumerate(tool_calls):
            try:
                # Convert tool call to dict if needed
                if hasattr(tool_call, 'dict'):
                    tool_dict = tool_call.dict()
                elif hasattr(tool_call, '__dict__'):
                    tool_dict = tool_call.__dict__
                elif isinstance(tool_call, dict):
                    tool_dict = tool_call
                else:
                    logger.warning(f"Tool call {i} has unexpected format: {type(tool_call)}")
                    continue
                
                # Validate required fields
                if not isinstance(tool_dict, dict):
                    logger.warning(f"Tool call {i} is not a dictionary")
                    continue
                
                # Check for required fields (adjust based on your tool call structure)
                required_fields = ['name', 'args']  # Adjust as needed
                if not all(field in tool_dict for field in required_fields):
                    logger.warning(f"Tool call {i} missing required fields: {required_fields}")
                    continue
                
                # Sanitize tool name
                tool_name = str(tool_dict.get('name', '')).strip()
                if not tool_name:
                    logger.warning(f"Tool call {i} has empty name")
                    continue
                
                # Validate arguments
                args = tool_dict.get('args')
                if args is not None and not isinstance(args, (dict, str)):
                    logger.warning(f"Tool call {i} has invalid args type: {type(args)}")
                    continue
                
                valid_tool_calls.append(tool_dict)
                
            except Exception as e:
                logger.error(f"Error validating tool call {i}: {str(e)}")
                continue
        
        logger.info(f"Validated {len(valid_tool_calls)} out of {len(tool_calls)} tool calls")
        return valid_tool_calls

    def _validate_tool_messages(self, tool_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate tool messages before creating ToolMessage objects"""
        valid_messages = []
        
        for i, msg in enumerate(tool_messages):
            try:
                if not isinstance(msg, dict):
                    logger.warning(f"Tool message {i} is not a dictionary")
                    continue
                
                # Check required fields for ToolMessage
                required_fields = ['content', 'tool_call_id']
                if not all(field in msg for field in required_fields):
                    logger.warning(f"Tool message {i} missing required fields: {required_fields}")
                    continue
                
                # Validate content
                content = msg.get('content')
                if not isinstance(content, str):
                    msg['content'] = str(content) if content is not None else ""
                
                # Validate tool_call_id
                tool_call_id = msg.get('tool_call_id')
                if not isinstance(tool_call_id, str):
                    msg['tool_call_id'] = str(tool_call_id) if tool_call_id is not None else ""
                
                valid_messages.append(msg)
                
            except Exception as e:
                logger.error(f"Error validating tool message {i}: {str(e)}")
                continue
        
        logger.info(f"Validated {len(valid_messages)} out of {len(tool_messages)} tool messages")
        return valid_messages

    async def _call_ext_tools_service(self, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call the external tools service with the tool calls"""
        try:
            # Validate input
            if not tool_calls:
                return {
                    "success": False,
                    "error": "No tool calls provided",
                    "details": "Empty tool calls list"
                }
            
            # Prepare the request payload
            payload = {
                "tool_calls": tool_calls
            }
            
            logger.info(f"Calling ext-tools service with {len(tool_calls)} tool calls")
            logger.debug(f"Tool calls: {tool_calls}")
            logger.debug(f"Ext-tools service URL: {self.ext_tools_service_url}")
            
            # Validate service URL
            if not self.ext_tools_service_url:
                logger.error("Ext-tools service URL not configured")
                return {
                    "success": False,
                    "error": "Service URL not configured",
                    "details": "EXT_TOOLS_SERVICE_URL environment variable not set"
                }
            
            # Call the external tools service
            ext_tools_url = f"{self.ext_tools_service_url}/execute"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.post(
                        ext_tools_url,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                except httpx.TimeoutException:
                    logger.error("Ext-tools service request timed out")
                    return {
                        "success": False,
                        "error": "Service timeout",
                        "details": "Request to ext-tools service timed out after 30 seconds"
                    }
                
                if response.status_code == 200:
                    try:
                        tool_response = response.json()
                    except json.JSONDecodeError as json_err:
                        logger.error(f"Failed to parse JSON response from ext-tools service: {json_err}")
                        return {
                            "success": False,
                            "error": "Invalid JSON response",
                            "details": f"JSON decode error: {str(json_err)}"
                        }
                    
                    logger.info(f"Ext-tools service responded successfully")
                    logger.debug(f"Tool response: {tool_response}")
                    
                    # Validate response structure
                    if not isinstance(tool_response, dict):
                        logger.error("Ext-tools service returned non-dict response")
                        return {
                            "success": False,
                            "error": "Invalid response format",
                            "details": "Expected dict response from ext-tools service"
                        }
                    
                    # Extract success status from the APIResponse format
                    # Handle both 'code' field (APIResponse format) and direct success field
                    if 'code' in tool_response:
                        success = tool_response.get('code') == 200
                    else:
                        success = tool_response.get('success', False)
                    
                    return {
                        "success": success,
                        "data": tool_response.get('data', {}),
                        "message": tool_response.get('msg', tool_response.get('message', 'Tool execution completed')),
                    }
                else:
                    error_text = response.text if hasattr(response, 'text') else str(response.content)
                    logger.error(f"Ext-tools service returned status {response.status_code}: {error_text}")
                    return {
                        "success": False,
                        "error": f"Tool service error: {response.status_code}",
                        "details": error_text
                    }
                    
        except httpx.RequestError as exc:
            logger.error(f"HTTP request to ext-tools service failed: {exc}")
            return {
                "success": False,
                "error": "Connection to tool service failed",
                "details": str(exc)
            }
        except Exception as e:
            logger.error(f"Unexpected error calling ext-tools service: {e}", exc_info=True)
            return {
                "success": False,
                "error": "Unexpected error",
                "details": str(e)
            }

    def _extract_final_answer(self, output: str) -> Dict[str, Any]:
        """Extract reasoning and answer from model output"""
        if not output:
            return {'reasoning': None, 'answer': ''}
        
        # Ensure output is a string
        if not isinstance(output, str):
            output = str(output)
        
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

    async def _generate_conversation_title(self, user_prompt: str) -> str:
        """Generate a conversation title from the first user message"""
        try:
            # Use a simple model to generate title
            if "ollama_qwen" in self.models:
                model = self.models["ollama_qwen"]
            else:
                model = self._get_or_create_model("ollama_qwen")
            
            title_prompt = f"""Generate a short, descriptive title (max 50 characters) for a conversation that starts with this user message: "{user_prompt[:200]}"

Return only the title, nothing else."""
            
            response = model.invoke([HumanMessage(title_prompt)])
            title = response.content.strip().strip('"').strip("'")
            
            # Fallback to truncated user prompt if generation fails
            if len(title) > 50 or len(title) < 3:
                title = user_prompt[:47] + "..." if len(user_prompt) > 50 else user_prompt
            
            return title
            
        except Exception as e:
            logger.warning(f"Failed to generate conversation title: {str(e)}", exc_info=True)
            # Fallback to truncated user prompt
            return user_prompt[:47] + "..." if len(user_prompt) > 50 else user_prompt

    async def _fetch_user_personalization(self, user_id: int) -> Dict[str, Any]:
        """Fetch user personalization data from personalization service"""
        try:
            personalization_url = f"{self.personalization_service_url}/profile/{user_id}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(personalization_url)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Successfully fetched personalization data for user {user_id}")
                    return data
                elif response.status_code == 404:
                    logger.info(f"No personalization profile found for user {user_id}")
                    return {}
                else:
                    logger.warning(f"Failed to fetch personalization data for user {user_id}. Status: {response.status_code}")
                    return {}
                    
        except httpx.RequestError as exc:
            logger.error(f"HTTP request to personalization service failed for user {user_id}: {exc}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching personalization data for user {user_id}: {e}")
            return {}

    def _create_personalized_system_prompt(self, user_id: int, personalization_data: Dict[str, Any]) -> str:
        """Create personalized system prompt for a user"""
        try:
            # Extract relevant user data
            user_name = personalization_data.get('name', 'User')
            preferences = personalization_data.get('preferences', {})
            
            # Build user preferences text
            user_preferences_text = f"User Name: {user_name}\n"
            
            if preferences:
                user_preferences_text += "User Preferences:\n"
                for key, value in preferences.items():
                    if value:  # Only include non-empty values
                        if isinstance(value, list):
                            user_preferences_text += f"  - {key.replace('_', ' ').title()}: {', '.join(map(str, value))}\n"
                        elif isinstance(value, dict):
                            user_preferences_text += f"  - {key.replace('_', ' ').title()}:\n"
                            for sub_key, sub_value in value.items():
                                if sub_value:
                                    user_preferences_text += f"    * {sub_key.replace('_', ' ').title()}: {sub_value}\n"
                        else:
                            user_preferences_text += f"  - {key.replace('_', ' ').title()}: {value}\n"
            else:
                user_preferences_text += "No specific preferences available.\n"
            
            # Create personalized system prompt by formatting the USER_PERSONALIZATION_PROMPT
            personalized_user_section = USER_PERSONALIZATION_PROMPT.format(
                user_preferences=user_preferences_text.strip()
            )
            
            # Construct the full personalized system prompt
            personalized_system_prompt = (
                SAFETY_CORE_PROMPT + "\n\n" +
                PERSONA_ROUTER_PROMPT + "\n\n" +
                personalized_user_section + "\n\n" +
                RESPONSE_FORMAT_PROMPT
            )
            
            logger.debug(f"Created personalized system prompt for user {user_id}")
            return personalized_system_prompt
            
        except Exception as e:
            logger.error(f"Error creating personalized system prompt for user {user_id}: {e}")
            # Fallback to default system prompt
            return self.system_prompt

    async def _get_personalized_system_prompt(self, user_id: int) -> str:
        """Get personalized system prompt for user with TTL caching"""
        try:
            current_time = time.time()
            
            # Check if we have a cached prompt and it's still valid
            if user_id in self.personalized_prompts_cache:
                cached_data = self.personalized_prompts_cache[user_id]
                if current_time - cached_data['timestamp'] < self.cache_ttl:
                    logger.debug(f"Using cached personalized system prompt for user {user_id}")
                    return cached_data['system_prompt']
                else:
                    logger.debug(f"Cached system prompt expired for user {user_id}, refreshing")
            
            # Fetch fresh personalization data
            personalization_data = await self._fetch_user_personalization(user_id)
            
            # Create personalized system prompt
            personalized_prompt = self._create_personalized_system_prompt(user_id, personalization_data)
            
            # Cache the result
            self.personalized_prompts_cache[user_id] = {
                'system_prompt': personalized_prompt,
                'timestamp': current_time
            }
            
            logger.debug(f"Cached new personalized system prompt for user {user_id}")
            return personalized_prompt
            
        except Exception as e:
            logger.error(f"Error getting personalized system prompt for user {user_id}: {e}")
            # Fallback to default system prompt
            return self.system_prompt

    def _cleanup_expired_cache_entries(self):
        """Clean up expired cache entries"""
        try:
            current_time = time.time()
            expired_users = []
            
            for user_id, cached_data in self.personalized_prompts_cache.items():
                if current_time - cached_data['timestamp'] >= self.cache_ttl:
                    expired_users.append(user_id)
            
            for user_id in expired_users:
                del self.personalized_prompts_cache[user_id]
                logger.debug(f"Removed expired cache entry for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")

    def clear_user_cache(self, user_id: int):
        """Clear cached personalized system prompt for a specific user"""
        if user_id in self.personalized_prompts_cache:
            del self.personalized_prompts_cache[user_id]
            logger.info(f"Cleared personalized system prompt cache for user {user_id}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        current_time = time.time()
        active_entries = 0
        expired_entries = 0
        
        for cached_data in self.personalized_prompts_cache.values():
            if current_time - cached_data['timestamp'] < self.cache_ttl:
                active_entries += 1
            else:
                expired_entries += 1
        
        return {
            "total_entries": len(self.personalized_prompts_cache),
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "cache_ttl_seconds": self.cache_ttl
        }
