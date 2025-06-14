
from typing import Optional, List, Dict, Any
from enum import Enum
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from common_utils.schema.response_schema import APIResponse
from ..tool_service import ToolService
from common_utils.logger import logger

# Create router instead of FastAPI app
router = APIRouter()

# Global tool service instance for this router
tool_service: Optional[ToolService] = None

class ToolCallInput(BaseModel):
    tool_calls: List[Dict[str, Any]] = Field(..., description="List of tool calls to execute")

class ToolInfoInput(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to get information about")

def get_tool_service() -> ToolService:
    if tool_service is None:
        raise HTTPException(status_code=500, detail="Tool service not initialized")
    return tool_service

# Initialize tool service for this router (called from main.py)
async def initialize_tool_service():
    global tool_service
    if tool_service is None:
        tool_service = ToolService()
        await tool_service.initialize()
        logger.info("Tool service initialized for tool router")

# Cleanup tool service (called from main.py)
async def cleanup_tool_service():
    global tool_service
    if tool_service:
        await tool_service.cleanup()
        tool_service = None
        logger.info("Tool service cleaned up for tool router")

@router.get("/")
def read_tools_root():
    return {
        "message": "External Tools API", 
        "status": "healthy",
        "endpoints": ["/tools", "/execute", "/info", "/health"],
        "description": "API for executing external tools and getting tool information"
    }

@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "external-tools-api"}

@router.get("/tools", response_model=APIResponse)
async def get_available_tools(service: ToolService = Depends(get_tool_service)) -> APIResponse:
    """Get list of available tools"""
    try:
        tools_info = service.get_available_tools()
        
        api_response = APIResponse()
        api_response.code = 200
        api_response.msg = "Available tools retrieved successfully"
        api_response.data = {
            "tools": tools_info,
            "total_count": len(tools_info)
        }
        
        return api_response
        
    except Exception as e:
        logger.error(f"Error getting available tools: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/execute", response_model=APIResponse)
async def execute_tool_calls(
    data: ToolCallInput,
    service: ToolService = Depends(get_tool_service)
) -> APIResponse:
    """
    Execute a list of tool calls and return the results.
    This endpoint is designed to work with LangChain tool calls.
    
    Expected format for tool_calls:
    [
        {
            "name": "tool_name",
            "args": {"param1": "value1", "param2": "value2"},
            "id": "call_id_123"
        }
    ]
    """
    try:
        if not data.tool_calls:
            api_response = APIResponse()
            api_response.code = 400
            api_response.msg = "No tool calls provided"
            api_response.data = {"error": "tool_calls list cannot be empty"}
            return api_response
        
        logger.info(f"Executing {len(data.tool_calls)} tool calls")
        
        result = await service.execute_tool_calls(data.tool_calls)
        
        logger.info(f"Tool execution completed with code: {result.code}")
        return result
        
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in execute_tool_calls endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/info", response_model=APIResponse)
async def get_tool_info(
    data: ToolInfoInput,
    service: ToolService = Depends(get_tool_service)
) -> APIResponse:
    """Get detailed information about a specific tool"""
    try:
        result = await service.get_tool_info(data.tool_name)
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error in get_tool_info endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/info/{tool_name}", response_model=APIResponse)
async def get_tool_info_by_path(
    tool_name: str,
    service: ToolService = Depends(get_tool_service)
) -> APIResponse:
    """Get detailed information about a specific tool (GET endpoint)"""
    try:
        result = await service.get_tool_info(tool_name)
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error in get_tool_info_by_path endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
