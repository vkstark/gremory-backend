from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, 
    Numeric, ForeignKey, Index, UUID, LargeBinary, Interval,
    func, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import INET
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_type = Column(String(20), nullable=False)  # 'registered', 'guest', 'bot'
    username = Column(String(50), unique=True)
    email = Column(String(100), unique=True)
    phone_number = Column(String(20))
    password_hash = Column(String(255))  # NULL for guests
    guest_session_id = Column(String(255))  # for guest continuity
    profile_picture_url = Column(String(500))
    display_name = Column(String(100))
    status = Column(String(20), default='active')
    timezone = Column(String(50))
    language_preference = Column(String(10), default='en')
    last_seen = Column(DateTime)
    registration_completed_at = Column(DateTime)
    guest_expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    conversations_created = relationship("Conversation", back_populates="creator")
    messages = relationship("Message", back_populates="sender")
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    function_calls = relationship("FunctionCallLog", back_populates="user")
    behavior_profile = relationship("UserBehaviorProfile", back_populates="user", uselist=False)
    authentication_methods = relationship("UserAuthentication", back_populates="user", cascade="all, delete-orphan")
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan", foreign_keys="UserPermission.user_id")
    consent_records = relationship("UserConsentRecord", back_populates="user", cascade="all, delete-orphan")
    data_processing_logs = relationship("DataProcessingLog", back_populates="user", cascade="all, delete-orphan")
    encrypted_messages = relationship("EncryptedMessage", back_populates="sender")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', type='{self.user_type}')>"


class UserSession(Base):
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    session_token = Column(String(255), unique=True)
    session_type = Column(String(20))  # 'web', 'mobile', 'api'
    device_metadata = Column(JSONB)
    ip_address = Column(INET)
    geographic_context = Column(JSONB)
    is_active = Column(Boolean, default=True)
    concurrent_session_group = Column(String(100))  # for multi-device sync
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    last_activity = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    function_calls = relationship("FunctionCallLog", back_populates="session")
    state_snapshots = relationship("SessionStateSnapshot", back_populates="session", cascade="all, delete-orphan")
    primary_syncs = relationship("CrossDeviceSessionSync", foreign_keys="CrossDeviceSessionSync.primary_session_id", back_populates="primary_session")
    secondary_syncs = relationship("CrossDeviceSessionSync", foreign_keys="CrossDeviceSessionSync.secondary_session_id", back_populates="secondary_session")
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, type='{self.session_type}')>"


class Conversation(Base):
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False)  # 'direct', 'group', 'support', 'bot'
    name = Column(String(100))
    description = Column(Text)
    created_by = Column(Integer, ForeignKey('users.id'))
    conversation_state = Column(String(20), default='active')
    context_data = Column(JSONB)  # for conversation-specific settings
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_archived = Column(Boolean, default=False)
    
    # Relationships
    creator = relationship("User", back_populates="conversations_created")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    function_calls = relationship("FunctionCallLog", back_populates="conversation")
    contexts = relationship("ConversationContext", back_populates="conversation", cascade="all, delete-orphan")
    encrypted_messages = relationship("EncryptedMessage", back_populates="conversation")
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, type='{self.type}', name='{self.name}')>"

