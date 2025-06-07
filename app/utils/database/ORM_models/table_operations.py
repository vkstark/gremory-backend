# from app.utils.database.ORM_models.orm_tables import (Base, User, Conversation, Message, 
#                                                       UserSession, FunctionCallLog, EntityExtraction, 
#                                                       MessageNLPAnalysis, UserPreference, UserConsentRecord,
#                                                       SessionStateSnapshot, 
#                                                     )

# from sqlalchemy import func
# from sqlalchemy.orm import Session
# from typing import List, Dict, Any, Optional
# from sqlalchemy.ext.declarative import declarative_base

# # Base class for SQLAlchemy ORM models
# Base = declarative_base()

# # Utility functions for common operations
# class ChatbotORM:
#     """Utility class with common database operations for the chatbot."""
    
#     def __init__(self, session):
#         self.session = session
    
#     def create_user(self, user_type: str, **kwargs) -> User:
#         """Create a new user with the specified type and attributes."""
#         user = User(user_type=user_type, **kwargs)
#         self.session.add(user)
#         self.session.flush()  # Get the ID without committing
#         return user
    
#     def create_conversation(self, creator_id: int, conversation_type: str, **kwargs) -> Conversation:
#         """Create a new conversation."""
#         conversation = Conversation(
#             created_by=creator_id,
#             type=conversation_type,
#             **kwargs
#         )
#         self.session.add(conversation)
#         self.session.flush()
#         return conversation
    
#     def add_message(self, conversation_id: int, sender_id: int, content: str, **kwargs) -> Message:
#         """Add a message to a conversation."""
#         message = Message(
#             conversation_id=conversation_id,
#             sender_id=sender_id,
#             content=content,
#             **kwargs
#         )
#         self.session.add(message)
#         self.session.flush()
#         return message
    
#     def log_function_call(self, user_id: int, session_id: int, function_name: str, 
#                          input_params: Dict[str, Any], **kwargs) -> FunctionCallLog:
#         """Log a function call with its parameters."""
#         function_call = FunctionCallLog(
#             user_id=user_id,
#             session_id=session_id,
#             function_name=function_name,
#             input_parameters=input_params,
#             **kwargs
#         )
#         self.session.add(function_call)
#         self.session.flush()
#         return function_call
    
#     def get_user_preferences(self, user_id: int, category: Optional[str] = None) -> List[UserPreference]:
#         """Get user preferences, optionally filtered by category."""
#         query = self.session.query(UserPreference).filter(UserPreference.user_id == user_id)
#         if category:
#             query = query.filter(UserPreference.category == category)
#         return query.all()
    
#     def get_conversation_history(self, conversation_id: int, limit: int = 50) -> List[Message]:
#         """Get recent messages from a conversation."""
#         return (self.session.query(Message)
#                 .filter(Message.conversation_id == conversation_id)
#                 .filter(Message.is_deleted == False)
#                 .order_by(Message.created_at.desc())
#                 .limit(limit)
#                 .all())
    
#     def update_user_activity(self, user_id: int, session_id: int):
#         """Update user's last activity timestamp."""
#         self.session.query(UserSession).filter(
#             UserSession.id == session_id,
#             UserSession.user_id == user_id
#         ).update({
#             'last_activity': func.now()
#         })
    
#     def search_messages(self, query: str, conversation_id: Optional[int] = None) -> List[Message]:
#         """Search messages using full-text search."""
#         search_query = self.session.query(Message).filter(
#             Message.content.op('@@')(func.to_tsquery('english', query))
#         )
#         if conversation_id:
#             search_query = search_query.filter(Message.conversation_id == conversation_id)
#         return search_query.all()


# # Database configuration and engine setup
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from sqlalchemy.pool import QueuePool
# import os

# class DatabaseConfig:
#     """Database configuration and session management."""
    
#     def __init__(self, database_url: Optional[str] = None):
#         if database_url is None:
#             database_url = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/chatbot_db')
        
#         # Engine configuration optimized for chatbot workloads
#         self.engine = create_engine(
#             database_url,
#             # Connection pool settings
#             poolclass=QueuePool,
#             pool_size=20,  # Base number of connections
#             max_overflow=30,  # Additional connections when needed
#             pool_pre_ping=True,  # Verify connections before use
#             pool_recycle=3600,  # Recycle connections every hour
            
#             # Performance settings
#             echo=False,  # Set to True for SQL debugging
#             future=True,  # Use SQLAlchemy 2.0 style
            
#             # PostgreSQL specific optimizations
#             connect_args={
#                 "options": "-c timezone=utc",
#                 "application_name": "chatbot_app",
#                 "connect_timeout": 10,
#             }
#         )
        
#         # Session factory
#         self.SessionLocal = sessionmaker(
#             bind=self.engine,
#             autocommit=False,
#             autoflush=False,
#             expire_on_commit=False
#         )
    
#     def create_tables(self):
#         """Create all tables in the database."""
#         Base.metadata.create_all(bind=self.engine)
    
