from typing import Optional
from enum import Enum
from fastapi import APIRouter, HTTPException, Depends
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
        logger.info(f"Processing chat request for model: {data.lm_name}, query length: {len(data.user_query)}")
        
        result = await service.get_ai_response(data.lm_name.value, data.user_query)
        
        logger.info(f"Successfully processed chat request for model: {data.lm_name}")
        return result
        
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