class Message(Base):
    __tablename__ = 'messages'
    
    # Fix: Add autoincrement=True to the primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    content = Column(Text)
    message_type = Column(String(20), default='text')
    reply_to_id = Column(BigInteger, ForeignKey('messages.id'))
    thread_id = Column(BigInteger, ForeignKey('messages.id'))
    thread_level = Column(Integer, default=0)
    message_metadata = Column(JSONB)
    processing_status = Column(String(20), default='processed')
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="messages")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")
    nlp_analysis = relationship("MessageNLPAnalysis", back_populates="message", uselist=False, cascade="all, delete-orphan")
    intent_recognition = relationship("IntentRecognition", back_populates="message", uselist=False, cascade="all, delete-orphan")
    entity_extractions = relationship("EntityExtraction", back_populates="message", cascade="all, delete-orphan")
    
    # Self-referential relationships for threading
    replies = relationship("Message", foreign_keys=[reply_to_id], remote_side=[id], backref="reply_to")
    thread_messages = relationship("Message", foreign_keys=[thread_id], remote_side=[id], backref="thread_parent")
    
    # Indexes
    __table_args__ = (
        Index('idx_messages_conversation_time', 'conversation_id', 'created_at'),
        Index('idx_messages_sender_time', 'sender_id', 'created_at'),
        Index('idx_messages_thread', 'thread_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, sender_id={self.sender_id}, type='{self.message_type}')>"


class UserPreference(Base):
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    category = Column(String(50))  # 'communication_style', 'content_type', 'privacy'
    preference_key = Column(String(100))
    preference_value = Column(JSONB)
    priority_weight = Column(Integer, default=1)  # for conflict resolution
    context_tags = Column(JSONB)  # conditional preferences
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="preferences")
    
    def __repr__(self):
        return f"<UserPreference(id={self.id}, user_id={self.user_id}, key='{self.preference_key}')>"


class MessageAttachment(Base):
    __tablename__ = 'message_attachments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, ForeignKey('messages.id', ondelete='CASCADE'))
    file_url = Column(String(500))
    file_type = Column(String(50))
    file_size = Column(BigInteger)
    file_name = Column(String(255))
    thumbnail_url = Column(String(500))
    encryption_metadata = Column(JSONB)  # for E2E encrypted files
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    message = relationship("Message", back_populates="attachments")
    
    def __repr__(self):
        return f"<MessageAttachment(id={self.id}, message_id={self.message_id}, file_name='{self.file_name}')>"


class CrossDeviceSessionSync(Base):
    __tablename__ = 'cross_device_session_sync'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    primary_session_id = Column(Integer, ForeignKey('user_sessions.id'))
    secondary_session_id = Column(Integer, ForeignKey('user_sessions.id'))
    sync_status = Column(String(20), default='active')
    sync_type = Column(String(20))  # 'real-time', 'periodic', 'on-demand'
    data_synchronization_rules = Column(JSONB)
    last_sync_timestamp = Column(DateTime)
    conflict_resolution_strategy = Column(String(50))
    
    # Relationships
    primary_session = relationship("UserSession", foreign_keys=[primary_session_id], back_populates="primary_syncs")
    secondary_session = relationship("UserSession", foreign_keys=[secondary_session_id], back_populates="secondary_syncs")
    
    def __repr__(self):
        return f"<CrossDeviceSessionSync(id={self.id}, primary={self.primary_session_id}, secondary={self.secondary_session_id})>"


class SessionStateSnapshot(Base):
    __tablename__ = 'session_state_snapshots'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('user_sessions.id'))
    snapshot_timestamp = Column(DateTime, default=func.now())
    conversation_state = Column(JSONB)  # compressed state data
    user_context_variables = Column(JSONB)
    active_workflows = Column(JSONB)
    rollback_compatibility_version = Column(String(10))
    
    # Relationships
    session = relationship("UserSession", back_populates="state_snapshots")
    
    def __repr__(self):
        return f"<SessionStateSnapshot(id={self.id}, session_id={self.session_id})>"


class MessageNLPAnalysis(Base):
    __tablename__ = 'message_nlp_analysis'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, ForeignKey('messages.id', ondelete='CASCADE'))
    sentiment_score = Column(Numeric(3, 2))  # -1.0 to 1.0
    sentiment_confidence = Column(Numeric(3, 2))
    detected_language = Column(String(10))
    toxicity_score = Column(Numeric(3, 2))
    emotional_indicators = Column(JSONB)  # multiple emotion scores
    complexity_metrics = Column(JSONB)  # reading level, technical depth
    
    # Relationships
    message = relationship("Message", back_populates="nlp_analysis")
    
    def __repr__(self):
        return f"<MessageNLPAnalysis(id={self.id}, message_id={self.message_id}, sentiment={self.sentiment_score})>"


class IntentRecognition(Base):
    __tablename__ = 'intent_recognition'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, ForeignKey('messages.id', ondelete='CASCADE'))
    primary_intent = Column(String(100))
    intent_confidence = Column(Numeric(3, 2))
    secondary_intents = Column(JSONB)  # array for multi-intent messages
    intent_category = Column(String(50))
    user_goal_progression = Column(JSONB)
    intent_fulfillment_status = Column(String(20))
    
    # Relationships
    message = relationship("Message", back_populates="intent_recognition")
    
    def __repr__(self):
        return f"<IntentRecognition(id={self.id}, message_id={self.message_id}, intent='{self.primary_intent}')>"


