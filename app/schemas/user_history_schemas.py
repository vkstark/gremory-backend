from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ConversationType(str, Enum):
    DIRECT = "direct"
    GROUP = "group"
    SUPPORT = "support"
    BOT = "bot"


class ConversationState(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"
    AI_RESPONSE = "ai_response"


# Request schemas
class NewChatHistoryRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user creating the chat")
    title: Optional[str] = Field(default=None, description="Optional title for the conversation")
    conversation_type: ConversationType = Field(default=ConversationType.DIRECT, description="Type of conversation")
    description: Optional[str] = Field(default=None, description="Optional description")
    context_data: Optional[Dict[str, Any]] = Field(default=None, description="Optional context data")


class ContinueChatRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user continuing the chat")


class SendMessageRequest(BaseModel):
    conversation_id: int = Field(..., description="ID of the conversation")
    sender_id: int = Field(..., description="ID of the message sender")
    content: str = Field(..., description="Message content")
    message_type: MessageType = Field(MessageType.TEXT, description="Type of message")
    reply_to_id: Optional[int] = Field(None, description="ID of message being replied to")
    message_metadata: Optional[Dict[str, Any]] = Field(None, description="Optional message metadata")


class UpdateConversationRequest(BaseModel):
    name: Optional[str] = Field(None, description="Updated conversation name")
    description: Optional[str] = Field(None, description="Updated conversation description")
    conversation_state: Optional[ConversationState] = Field(None, description="Updated conversation state")
    context_data: Optional[Dict[str, Any]] = Field(None, description="Updated context data")


# Response schemas
class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    content: str
    message_type: str
    reply_to_id: Optional[int] = None
    thread_id: Optional[int] = None
    thread_level: int = 0
    message_metadata: Optional[Dict[str, Any]] = None
    processing_status: str = "processed"
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    
    # Sender information
    sender_username: Optional[str] = None
    sender_display_name: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    id: int
    type: str
    name: Optional[str] = None
    description: Optional[str] = None
    created_by: int
    conversation_state: str = "active"
    context_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    is_archived: bool = False
    
    # Additional computed fields
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    
    # Creator information
    creator_username: Optional[str] = None
    creator_display_name: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationDetail(ConversationSummary):
    messages: List[MessageResponse] = []


class UserHistoryResponse(BaseModel):
    success: bool = True
    message: str = "User history retrieved successfully"
    data: Dict[str, Any] = Field(default_factory=dict)
    conversations: List[ConversationSummary] = []
    total_conversations: int = 0
    page: int = 1
    per_page: int = 20
    has_next: bool = False
    has_prev: bool = False


class ConversationResponse(BaseModel):
    success: bool = True
    message: str = "Conversation retrieved successfully"
    data: Optional[ConversationDetail] = None


class UserMessagesResponse(BaseModel):
    success: bool = True
    message: str = "Messages retrieved successfully"
    conversation_id: int
    messages: List[MessageResponse] = []
    total_messages: int = 0
    page: int = 1
    per_page: int = 50
    has_next: bool = False
    has_prev: bool = False


class MessageSentResponse(BaseModel):
    success: bool = True
    message: str = "Message sent successfully"
    data: Optional[MessageResponse] = None


class ConversationCreatedResponse(BaseModel):
    success: bool = True
    message: str = "Conversation created successfully"
    data: Optional[ConversationSummary] = None


class ConversationUpdatedResponse(BaseModel):
    success: bool = True
    message: str = "Conversation updated successfully"
    data: Optional[ConversationSummary] = None


# Error response schema
class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# Pagination schema for reusability
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field("created_at", description="Field to sort by")
    sort_order: Optional[str] = Field("desc", pattern=r"^(asc|desc)$", description="Sort order")


# Filter schemas
class ConversationFilters(BaseModel):
    conversation_type: Optional[ConversationType] = None
    conversation_state: Optional[ConversationState] = None
    is_archived: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    search_query: Optional[str] = Field(None, description="Search in conversation name and description")


class MessageFilters(BaseModel):
    message_type: Optional[MessageType] = None
    sender_id: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    search_query: Optional[str] = Field(None, description="Search in message content")
    include_deleted: bool = Field(False, description="Include deleted messages")