#     def drop_tables(self):
#         """Drop all tables in the database."""
#         Base.metadata.drop_all(bind=self.engine)
    
#     def get_session(self):
#         """Get a database session."""
#         return self.SessionLocal()
    
#     def get_chatbot_orm(self):
#         """Get a ChatbotORM instance with a session."""
#         session = self.get_session()
#         return ChatbotORM(session), session


# # Advanced query helpers and utilities
# from sqlalchemy.orm import Query
# from sqlalchemy import and_, or_, desc, asc
# from datetime import datetime, timedelta

# class ChatbotQueries:
#     """Advanced query methods for chatbot operations."""
    
#     def __init__(self, session):
#         self.session = session
    
#     def get_active_sessions(self, user_id: int) -> List[UserSession]:
#         """Get all active sessions for a user."""
#         return (self.session.query(UserSession)
#                 .filter(UserSession.user_id == user_id)
#                 .filter(UserSession.is_active == True)
#                 .filter(UserSession.expires_at > func.now())
#                 .all())
    
#     def get_conversation_participants(self, conversation_id: int) -> List[User]:
#         """Get all users who have participated in a conversation."""
#         return (self.session.query(User)
#                 .join(Message, User.id == Message.sender_id)
#                 .filter(Message.conversation_id == conversation_id)
#                 .distinct()
#                 .all())
    
#     def get_user_message_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
#         """Get message statistics for a user over the specified period."""
#         start_date = datetime.utcnow() - timedelta(days=days)
        
#         # Total messages
#         total_messages = (self.session.query(Message)
#                          .filter(Message.sender_id == user_id)
#                          .filter(Message.created_at >= start_date)
#                          .count())
        
#         # Messages by type
#         message_types = (self.session.query(Message.message_type, func.count(Message.id))
#                         .filter(Message.sender_id == user_id)
#                         .filter(Message.created_at >= start_date)
#                         .group_by(Message.message_type)
#                         .all())
        
#         # Average sentiment (if available)
#         avg_sentiment = (self.session.query(func.avg(MessageNLPAnalysis.sentiment_score))
#                         .join(Message, MessageNLPAnalysis.message_id == Message.id)
#                         .filter(Message.sender_id == user_id)
#                         .filter(Message.created_at >= start_date)
#                         .scalar())
        
#         return {
#             'total_messages': total_messages,
#             'message_types': dict(message_types),
#             'average_sentiment': float(avg_sentiment) if avg_sentiment else None,
#             'period_days': days
#         }
    
#     def get_conversation_analytics(self, conversation_id: int) -> Dict[str, Any]:
#         """Get comprehensive analytics for a conversation."""
#         # Basic stats
#         total_messages = (self.session.query(Message)
#                          .filter(Message.conversation_id == conversation_id)
#                          .count())
        
#         participants = (self.session.query(func.count(func.distinct(Message.sender_id)))
#                        .filter(Message.conversation_id == conversation_id)
#                        .scalar())
        
#         # Time range
#         time_range = (self.session.query(
#                         func.min(Message.created_at),
#                         func.max(Message.created_at)
#                      )
#                      .filter(Message.conversation_id == conversation_id)
#                      .first())
        
#         # Function calls in this conversation
#         function_calls = (self.session.query(func.count(FunctionCallLog.id))
#                          .filter(FunctionCallLog.conversation_id == conversation_id)
#                          .scalar())
        
#         # Most active participants
#         active_participants = (self.session.query(
#                                  User.display_name,
#                                  func.count(Message.id).label('message_count')
#                               )
#                               .join(Message, User.id == Message.sender_id)
#                               .filter(Message.conversation_id == conversation_id)
#                               .group_by(User.id, User.display_name)
#                               .order_by(desc('message_count'))
#                               .limit(5)
#                               .all())
        
#         return {
#             'total_messages': total_messages,
#             'participants': participants,
#             'start_time': time_range[0],
#             'end_time': time_range[1],
#             'function_calls': function_calls,
#             'top_participants': [
#                 {'name': name, 'message_count': count} 
#                 for name, count in active_participants
#             ]
#         }
    
#     def get_trending_topics(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
#         """Get trending topics based on entity extraction."""
#         start_date = datetime.utcnow() - timedelta(days=days)
        
#         trending = (self.session.query(
#                       EntityExtraction.entity_value,
#                       EntityExtraction.entity_type,
#                       func.count(EntityExtraction.id).label('frequency'),
#                       func.avg(EntityExtraction.confidence_score).label('avg_confidence')
#                    )
#                    .join(Message, EntityExtraction.message_id == Message.id)
#                    .filter(Message.created_at >= start_date)
#                    .filter(EntityExtraction.confidence_score > 0.7)
#                    .group_by(EntityExtraction.entity_value, EntityExtraction.entity_type)
#                    .order_by(desc('frequency'))
#                    .limit(limit)
#                    .all())
        
