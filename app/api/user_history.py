from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional
from app.services.user_history_service import UserHistoryService
from app.schemas.user_history_schemas import (
    UserHistoryResponse, UserMessagesResponse, ConversationResponse,
    NewChatHistoryRequest, SendMessageRequest, UpdateConversationRequest,
    MessageSentResponse, ConversationCreatedResponse, ConversationUpdatedResponse,
    PaginationParams, ConversationFilters, MessageFilters,
    ConversationType, ConversationState, MessageType
)
from app.logger import logger

router = APIRouter()

# Global service instance
user_history_service = UserHistoryService()

# Service lifecycle management
async def initialize_user_history_service():
    """Initialize user history service"""
    await user_history_service.initialize()

async def cleanup_user_history_service():
    """Cleanup user history service"""
    await user_history_service.cleanup()

# Dependency to get service
def get_user_history_service() -> UserHistoryService:
    return user_history_service

# Helper functions for type conversion
def convert_to_enum(value: Optional[str], enum_class):
    """Convert string to enum if value is provided"""
    if value is None:
        return None
    try:
        return enum_class(value)
    except ValueError:
        return None

# Error response helper
def create_error_response(status_code: int, message: str, details: Optional[str] = None):
    """Create standardized error response"""
    error_data = {
        "success": False,
        "message": message,
        "data": None
    }
    if details:
        error_data["details"] = details
    return JSONResponse(status_code=status_code, content=error_data)

@router.get("/user/{user_id}/history", response_model=UserHistoryResponse)
async def get_user_history(
    user_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    conversation_type: Optional[str] = Query(None, description="Filter by conversation type"),
    conversation_state: Optional[str] = Query(None, description="Filter by conversation state"),
    is_archived: Optional[bool] = Query(None, description="Filter by archive status"),
    search_query: Optional[str] = Query(None, description="Search in conversation name and description"),
    service: UserHistoryService = Depends(get_user_history_service)
):
    """Get user's conversation history with pagination and filters"""
    try:
        pagination = PaginationParams(
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Convert string parameters to enums
        conv_type_enum = convert_to_enum(conversation_type, ConversationType)
        conv_state_enum = convert_to_enum(conversation_state, ConversationState)
        
        filters = ConversationFilters(
            conversation_type=conv_type_enum,
            conversation_state=conv_state_enum,
            is_archived=is_archived,
            search_query=search_query
        )
        
        history = await service.get_user_history(user_id, pagination, filters)
        return history
    except Exception as e:
        logger.error(f"Error getting user history for user {user_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.get("/conversation/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_details(
    conversation_id: int,
    user_id: Optional[int] = Query(None, description="User ID for access control"),
    service: UserHistoryService = Depends(get_user_history_service)
):
    """Get detailed conversation information including messages"""
    try:
        conversation = await service.get_conversation_details(conversation_id, user_id)
        return conversation
    except Exception as e:
        logger.error(f"Error getting conversation details {conversation_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.get("/conversation/{conversation_id}/messages", response_model=UserMessagesResponse)
async def get_conversation_messages(
    conversation_id: int,
    user_id: Optional[int] = Query(None, description="User ID for access control"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order"),
    message_type: Optional[str] = Query(None, description="Filter by message type"),
    sender_id: Optional[int] = Query(None, description="Filter by sender ID"),
    search_query: Optional[str] = Query(None, description="Search in message content"),
    include_deleted: bool = Query(False, description="Include deleted messages"),
    service: UserHistoryService = Depends(get_user_history_service)
):
    """Get messages for a specific conversation with pagination and filters"""
    try:
        pagination = PaginationParams(
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Convert string parameters to enums
        msg_type_enum = convert_to_enum(message_type, MessageType)
        
        filters = MessageFilters(
            message_type=msg_type_enum,
            sender_id=sender_id,
            search_query=search_query,
            include_deleted=include_deleted
        )
        
        messages = await service.get_messages_for_history(conversation_id, pagination, filters, user_id)
        
        if not messages.success:
            return create_error_response(404, messages.message)
        
        return messages
    except Exception as e:
        logger.error(f"Error getting messages for conversation {conversation_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.post("/user/history", response_model=ConversationCreatedResponse)
async def create_new_chat_history(
    request: NewChatHistoryRequest,
    service: UserHistoryService = Depends(get_user_history_service)
):
    """Create a new chat history/conversation"""
    try:
        new_history = await service.create_chat_history(
            user_id=request.user_id,
            title=request.title,
            conversation_type=request.conversation_type.value,
            description=request.description,
            context_data=request.context_data
        )
        
        if not new_history.success:
            return create_error_response(400, new_history.message)
        
        return new_history
    except Exception as e:
        logger.error(f"Error creating chat history: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.put("/conversation/{conversation_id}/continue", response_model=ConversationResponse)
async def continue_chat_history(
    conversation_id: int,
    user_id: Optional[int] = Query(None, description="User ID for access control"),
    service: UserHistoryService = Depends(get_user_history_service)
):
    """Continue an existing chat history (reactivate if needed)"""
    try:
        updated_history = await service.continue_chat_history(conversation_id, user_id)
        
        if not updated_history.success:
            return create_error_response(404, updated_history.message)
        
        return updated_history
    except Exception as e:
        logger.error(f"Error continuing chat history {conversation_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.post("/conversation/{conversation_id}/messages", response_model=MessageSentResponse)
async def send_message_to_conversation(
    conversation_id: int,
    request: SendMessageRequest,
    service: UserHistoryService = Depends(get_user_history_service)
):
    """Send a message to a conversation"""
    try:
        # Ensure the conversation_id in the path matches the request
        if request.conversation_id != conversation_id:
            return create_error_response(
                400, 
                "Conversation ID in path does not match request body"
            )
        
        message_response = await service.send_message(request)
        
        if not message_response.success:
            return create_error_response(400, message_response.message)
        
        return message_response
    except Exception as e:
        logger.error(f"Error sending message to conversation {conversation_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.put("/conversation/{conversation_id}", response_model=ConversationUpdatedResponse)
async def update_conversation(
    conversation_id: int,
    request: UpdateConversationRequest,
    user_id: Optional[int] = Query(None, description="User ID for access control"),
    service: UserHistoryService = Depends(get_user_history_service)
):
    """Update conversation details"""
    try:
        updated_conversation = await service.update_conversation(conversation_id, request, user_id)
        
        if not updated_conversation.success:
            return create_error_response(404, updated_conversation.message)
        
        return updated_conversation
    except Exception as e:
        logger.error(f"Error updating conversation {conversation_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.put("/conversation/{conversation_id}/archive", response_model=ConversationUpdatedResponse)
async def archive_conversation(
    conversation_id: int,
    user_id: Optional[int] = Query(None, description="User ID for access control"),
    service: UserHistoryService = Depends(get_user_history_service)
):
    """Archive a conversation"""
    try:
        archived_conversation = await service.archive_conversation(conversation_id, user_id)
        
        if not archived_conversation.success:
            return create_error_response(404, archived_conversation.message)
        
        return archived_conversation
    except Exception as e:
        logger.error(f"Error archiving conversation {conversation_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.delete("/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    user_id: Optional[int] = Query(None, description="User ID for access control"),
    service: UserHistoryService = Depends(get_user_history_service)
):
    """Soft delete a conversation and its messages"""
    try:
        result = await service.delete_conversation(conversation_id, user_id)
        
        if not result["success"]:
            return create_error_response(404, result["message"])
        
        return result
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.get("/user-history/health")
async def user_history_health_check():
    """Health check endpoint for user history service"""
    return {"status": "healthy", "service": "user-history-api"}
