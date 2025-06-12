
from typing import Optional
from enum import Enum
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from common_utils.schema.response_schema import APIResponse
from common_utils.logger import logger

# from chat_inference.chat_service import ChatService  # TODO

# Create router instead of FastAPI app
router = APIRouter()

# Global chat service instance for this router
chat_service: Optional[PersonalizeService] = None