class EntityExtraction(Base):
    __tablename__ = 'entity_extraction'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, ForeignKey('messages.id', ondelete='CASCADE'))
    entity_type = Column(String(50))
    entity_value = Column(Text)
    entity_category = Column(String(50))
    confidence_score = Column(Numeric(3, 2))
    start_position = Column(Integer)
    end_position = Column(Integer)
    canonical_form = Column(String(255))
    aliases = Column(JSONB)
    relationship_to_other_entities = Column(JSONB)
    
    # Relationships
    message = relationship("Message", back_populates="entity_extractions")
    
    def __repr__(self):
        return f"<EntityExtraction(id={self.id}, message_id={self.message_id}, type='{self.entity_type}')>"


class FunctionCallLog(Base):
    __tablename__ = 'function_call_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(Integer, ForeignKey('user_sessions.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    conversation_id = Column(Integer, ForeignKey('conversations.id'))
    function_name = Column(String(100))
    function_category = Column(String(50))
    input_parameters = Column(JSONB)
    output_response = Column(JSONB)
    execution_start_time = Column(DateTime, default=func.now())
    execution_end_time = Column(DateTime)
    execution_duration_ms = Column(Integer)
    call_chain_id = Column(UUID(as_uuid=True))  # for multi-step sequences
    security_context = Column(JSONB)
    cost_tracking = Column(JSONB)  # API costs, compute resources
    error_details = Column(JSONB)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    session = relationship("UserSession", back_populates="function_calls")
    user = relationship("User", back_populates="function_calls")
    conversation = relationship("Conversation", back_populates="function_calls")
    execution_pipeline = relationship("FunctionExecutionPipeline", back_populates="parent_call", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_function_calls_time_function', 'execution_start_time', 'function_name'),
    )
    
    def __repr__(self):
        return f"<FunctionCallLog(id={self.id}, function='{self.function_name}', user_id={self.user_id})>"


class FunctionExecutionPipeline(Base):
    __tablename__ = 'function_execution_pipeline'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_call_id = Column(UUID(as_uuid=True), ForeignKey('function_call_logs.id'))
    step_sequence = Column(Integer)
    step_type = Column(String(50))
    step_input = Column(JSONB)
    step_output = Column(JSONB)
    execution_time_ms = Column(Integer)
    memory_usage_mb = Column(Integer)
    dependency_resolution = Column(JSONB)  # external APIs called
    
    # Relationships
    parent_call = relationship("FunctionCallLog", back_populates="execution_pipeline")
    
    def __repr__(self):
        return f"<FunctionExecutionPipeline(id={self.id}, parent_call_id={self.parent_call_id}, step={self.step_sequence})>"


class APICallMetrics(Base):
    __tablename__ = 'api_call_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_endpoint = Column(String(255))
    http_method = Column(String(10))
    response_time_percentiles = Column(JSONB)  # p50, p95, p99
    success_rate = Column(Numeric(5, 4))
    error_rate_by_type = Column(JSONB)
    throughput_metrics = Column(JSONB)
    geographic_distribution = Column(JSONB)
    time_bucket = Column(DateTime)  # for time-series analysis
    
    def __repr__(self):
        return f"<APICallMetrics(id={self.id}, endpoint='{self.api_endpoint}', method='{self.http_method}')>"


class FunctionPerformanceAnalytics(Base):
    __tablename__ = 'function_performance_analytics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    function_name = Column(String(100))
    time_period = Column(String(20))  # 'hourly', 'daily', 'weekly'
    usage_frequency = Column(Integer)
    success_patterns = Column(JSONB)
    user_satisfaction_correlation = Column(Numeric(3, 2))
    business_impact_metrics = Column(JSONB)
    optimization_recommendations = Column(Text)
    
    def __repr__(self):
        return f"<FunctionPerformanceAnalytics(id={self.id}, function='{self.function_name}', period='{self.time_period}')>"


class UserBehaviorProfile(Base):
    __tablename__ = 'user_behavior_profiles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    interaction_patterns = Column(JSONB)  # usage frequency, peak times
    preference_evolution = Column(JSONB)  # historical changes
    personality_indicators = Column(JSONB)  # communication style markers
    domain_expertise_levels = Column(JSONB)  # competency mapping
    learning_style_preferences = Column(JSONB)
    communication_formality_level = Column(String(20))
    response_length_preference = Column(String(20))
    topic_interests = Column(JSONB)  # weighted interest scores
    behavioral_segments = Column(JSONB)  # segment memberships
    last_updated = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="behavior_profile")
    
    def __repr__(self):
        return f"<UserBehaviorProfile(id={self.id}, user_id={self.user_id})>"


