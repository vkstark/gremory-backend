"""
Simplified Personalization Schema ORM Tables
Maps to the unified/simplified database schema that reduces complexity
while maintaining core functionality.
"""
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Text, DECIMAL, 
    ForeignKey, CheckConstraint, UniqueConstraint, Index, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import VECTOR
from datetime import datetime, timedelta
import enum

Base = declarative_base()

# Enums for configuration types
class ConfigType(enum.Enum):
    FEATURE = "feature"
    EXPERIMENT = "experiment"
    SETTING = "setting"

class ConfigStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"


class UserProfile(Base):
    """Unified user profiles combining static and dynamic data"""
    __tablename__ = 'user_profiles'
    __table_args__ = {'schema': 'personalization'}
    
    user_id = Column(Integer, primary_key=True)
    
    # Static profile data
    name = Column(String(255))
    email = Column(String(255))
    birthdate = Column(Date)
    signup_source = Column(String(100))
    language_preference = Column(String(10), default='en')
    timezone = Column(String(50))
    preferences = Column(JSONB, default={})
    
    # Dynamic activity data
    last_login_at = Column(DateTime(timezone=True))
    activity_summary = Column(JSONB, default={})  # session counts, daily activity, etc.
    recent_interactions = Column(JSONB, default={})  # topics, feedback, etc.
    
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

class UserEmbedding(Base):
    """User embeddings for ML/AI features"""
    __tablename__ = 'user_embeddings'
    __table_args__ = (
        CheckConstraint('confidence_score >= 0.00 AND confidence_score <= 1.00', name='chk_confidence_score'),
        {'schema': 'personalization'}
    )
    
    user_id = Column(Integer, primary_key=True)
    embedding_type = Column(String(200), primary_key=True)  # 'interests', 'communication_style', 'behavior'
    model_version = Column(String(50), primary_key=True)
    embedding_vector = Column(VECTOR(1536))
    confidence_score = Column(DECIMAL(3, 2))
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), default=func.now())
    expires_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow() + timedelta(days=365))

class UserConfiguration(Base):
    """Unified configurations (features, experiments, flags)"""
    __tablename__ = 'user_configurations'
    __table_args__ = (
        CheckConstraint("config_type IN ('feature', 'experiment', 'setting')", name='chk_config_type'),
        CheckConstraint("status IN ('active', 'inactive', 'completed')", name='chk_status'),
        {'schema': 'personalization'}
    )
    
    user_id = Column(Integer, primary_key=True)
    config_type = Column(String(20), primary_key=True)  # 'feature', 'experiment', 'setting'
    config_key = Column(String(100), primary_key=True)
    config_value = Column(JSONB, nullable=False)
    meta_data = Column(JSONB, default={})
    status = Column(String(20), default='active')
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

class UserEvent(Base):
    """Time-series events (partitioned for performance)"""
    __tablename__ = 'user_events'
    __table_args__ = {'schema': 'personalization'}
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    event_data = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), default=func.now())

class UserRecommendation(Base):
    """Cached recommendations"""
    __tablename__ = 'user_recommendations'
    __table_args__ = {'schema': 'personalization'}
    
    user_id = Column(Integer, primary_key=True)
    recommendation_type = Column(String(50), default='general')
    recommendations = Column(JSONB, nullable=False)
    meta_data = Column(JSONB, default={})
    expires_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow() + timedelta(weeks=26))
    created_at = Column(DateTime(timezone=True), default=func.now())

# Performance Indexes
# User profiles indexes
Index('idx_user_profiles_last_login', UserProfile.last_login_at)
Index('idx_user_profiles_updated_at', UserProfile.updated_at)
Index('idx_user_profiles_preferences', UserProfile.preferences, postgresql_using='gin')
Index('idx_user_profiles_activity', UserProfile.activity_summary, postgresql_using='gin')

# Embeddings indexes
Index('idx_user_embeddings_type_expires', UserEmbedding.embedding_type, UserEmbedding.expires_at)
Index('idx_user_embeddings_confidence', UserEmbedding.confidence_score)

# Configurations indexes
Index('idx_user_configurations_type_status', UserConfiguration.config_type, UserConfiguration.status)
Index('idx_user_configurations_expires', UserConfiguration.expires_at)

# Events indexes (will apply to partitions)
Index('idx_user_events_user_type', UserEvent.user_id, UserEvent.event_type)
Index('idx_user_events_created_at', UserEvent.created_at)

# Recommendations indexes
Index('idx_user_recommendations_expires', UserRecommendation.expires_at)
Index('idx_user_recommendations_type', UserRecommendation.recommendation_type)
