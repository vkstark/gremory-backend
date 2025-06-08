from typing import Optional
from enum import Enum
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.configs.config import APIResponse
from app.services.chat_service import ChatService
from app.logger import logger

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
        "endpoints": ["/chat", "/models"]
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

@router.get("/conversations/{user_id}")
async def get_user_conversations(
    user_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    service: ChatService = Depends(get_chat_service)
):
    """Get user's conversation history"""
    try:
        if not service.history_service:
            raise HTTPException(status_code=500, detail="History service not available")
        
        from app.schemas.user_history_schemas import PaginationParams, ConversationFilters, ConversationType
        
        pagination = PaginationParams(page=page, per_page=per_page, sort_by="updated_at", sort_order="desc")
        filters = ConversationFilters(search_query=None)
        
        result = await service.history_service.get_user_history(user_id, pagination, filters)
        return result
        
    except Exception as e:
        logger.error(f"Error getting conversations for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/conversations/{user_id}/{conversation_id}")
async def get_conversation_details(
    user_id: int,
    conversation_id: int,
    service: ChatService = Depends(get_chat_service)
):
    """Get detailed conversation information including messages"""
    try:
        if not service.history_service:
            raise HTTPException(status_code=500, detail="History service not available")
        
        result = await service.history_service.get_conversation_details(conversation_id, user_id)
        return result
        
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id} for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/conversations/{user_id}/new")
async def create_new_conversation(
    user_id: int,
    title: Optional[str] = None,
    service: ChatService = Depends(get_chat_service)
):
    """Create a new conversation for the user"""
    try:
        if not service.history_service:
            raise HTTPException(status_code=500, detail="History service not available")
        
        result = await service.history_service.create_chat_history(
            user_id=user_id,
            title=title or f"New Chat",
            conversation_type="bot",
            description="AI conversation"
        )
        return result
        
    except Exception as e:
        logger.error(f"Error creating conversation for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/conversations/{user_id}/{conversation_id}/continue")
async def continue_conversation(
    user_id: int,
    conversation_id: int,
    service: ChatService = Depends(get_chat_service)
):
    """Continue an existing conversation (reactivate if needed)"""
    try:
        if not service.history_service:
            raise HTTPException(status_code=500, detail="History service not available")
        
        result = await service.history_service.continue_chat_history(conversation_id, user_id)
        return result
        
    except Exception as e:
        logger.error(f"Error continuing conversation {conversation_id} for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/conversations/{user_id}/{conversation_id}")
async def delete_conversation(
    user_id: int,
    conversation_id: int,
    service: ChatService = Depends(get_chat_service)
):
    """Delete a conversation"""
    try:
        if not service.history_service:
            raise HTTPException(status_code=500, detail="History service not available")
        
        result = await service.history_service.delete_conversation(conversation_id, user_id)
        return result
        
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id} for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
