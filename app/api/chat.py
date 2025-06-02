from typing import Dict, Optional
from enum import Enum
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
import os
from contextlib import asynccontextmanager

from app.models.config import APIResponse
from app.services.chat_service import ChatService
from app.logger import logger

# Global chat service instance
chat_service: Optional[ChatService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global chat_service
    chat_service = ChatService()
    await chat_service.initialize()
    yield
    # Shutdown
    if chat_service:
        await chat_service.cleanup()

app = FastAPI(
    title="AI Chat API",
    description="API for chatting with various AI models",
    version="1.0.0",
    lifespan=lifespan
)

class SupportedModels(str, Enum):
    OLLAMA_QWEN = "ollama_qwen"
    GEMINI_2O_FLASH = "gemini_2o_flash"

class UserInput(BaseModel):
    lm_name: SupportedModels
    user_query: str = Field(..., min_length=1, max_length=10000)


def get_chat_service() -> ChatService:
    if chat_service is None:
        raise HTTPException(status_code=500, detail="Chat service not initialized")
    return chat_service

@app.get("/")
def read_root():
    return {"message": "AI Chat API", "status": "healthy"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ai-chat-api"}

@app.get("/models")
def get_supported_models():
    return {"supported_models": [model.value for model in SupportedModels]}

@app.post("/chat", response_model=APIResponse)
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