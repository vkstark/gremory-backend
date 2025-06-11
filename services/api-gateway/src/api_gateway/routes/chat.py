"""
AI Chat API - Focused on AI model interactions and chat functionality.

This API handles:
- AI model chat interactions (/chat)
- Supported model listing (/models)
- Health checks (/health)

For conversation management (CRUD operations), use the user-history API endpoints:
- GET /api/v1/user/{user_id}/history - Get user conversations
- POST /api/v1/user/history - Create new conversation
- GET /api/v1/conversation/{id} - Get conversation details
- PUT /api/v1/conversation/{id} - Update conversation
- DELETE /api/v1/conversation/{id} - Delete conversation
"""

from typing import Optional
from enum import Enum
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from common_utils.schema.response_schema import APIResponse
from chat_inference.chat_service import ChatService
from common_utils.logger import logger

# Create router instead of FastAPI app
router = APIRouter()

# Global chat service instance for this router
chat_service: Optional[ChatService] = None

class SupportedModels(str, Enum):
    OLLAMA_QWEN = "ollama_qwen"
    OLLAMA_LLAMA = "ollama_llama"
    GEMINI_2O_FLASH = "gemini_2o_flash"
    OPENAI_4o = "openai_gpt4"

class UserInput(BaseModel):
    lm_name: SupportedModels
    user_query: str = Field(..., min_length=1, max_length=10000)
    user_id: int = Field(..., description="ID of the user sending the message")
    conversation_id: Optional[int] = Field(None, description="ID of existing conversation, or None to create new one")
    

def get_chat_service() -> ChatService:
    if chat_service is None:
        raise HTTPException(status_code=500, detail="Chat service not initialized")
    return chat_service

# Initialize chat service for this router (called from main.py)
async def initialize_chat_service():
    global chat_service
    if chat_service is None:
        chat_service = ChatService()
        await chat_service.initialize()
        logger.info("Chat service initialized for chat router")

# Cleanup chat service (called from main.py)
async def cleanup_chat_service():
    global chat_service
    if chat_service:
        await chat_service.cleanup()
        chat_service = None
        logger.info("Chat service cleaned up for chat router")

@router.get("/")
def read_chat_root():
    return {
        "message": "AI Chat API", 
        "status": "healthy",
        "endpoints": ["/chat", "/models", "/health"],
        "note": "For conversation management, use the user-history API endpoints"
    }

@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "ai-chat-api"}

@router.get("/models")
def get_supported_models():
    return {"supported_models": [model.value for model in SupportedModels]}

@router.post("/chat", response_model=APIResponse)
async def chat(
    data: UserInput, 
    service: ChatService = Depends(get_chat_service)
) -> APIResponse:
    try:
        logger.info(f"Processing chat request for model: {data.lm_name}, user: {data.user_id}, conversation: {data.conversation_id}, query length: {len(data.user_query)}")
        
        # Use the new conversation-based method
        result = await service.get_ai_response_with_conversation(
            model_name=data.lm_name.value, 
            user_prompt=data.user_query,
            user_id=data.user_id,
            conversation_id=data.conversation_id
        )
        
        logger.info(f"Successfully processed chat request for model: {data.lm_name}, conversation: {result.data.get('conversation_id') if result.data else 'unknown'}")
        return result
        
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
