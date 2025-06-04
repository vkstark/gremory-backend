
from typing import Dict, Optional, Any, List
import os
import re
from langchain_ollama.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages import (
    SystemMessage, 
    HumanMessage, 
    AIMessage, 
    trim_messages,
    RemoveMessage
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph

from app.configs.config import APIResponse
from app.logger import logger
from app.config import settings
from app.configs.constants import SYSTEM_PROMPT

class ChatService:
    def __init__(self):
        self.models: Dict[str, BaseLanguageModel] = {}
        self.model_mapping = {
            "ollama_qwen": "qwen3:8b",
            "gemini_2o_flash": "gemini-2.0-flash"
        }
        self.system_prompt = self._get_system_prompt()
        
        # History management
        self.memory = MemorySaver()
        self.apps: Dict[str, Any] = {}  # Store compiled graphs per model
        self.max_history_length = getattr(settings, 'MAX_HISTORY_LENGTH', 10)
        self.enable_summarization = getattr(settings, 'ENABLE_SUMMARIZATION', True)
        self.summary_threshold = getattr(settings, 'SUMMARY_THRESHOLD', 10)

    def _get_system_prompt(self) -> str:
        """Define the system prompt for all models"""
        system_prompt = SYSTEM_PROMPT
        return system_prompt
    
    async def initialize(self):
        """Initialize models and apps on startup"""
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

        # Initialize apps for each model
        for model_name in self.model_mapping.keys():
            self._create_app(model_name)

        logger.info("Chat service initialization complete")

    async def cleanup(self):
        """Cleanup resources on shutdown"""
        logger.info("Cleaning up chat service...")
        self.models.clear()
        self.apps.clear()

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

    def _create_app(self, model_name: str):
        """Create LangGraph app with memory for a specific model"""
        logger.debug(f"Creating LangGraph app for model: {model_name}")
        
        workflow = StateGraph(state_schema=MessagesState)
        
        def call_model(state: MessagesState):
            logger.debug(f"call_model function called for {model_name}")
            return self._call_model_with_history(state, model_name)
        
        workflow.add_node("model", call_model)
        workflow.add_edge(START, "model")
        
        # Compile with memory checkpointer
        self.apps[model_name] = workflow.compile(checkpointer=self.memory)
        logger.info(f"Created LangGraph app for model: {model_name}")
        logger.debug(f"Memory checkpointer type: {type(self.memory)}")
        logger.debug(f"App compiled successfully for {model_name}")

    def _call_model_with_history(self, state: MessagesState, model_name: str):
        """Call model with conversation history management"""
        model = self._get_or_create_model(model_name)
        
        # DEBUG: Log incoming state
        logger.debug(f"[{model_name}] _call_model_with_history called")
        logger.debug(f"[{model_name}] Incoming state messages count: {len(state['messages'])}")
        for i, msg in enumerate(state["messages"]):
            msg_type = type(msg).__name__
            content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            logger.debug(f"[{model_name}] Message {i}: {msg_type} - '{content_preview}'")
        
        # Get message history (excluding current user input)
        message_history = state["messages"][:-1]
        current_message = state["messages"][-1]
        
        logger.debug(f"[{model_name}] Message history length: {len(message_history)}")
        logger.debug(f"[{model_name}] Current message: {current_message.content}")
        
        # Handle summarization if history is too long
        if (self.enable_summarization and 
            len(message_history) >= self.summary_threshold):
            
            logger.debug(f"[{model_name}] Triggering summarization (threshold: {self.summary_threshold})")
            return self._handle_summarization(
                model, message_history, current_message, state
            )
        
        # Handle trimming if history exceeds max length
        elif len(message_history) > self.max_history_length:
            logger.debug(f"[{model_name}] Trimming messages (max length: {self.max_history_length})")
            trimmed_messages = self._trim_messages(message_history)
            messages = [SystemMessage(self.system_prompt)] + trimmed_messages + [current_message]
        else:
            logger.debug(f"[{model_name}] Using full history (no trimming/summarization needed)")
            messages = [SystemMessage(self.system_prompt)] + state["messages"]
        
        # DEBUG: Log final message chain being sent to model
        logger.debug(f"[{model_name}] Final message chain length: {len(messages)}")
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            logger.debug(f"[{model_name}] Final Message {i}: {msg_type} - '{content_preview}'")
        
        # Invoke model
        logger.debug(f"[{model_name}] Invoking model with {len(messages)} messages")
        response = model.invoke(messages)
        
        # DEBUG: Log model response
        response_preview = response.content[:100] + "..." if len(response.content) > 100 else response.content
        logger.debug(f"[{model_name}] Model response: '{response_preview}'")
        
        return {"messages": response}

    def _handle_summarization(self, model, message_history: List, current_message, state):
        """Handle conversation summarization when history gets too long"""
        try:
            # Create summary prompt
            summary_prompt = (
                "Distill the above chat messages into a single summary message. "
                "Include as many specific details as you can, especially user preferences, "
                "context, and important information that should be remembered."
            )
            
            # Generate summary
            summary_message = model.invoke(
                message_history + [HumanMessage(summary_prompt)]
            )
            
            # Create deletion instructions for old messages
            delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-1]]
            
            # Create new human message (to reset ID)
            human_message = HumanMessage(current_message.content)
            
            # Generate response with summary context
            system_message = SystemMessage(
                self.system_prompt + 
                "\n\nThe provided chat history includes a summary of the earlier conversation."
            )
            response = model.invoke([system_message, summary_message, human_message])
            
            # Return updates: summary, current message, response, and deletions
            return {
                "messages": [summary_message, human_message, response] + delete_messages
            }
            
        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}, falling back to trimming")
            # Fallback to trimming
            trimmed_messages = self._trim_messages(message_history)
            messages = [SystemMessage(self.system_prompt)] + trimmed_messages + [current_message]
            response = model.invoke(messages)
            return {"messages": response}

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

    async def get_ai_response(
        self, 
        model_name: str, 
        user_prompt: str, 
        session_id: str = "default"
    ) -> APIResponse:
        """Get AI response with conversation history"""
        api_response = APIResponse()
        
        try:
            logger.debug(f"=== AI RESPONSE START ===")
            logger.debug(f"Model: {model_name}, Session: {session_id}")
            logger.debug(f"User prompt: '{user_prompt}'")
            
            # Ensure app exists for this model
            if model_name not in self.apps:
                logger.debug(f"Creating new app for model: {model_name}")
                self._create_app(model_name)
            
            app = self.apps[model_name]
            
            # DEBUG: Check current state before invoke
            try:
                current_state = app.get_state(config={"configurable": {"thread_id": session_id}})
                if current_state.values and "messages" in current_state.values:
                    existing_messages = current_state.values["messages"]
                    logger.debug(f"[{model_name}] Existing history length: {len(existing_messages)}")
                    for i, msg in enumerate(existing_messages):
                        msg_type = type(msg).__name__
                        content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                        logger.debug(f"[{model_name}] Existing Message {i}: {msg_type} - '{content_preview}'")
                else:
                    logger.debug(f"[{model_name}] No existing history found")
            except Exception as e:
                logger.debug(f"[{model_name}] Could not retrieve existing state: {str(e)}")
            
            logger.info(f"Invoking model {model_name} with prompt length: {len(user_prompt)} for session: {session_id}")
            
            # Invoke with conversation history
            result = app.invoke(
                {"messages": [HumanMessage(user_prompt)]},
                config={"configurable": {"thread_id": session_id}}
            )
            
            # DEBUG: Log the complete result
            logger.debug(f"[{model_name}] Complete result messages count: {len(result['messages'])}")
            for i, msg in enumerate(result["messages"]):
                msg_type = type(msg).__name__
                content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                logger.debug(f"[{model_name}] Result Message {i}: {msg_type} - '{content_preview}'")
            
            # Get the latest AI response
            latest_message = result["messages"][-1]
            
            # Log the raw response for debugging (truncated)
            content_preview = latest_message.content[:200] + "..." if len(latest_message.content) > 200 else latest_message.content
            logger.debug(f"Model response preview: {content_preview}")
            
            # Extract the final answer
            extracted = self._extract_final_answer(latest_message.content)
            api_response.data = {
                "answer": extracted['answer'],
                "model_used": model_name,
                "session_id": session_id,
                "has_reasoning": extracted['reasoning'] is not None,
                "message_count": len(result["messages"])
            }
            
            # Optionally include reasoning in response for debugging
            if extracted['reasoning'] and settings.INCLUDE_REASONING:
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
            if not model_name:
                model_name = list(self.model_mapping.keys())[0]  # Use first available model
            
            if model_name not in self.apps:
                self._create_app(model_name)
            
            app = self.apps[model_name]
            
            # Get state for the session
            state = app.get_state(config={"configurable": {"thread_id": session_id}})
            
            messages = state.values.get("messages", []) if state.values else []
            
            # Convert messages to serializable format
            history = []
            for msg in messages:
                if isinstance(msg, (HumanMessage, AIMessage)):
                    history.append({
                        "type": "human" if isinstance(msg, HumanMessage) else "ai",
                        "content": msg.content,
                        "timestamp": getattr(msg, 'timestamp', None)
                    })
            
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
            # Clear from all model apps
            for model_name, app in self.apps.items():
                try:
                    # Get current state
                    state = app.get_state(config={"configurable": {"thread_id": session_id}})
                    if state.values and "messages" in state.values:
                        # Create delete messages for all existing messages
                        delete_messages = [
                            RemoveMessage(id=m.id) 
                            for m in state.values["messages"] 
                            if hasattr(m, 'id')
                        ]
                        if delete_messages:
                            app.invoke(
                                {"messages": delete_messages},
                                config={"configurable": {"thread_id": session_id}}
                            )
                except Exception as e:
                    logger.warning(f"Error clearing history for model {model_name}: {str(e)}")
            
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
        """Update system prompt and reinitialize apps"""
        logger.info("Updating system prompt...")
        self.system_prompt = new_prompt
        
        # Clear existing models and apps to force reinitialization with new prompt
        self.models.clear()
        self.apps.clear()
        
        # Reinitialize apps for each model
        for model_name in self.model_mapping.keys():
            self._create_app(model_name)
        
        logger.info("System prompt updated. Apps reinitialized.")

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