#         return [
#             {
#                 'entity': entity,
#                 'type': entity_type,
#                 'frequency': freq,
#                 'confidence': float(conf)
#             }
#             for entity, entity_type, freq, conf in trending
#         ]
    
#     def get_function_performance_summary(self, days: int = 30) -> List[Dict[str, Any]]:
#         """Get performance summary for all functions."""
#         start_date = datetime.utcnow() - timedelta(days=days)
        
#         performance = (self.session.query(
#                          FunctionCallLog.function_name,
#                          func.count(FunctionCallLog.id).label('call_count'),
#                          func.avg(FunctionCallLog.execution_duration_ms).label('avg_duration'),
#                          func.sum(
#                              func.case(
#                                  (FunctionCallLog.error_details.is_(None), 1),
#                                  else_=0
#                              )
#                          ).label('success_count')
#                       )
#                       .filter(FunctionCallLog.execution_start_time >= start_date)
#                       .group_by(FunctionCallLog.function_name)
#                       .all())
        
#         return [
#             {
#                 'function_name': name,
#                 'call_count': count,
#                 'avg_duration_ms': float(avg_dur) if avg_dur else 0,
#                 'success_rate': (success / count) * 100 if count > 0 else 0
#             }
#             for name, count, avg_dur, success in performance
#         ]
    
#     def cleanup_expired_sessions(self) -> int:
#         """Clean up expired sessions and return count of deleted sessions."""
#         deleted = (self.session.query(UserSession)
#                   .filter(UserSession.expires_at < func.now())
#                   .delete())
#         self.session.commit()
#         return deleted
    
#     def cleanup_old_snapshots(self, retention_days: int = 30) -> int:
#         """Clean up old session snapshots beyond retention period."""
#         cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
#         deleted = (self.session.query(SessionStateSnapshot)
#                   .filter(SessionStateSnapshot.snapshot_timestamp < cutoff_date)
#                   .delete())
#         self.session.commit()
#         return deleted
    
#     def get_user_consent_status(self, user_id: int) -> Dict[str, bool]:
#         """Get current consent status for all consent types for a user."""
#         consents = (self.session.query(UserConsentRecord)
#                    .filter(UserConsentRecord.user_id == user_id)
#                    .filter(UserConsentRecord.withdrawal_timestamp.is_(None))
#                    .all())
        
#         consent_status = {}
#         for consent in consents:
#             consent_status[consent.consent_type] = consent.consent_status
        
#         return consent_status
    
#     def update_user_preference(self, user_id: int, category: str, 
#                               preference_key: str, preference_value: Any) -> UserPreference:
#         """Update or create a user preference."""
#         existing = (self.session.query(UserPreference)
#                    .filter(UserPreference.user_id == user_id)
#                    .filter(UserPreference.category == category)
#                    .filter(UserPreference.preference_key == preference_key)
#                    .first())
        
#         if existing:
#             existing.preference_value = preference_value
#             existing.updated_at = func.now()
#             return existing
#         else:
#             new_pref = UserPreference(
#                 user_id=user_id,
#                 category=category,
#                 preference_key=preference_key,
#                 preference_value=preference_value
#             )
#             self.session.add(new_pref)
#             return new_pref
# # Example usage and testing utilities
# def example_usage():
#     """Example of how to use the ChatbotORM classes."""
    
#     # Initialize database
#     db_config = DatabaseConfig("postgresql://user:password@localhost/chatbot_db")
#     db_config.create_tables()
    
#     # Get ORM instance
#     chatbot_orm, session = db_config.get_chatbot_orm()
    
#     try:
#         # Create a user
#         user = chatbot_orm.create_user(
#             user_type="registered",
#             username="john_doe",
#             email="john@example.com",
#             display_name="John Doe"
#         )
        
#         # Flush to get the user ID
#         session.flush()
#         session.commit()  # Commit to get the actual ID value
        
#         # Refresh to get the actual ID value
#         session.refresh(user)
        
#         # Create a conversation
#         conversation = chatbot_orm.create_conversation(
#             creator_id=user.id,
#             conversation_type="direct",
#             name="Test Conversation"
#         )
        
#         # Add messages
#         message1 = chatbot_orm.add_message(
#             conversation_id=conversation.id,
#             sender_id=user.id,
#             content="Hello, this is a test message!"
#         )
        
#         # Log a function call
#         function_call = chatbot_orm.log_function_call(
#             user_id=user.id,
#             session_id=1,  # Assuming session exists
#             function_name="weather_lookup",
#             input_params={"location": "New York", "days": 7}
#         )
        
#         # Get conversation history
#         history = chatbot_orm.get_conversation_history(conversation.id)
#         print(f"Found {len(history)} messages in conversation")
        
#         # Commit changes
#         session.commit()
        
#     except Exception as e:
#         session.rollback()
#         print(f"Error: {e}")
#     finally:
#         session.close()


# if __name__ == "__main__":
#     example_usage()