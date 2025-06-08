from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, func, and_, or_
from datetime import datetime, timezone

from app.utils.database.db_conn_updated import create_db_manager_from_settings, DatabaseManager
from app.utils.database.ORM_models.orm_tables import User, Conversation, Message
from app.schemas.user_history_schemas import (
    ConversationSummary, ConversationDetail, MessageResponse,
    UserHistoryResponse, UserMessagesResponse, ConversationResponse,
    MessageSentResponse, ConversationCreatedResponse, ConversationUpdatedResponse,
    NewChatHistoryRequest, SendMessageRequest, UpdateConversationRequest,
    PaginationParams, ConversationFilters, MessageFilters
)
from app.config import settings
from app.logger import logger


class UserHistoryService:
    """Service for managing user chat history and conversations"""
    
    def __init__(self):
        self.db_manager: Optional[DatabaseManager] = None
        
    async def initialize(self):
        """Initialize the service"""
        logger.info("Initializing user history service...")
        self.db_manager = create_db_manager_from_settings(settings)
        logger.info("User history service initialized successfully")
    
    async def cleanup(self):
        """Cleanup service resources"""
        if self.db_manager:
            self.db_manager.close()
            logger.info("User history service cleaned up")

    def _get_db_manager(self) -> DatabaseManager:
        """Get database manager, initialize if needed"""
        if not self.db_manager:
            self.db_manager = create_db_manager_from_settings(settings)
        return self.db_manager

    def _build_conversation_summary(self, conversation: Conversation, session: Session) -> ConversationSummary:
        """Build conversation summary with additional computed fields"""
        # Get message count and last message info
        message_count = session.query(Message).filter(
            Message.conversation_id == conversation.id,
            Message.is_deleted == False
        ).count()
        
        last_message = session.query(Message).filter(
            Message.conversation_id == conversation.id,
            Message.is_deleted == False
        ).order_by(desc(Message.created_at)).first()
        
        # Get creator info
        creator = session.query(User).filter(User.id == conversation.created_by).first()
        
        return ConversationSummary(
            id=conversation.id,
            type=conversation.type,
            name=conversation.name,
            description=conversation.description,
            created_by=conversation.created_by,
            conversation_state=conversation.conversation_state,
            context_data=conversation.context_data,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            is_archived=conversation.is_archived,
            message_count=message_count,
            last_message_at=last_message.created_at if last_message else None,
            last_message_preview=last_message.content[:100] + "..." if last_message and len(last_message.content) > 100 else last_message.content if last_message else None,
            creator_username=creator.username if creator else None,
            creator_display_name=creator.display_name if creator else None
        )

    def _build_message_response(self, message: Message, session: Session) -> MessageResponse:
        """Build message response with sender information"""
        sender = session.query(User).filter(User.id == message.sender_id).first()
        
        return MessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            content=message.content,
            message_type=message.message_type,
            reply_to_id=message.reply_to_id,
            thread_id=message.thread_id,
            thread_level=message.thread_level,
            message_metadata=message.message_metadata,
            processing_status=message.processing_status,
            created_at=message.created_at,
            updated_at=message.updated_at,
            is_deleted=message.is_deleted,
            deleted_at=message.deleted_at,
            sender_username=sender.username if sender else None,
            sender_display_name=sender.display_name if sender else None
        )

    async def get_user_history(
        self, 
        user_id: int, 
        pagination: PaginationParams = PaginationParams(),
        filters: ConversationFilters = ConversationFilters()
    ) -> UserHistoryResponse:
        """Get user's conversation history with pagination and filters"""
        try:
            db_manager = self._get_db_manager()
            
            with db_manager.get_session() as session:
                # Verify user exists
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return UserHistoryResponse(
                        success=False,
                        message=f"User with ID {user_id} not found",
                        conversations=[],
                        total_conversations=0
                    )
                
                # Build base query
                query = session.query(Conversation).filter(Conversation.created_by == user_id)
                
                # Apply filters
                if filters.conversation_type:
                    query = query.filter(Conversation.type == filters.conversation_type.value)
                
                if filters.conversation_state:
                    query = query.filter(Conversation.conversation_state == filters.conversation_state.value)
                
                if filters.is_archived is not None:
                    query = query.filter(Conversation.is_archived == filters.is_archived)
                
                if filters.created_after:
                    query = query.filter(Conversation.created_at >= filters.created_after)
                
                if filters.created_before:
                    query = query.filter(Conversation.created_at <= filters.created_before)
                
                if filters.search_query:
                    search = f"%{filters.search_query}%"
                    query = query.filter(
                        or_(
                            Conversation.name.ilike(search),
                            Conversation.description.ilike(search)
                        )
                    )
                
                # Get total count
                total_conversations = query.count()
                
                # Apply sorting
                if pagination.sort_order == "asc":
                    query = query.order_by(asc(getattr(Conversation, pagination.sort_by)))
                else:
                    query = query.order_by(desc(getattr(Conversation, pagination.sort_by)))
                
                # Apply pagination
                conversations = query.offset(
                    (pagination.page - 1) * pagination.per_page
                ).limit(pagination.per_page).all()
                
                # Build response
                conversation_summaries = [
                    self._build_conversation_summary(conv, session) 
                    for conv in conversations
                ]
                
                has_next = (pagination.page * pagination.per_page) < total_conversations
                has_prev = pagination.page > 1
                
                return UserHistoryResponse(
                    success=True,
                    message="User history retrieved successfully",
                    conversations=conversation_summaries,
                    total_conversations=total_conversations,
                    page=pagination.page,
                    per_page=pagination.per_page,
                    has_next=has_next,
                    has_prev=has_prev,
                    data={
                        "user_id": user_id,
                        "username": user.username,
                        "display_name": user.display_name
                    }
                )
                
        except Exception as e:
            logger.error(f"Error getting user history for user {user_id}: {str(e)}")
            return UserHistoryResponse(
                success=False,
                message=f"Failed to retrieve user history: {str(e)}",
                conversations=[],
                total_conversations=0
            )

    async def get_conversation_details(self, conversation_id: int, user_id: Optional[int] = None) -> ConversationResponse:
        """Get detailed conversation information including messages"""
        try:
            db_manager = self._get_db_manager()
            
            with db_manager.get_session() as session:
                # Get conversation
                query = session.query(Conversation).filter(Conversation.id == conversation_id)
                
                # If user_id provided, ensure user has access to this conversation
                if user_id:
                    query = query.filter(Conversation.created_by == user_id)
                
                conversation = query.first()
                if not conversation:
                    return ConversationResponse(
                        success=False,
                        message=f"Conversation with ID {conversation_id} not found or access denied"
                    )
                
                # Get messages for this conversation
                messages = session.query(Message).filter(
                    Message.conversation_id == conversation_id,
                    Message.is_deleted == False
                ).order_by(asc(Message.created_at)).all()
                
                # Build conversation detail
                conversation_summary = self._build_conversation_summary(conversation, session)
                message_responses = [self._build_message_response(msg, session) for msg in messages]
                
                conversation_detail = ConversationDetail(
                    **conversation_summary.dict(),
                    messages=message_responses
                )
                
                return ConversationResponse(
                    success=True,
                    message="Conversation retrieved successfully",
                    data=conversation_detail
                )
                
        except Exception as e:
            logger.error(f"Error getting conversation details {conversation_id}: {str(e)}")
            return ConversationResponse(
                success=False,
                message=f"Failed to retrieve conversation: {str(e)}"
            )

    async def get_messages_for_history(
        self, 
        conversation_id: int, 
        pagination: PaginationParams = PaginationParams(),
        filters: MessageFilters = MessageFilters(),
        user_id: Optional[int] = None
    ) -> UserMessagesResponse:
        """Get messages for a specific conversation with pagination and filters"""
        try:
            db_manager = self._get_db_manager()
            
            with db_manager.get_session() as session:
                # Verify conversation exists and user has access
                conv_query = session.query(Conversation).filter(Conversation.id == conversation_id)
                if user_id:
                    conv_query = conv_query.filter(Conversation.created_by == user_id)
                
                conversation = conv_query.first()
                if not conversation:
                    return UserMessagesResponse(
                        success=False,
                        message=f"Conversation with ID {conversation_id} not found or access denied",
                        conversation_id=conversation_id,
                        messages=[],
                        total_messages=0
                    )
                
                # Build base query
                query = session.query(Message).filter(Message.conversation_id == conversation_id)
                
                # Apply filters
                if not filters.include_deleted:
                    query = query.filter(Message.is_deleted == False)
                
                if filters.message_type:
                    query = query.filter(Message.message_type == filters.message_type.value)
                
                if filters.sender_id:
                    query = query.filter(Message.sender_id == filters.sender_id)
                
                if filters.created_after:
                    query = query.filter(Message.created_at >= filters.created_after)
                
                if filters.created_before:
                    query = query.filter(Message.created_at <= filters.created_before)
                
                if filters.search_query:
                    search = f"%{filters.search_query}%"
                    query = query.filter(Message.content.ilike(search))
                
                # Get total count
                total_messages = query.count()
                
                # Apply sorting
                if pagination.sort_order == "asc":
                    query = query.order_by(asc(getattr(Message, pagination.sort_by)))
                else:
                    query = query.order_by(desc(getattr(Message, pagination.sort_by)))
                
                # Apply pagination
                messages = query.offset(
                    (pagination.page - 1) * pagination.per_page
                ).limit(pagination.per_page).all()
                
                # Build response
                message_responses = [self._build_message_response(msg, session) for msg in messages]
                
                has_next = (pagination.page * pagination.per_page) < total_messages
                has_prev = pagination.page > 1
                
                return UserMessagesResponse(
                    success=True,
                    message="Messages retrieved successfully",
                    conversation_id=conversation_id,
                    messages=message_responses,
                    total_messages=total_messages,
                    page=pagination.page,
                    per_page=pagination.per_page,
                    has_next=has_next,
                    has_prev=has_prev
                )
                
        except Exception as e:
            logger.error(f"Error getting messages for conversation {conversation_id}: {str(e)}")
            return UserMessagesResponse(
                success=False,
                message=f"Failed to retrieve messages: {str(e)}",
                conversation_id=conversation_id,
                messages=[],
                total_messages=0
            )

    async def create_chat_history(self, user_id: int, title: Optional[str] = None, **kwargs) -> ConversationCreatedResponse:
        """Create a new chat history/conversation"""
        try:
            db_manager = self._get_db_manager()
            
            with db_manager.get_session() as session:
                # Verify user exists
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return ConversationCreatedResponse(
                        success=False,
                        message=f"User with ID {user_id} not found"
                    )
                
                # Create new conversation
                conversation = Conversation(
                    type=kwargs.get('conversation_type', 'direct'),
                    name=title or f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                    description=kwargs.get('description'),
                    created_by=user_id,
                    conversation_state='active',
                    context_data=kwargs.get('context_data'),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                
                session.add(conversation)
                session.commit()
                session.refresh(conversation)
                
                # Build response
                conversation_summary = self._build_conversation_summary(conversation, session)
                
                return ConversationCreatedResponse(
                    success=True,
                    message="Conversation created successfully",
                    data=conversation_summary
                )
                
        except Exception as e:
            logger.error(f"Error creating chat history for user {user_id}: {str(e)}")
            return ConversationCreatedResponse(
                success=False,
                message=f"Failed to create conversation: {str(e)}"
            )

    async def continue_chat_history(self, conversation_id: int, user_id: Optional[int] = None) -> ConversationResponse:
        """Continue an existing chat history (reactivate if needed)"""
        try:
            db_manager = self._get_db_manager()
            
            with db_manager.get_session() as session:
                # Get conversation
                query = session.query(Conversation).filter(Conversation.id == conversation_id)
                if user_id:
                    query = query.filter(Conversation.created_by == user_id)
                
                conversation = query.first()
                if not conversation:
                    return ConversationResponse(
                        success=False,
                        message=f"Conversation with ID {conversation_id} not found or access denied"
                    )
                
                # Update conversation state to active if it was paused/archived
                if conversation.conversation_state in ['paused', 'archived']:
                    conversation.conversation_state = 'active'
                    conversation.updated_at = datetime.now(timezone.utc)
                    session.commit()
                
                # Get detailed conversation
                return await self.get_conversation_details(conversation_id, user_id)
                
        except Exception as e:
            logger.error(f"Error continuing chat history {conversation_id}: {str(e)}")
            return ConversationResponse(
                success=False,
                message=f"Failed to continue conversation: {str(e)}"
            )

    async def send_message(self, request: SendMessageRequest) -> MessageSentResponse:
        """Send a message to a conversation"""
        try:
            db_manager = self._get_db_manager()
            
            with db_manager.get_session() as session:
                # Verify conversation exists
                conversation = session.query(Conversation).filter(
                    Conversation.id == request.conversation_id
                ).first()
                if not conversation:
                    return MessageSentResponse(
                        success=False,
                        message=f"Conversation with ID {request.conversation_id} not found"
                    )
                
                # Verify sender exists
                sender = session.query(User).filter(User.id == request.sender_id).first()
                if not sender:
                    return MessageSentResponse(
                        success=False,
                        message=f"User with ID {request.sender_id} not found"
                    )
                
                # Create new message
                message = Message(
                    conversation_id=request.conversation_id,
                    sender_id=request.sender_id,
                    content=request.content,
                    message_type=request.message_type.value,
                    reply_to_id=request.reply_to_id,
                    message_metadata=request.message_metadata,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                
                session.add(message)
                
                # Update conversation updated_at
                conversation.updated_at = datetime.now(timezone.utc)
                
                session.commit()
                session.refresh(message)
                
                # Build response
                message_response = self._build_message_response(message, session)
                
                return MessageSentResponse(
                    success=True,
                    message="Message sent successfully",
                    data=message_response
                )
                
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return MessageSentResponse(
                success=False,
                message=f"Failed to send message: {str(e)}"
            )

    async def update_conversation(
        self, 
        conversation_id: int, 
        updates: UpdateConversationRequest,
        user_id: Optional[int] = None
    ) -> ConversationUpdatedResponse:
        """Update conversation details"""
        try:
            db_manager = self._get_db_manager()
            
            with db_manager.get_session() as session:
                # Get conversation
                query = session.query(Conversation).filter(Conversation.id == conversation_id)
                if user_id:
                    query = query.filter(Conversation.created_by == user_id)
                
                conversation = query.first()
                if not conversation:
                    return ConversationUpdatedResponse(
                        success=False,
                        message=f"Conversation with ID {conversation_id} not found or access denied"
                    )
                
                # Apply updates
                if updates.name is not None:
                    conversation.name = updates.name
                
                if updates.description is not None:
                    conversation.description = updates.description
                
                if updates.conversation_state is not None:
                    conversation.conversation_state = updates.conversation_state.value
                
                if updates.context_data is not None:
                    conversation.context_data = updates.context_data
                
                conversation.updated_at = datetime.now(timezone.utc)
                session.commit()
                
                # Build response
                conversation_summary = self._build_conversation_summary(conversation, session)
                
                return ConversationUpdatedResponse(
                    success=True,
                    message="Conversation updated successfully",
                    data=conversation_summary
                )
                
        except Exception as e:
            logger.error(f"Error updating conversation {conversation_id}: {str(e)}")
            return ConversationUpdatedResponse(
                success=False,
                message=f"Failed to update conversation: {str(e)}"
            )

    async def archive_conversation(self, conversation_id: int, user_id: Optional[int] = None) -> ConversationUpdatedResponse:
        """Archive a conversation"""
        return await self.update_conversation(
            conversation_id, 
            UpdateConversationRequest(is_archived=True, conversation_state="archived"),
            user_id
        )

    async def delete_conversation(self, conversation_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Soft delete a conversation and its messages"""
        try:
            db_manager = self._get_db_manager()
            
            with db_manager.get_session() as session:
                # Get conversation
                query = session.query(Conversation).filter(Conversation.id == conversation_id)
                if user_id:
                    query = query.filter(Conversation.created_by == user_id)
                
                conversation = query.first()
                if not conversation:
                    return {
                        "success": False,
                        "message": f"Conversation with ID {conversation_id} not found or access denied"
                    }
                
                # Soft delete all messages in conversation
                session.query(Message).filter(
                    Message.conversation_id == conversation_id,
                    Message.is_deleted == False
                ).update({
                    "is_deleted": True,
                    "deleted_at": datetime.now(timezone.utc)
                })
                
                # Archive the conversation
                conversation.is_archived = True
                conversation.conversation_state = "archived"
                conversation.updated_at = datetime.now(timezone.utc)
                
                session.commit()
                
                return {
                    "success": True,
                    "message": "Conversation deleted successfully"
                }
                
        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to delete conversation: {str(e)}"
            }