class ConversationContext(Base):
    __tablename__ = 'conversation_contexts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'))
    context_type = Column(String(50))  # 'topic', 'mood', 'urgency', 'domain'
    context_data = Column(JSONB)
    context_priority = Column(Integer)  # for resolution conflicts
    context_lifetime = Column(String(20))  # 'message', 'conversation', 'session'
    inheritance_rules = Column(JSONB)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="contexts")
    
    def __repr__(self):
        return f"<ConversationContext(id={self.id}, conversation_id={self.conversation_id}, type='{self.context_type}')>"


class UserAuthentication(Base):
    __tablename__ = 'user_authentication'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    auth_type = Column(String(20))  # 'password', 'oauth', 'mfa', 'biometric'
    auth_data = Column(JSONB)  # encrypted credentials
    is_primary = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="authentication_methods")
    
    def __repr__(self):
        return f"<UserAuthentication(id={self.id}, user_id={self.user_id}, type='{self.auth_type}')>"


class UserPermission(Base):
    __tablename__ = 'user_permissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    resource_type = Column(String(50))  # 'conversation', 'message', 'user_data'
    resource_id = Column(String(100))
    permission_type = Column(String(20))  # 'read', 'write', 'admin'
    granted_by = Column(Integer, ForeignKey('users.id'))
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="permissions", foreign_keys=[user_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by])
    
    def __repr__(self):
        return f"<UserPermission(id={self.id}, user_id={self.user_id}, resource='{self.resource_type}')>"


class UserConsentRecord(Base):
    __tablename__ = 'user_consent_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    consent_type = Column(String(50))  # 'analytics', 'personalization', 'marketing'
    consent_status = Column(Boolean)
    consent_timestamp = Column(DateTime, default=func.now())
    consent_mechanism = Column(String(50))  # 'explicit', 'implicit', 'updated'
    legal_basis = Column(String(50))  # 'consent', 'contract', 'legitimate_interest'
    withdrawal_timestamp = Column(DateTime)
    data_retention_period = Column(Interval)
    
    # Relationships
    user = relationship("User", back_populates="consent_records")
    
    def __repr__(self):
        return f"<UserConsentRecord(id={self.id}, user_id={self.user_id}, type='{self.consent_type}')>"


class DataProcessingLog(Base):
    __tablename__ = 'data_processing_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    processing_activity = Column(String(100))
    data_categories = Column(JSONB)  # types of data processed
    processing_purpose = Column(String(100))
    legal_basis = Column(String(50))
    data_retention_applied = Column(Boolean)
    automated_decision_making = Column(Boolean)
    processing_timestamp = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="data_processing_logs")
    
    def __repr__(self):
        return f"<DataProcessingLog(id={self.id}, user_id={self.user_id}, activity='{self.processing_activity}')>"


class EncryptionKey(Base):
    __tablename__ = 'encryption_keys'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key_id = Column(String(100), unique=True)
    key_type = Column(String(20))  # 'message', 'file', 'user_data'
    encrypted_key = Column(LargeBinary)  # encrypted with master key
    key_metadata = Column(JSONB)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    encrypted_messages = relationship("EncryptedMessage", back_populates="encryption_key")
    
    def __repr__(self):
        return f"<EncryptionKey(id={self.id}, key_id='{self.key_id}', type='{self.key_type}')>"


class EncryptedMessage(Base):
    __tablename__ = 'encrypted_messages'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'))
    sender_id = Column(Integer, ForeignKey('users.id'))
    encrypted_content = Column(LargeBinary)
    encryption_key_id = Column(String(100), ForeignKey('encryption_keys.key_id'))
    content_hash = Column(String(64))  # for integrity verification
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="encrypted_messages")
    sender = relationship("User", back_populates="encrypted_messages")
    encryption_key = relationship("EncryptionKey", back_populates="encrypted_messages")
    
    def __repr__(self):
        return f"<EncryptedMessage(id={self.id}, conversation_id={self.conversation_id}, sender_id={self.sender_id})>"


# Additional indexes that couldn't be defined in __table_args__
from sqlalchemy import event

@event.listens_for(UserSession.__table__, 'after_create')
def create_session_indexes(target, connection, **kw):
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_user_active "
        "ON user_sessions(user_id, is_active, last_activity DESC)"
    )

@event.listens_for(Message.__table__, 'after_create')
def create_message_search_index(target, connection, **kw):
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_content_search "
        "ON messages USING gin(to_tsvector('english', content))"
    )

