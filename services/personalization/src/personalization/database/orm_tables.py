from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Text, JSON, 
    Numeric, ForeignKey, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import VECTOR  # Ensure you have the pgvector package installed
from datetime import datetime, timedelta
import enum

Base = declarative_base()

class EmbeddingType(enum.Enum):
    INTERESTS = "interests"
    COMMUNICATION_STYLE = "communication_style"
    PREFERENCES = "preferences"
    BEHAVIOR = "behavior"
    CONTENT_AFFINITY = "content_affinity"

class ChangeFrequency(enum.Enum):
    STATIC = "static"
    SLOW = "slow"
    DYNAMIC = "dynamic"

class ExperimentStatus(enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DISABLED = "disabled"

class UserProfileStatic(Base):
    __tablename__ = 'user_profiles_static'
    __table_args__ = {'schema': 'personalization'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('gremory.users.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False, unique=True)
    name = Column(String(255))
    email = Column(String(255))
    birthdate = Column(Date)
    signup_source = Column(String(100))
    language_preference = Column(String(10), default='en')
    timezone = Column(String(50))
    long_term_goals = Column(JSONB)
    immutable_preferences = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    dynamic_profiles = relationship("UserProfileDynamic", back_populates="static_profile", cascade="all, delete-orphan")
    embeddings = relationship("UserEmbedding", back_populates="user_profile", cascade="all, delete-orphan")
    features = relationship("UserFeature", back_populates="user_profile", cascade="all, delete-orphan")
    experiments = relationship("UserExperiment", back_populates="user_profile", cascade="all, delete-orphan")

class UserProfileDynamic(Base):
    __tablename__ = 'user_profiles_dynamic'
    __table_args__ = (
        UniqueConstraint('user_id', 'activity_date'),
        {'schema': 'personalization'}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('gremory.users.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False)
    last_login_at = Column(DateTime(timezone=True))
    session_message_count = Column(Integer, default=0)
    daily_activity_count = Column(Integer, default=0)
    recent_topics = Column(JSONB)
    real_time_feedback = Column(JSONB)
    session_metrics = Column(JSONB)
    activity_date = Column(Date, default=func.current_date())
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow() + timedelta(days=90))
    
    # Relationships
    static_profile = relationship("UserProfileStatic", back_populates="dynamic_profiles")

class UserEmbedding(Base):
    __tablename__ = 'user_embeddings'
    __table_args__ = (
        UniqueConstraint('user_id', 'embedding_type'),
        CheckConstraint('confidence_score >= 0.00 AND confidence_score <= 1.00', name='chk_confidence_score'),
        CheckConstraint(
            "embedding_type IN ('interests', 'communication_style', 'preferences', 'behavior', 'content_affinity')",
            name='chk_embedding_type'
        ),
        {'schema': 'personalization'}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('gremory.users.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False)
    embedding_type = Column(String(50), nullable=False)
    embedding_vector = Column(VECTOR(1536))  # Adjust dimension as needed
    meta_data = Column(JSONB)  # Changed from 'metadata' to avoid conflict
    model_version = Column(String(50))
    confidence_score = Column(Numeric(3, 2))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow() + timedelta(days=30))
    
    # Relationships
    user_profile = relationship("UserProfileStatic", back_populates="embeddings")

class UserFeature(Base):
    __tablename__ = 'user_features'
    __table_args__ = (
        UniqueConstraint('user_id', 'feature_name', 'feature_version'),
        CheckConstraint("change_frequency IN ('static', 'slow', 'dynamic')", name='chk_change_frequency'),
        {'schema': 'personalization'}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('gremory.users.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False)
    feature_name = Column(String(100), nullable=False)
    feature_value = Column(JSONB, nullable=False)
    feature_version = Column(String(20), default='1.0')
    change_frequency = Column(String(20))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    user_profile = relationship("UserProfileStatic", back_populates="features")

class UserExperiment(Base):
    __tablename__ = 'user_experiments'
    __table_args__ = (
        UniqueConstraint('user_id', 'experiment_name'),
        CheckConstraint("status IN ('active', 'completed', 'disabled')", name='chk_experiment_status'),
        {'schema': 'personalization'}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('gremory.users.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False)
    experiment_name = Column(String(100), nullable=False)
    variant = Column(String(50), nullable=False)
    assigned_at = Column(DateTime(timezone=True), default=func.now())
    status = Column(String(20), default='active')
    meta_data = Column(JSONB)  # Changed from 'metadata' to avoid conflict
    
    # Relationships
    user_profile = relationship("UserProfileStatic", back_populates="experiments")

# Indexes are typically handled by migration files, but here's how you'd define them in SQLAlchemy:
# Performance indexes
Index('idx_user_profiles_static_user_id', UserProfileStatic.user_id)
Index('idx_user_profiles_static_created_at', UserProfileStatic.created_at)
Index('idx_user_profiles_static_updated_at', UserProfileStatic.updated_at)

Index('idx_user_profiles_dynamic_user_id', UserProfileDynamic.user_id)
Index('idx_user_profiles_dynamic_activity_date', UserProfileDynamic.activity_date)
Index('idx_user_profiles_dynamic_expires_at', UserProfileDynamic.expires_at)
Index('idx_user_profiles_dynamic_last_login', UserProfileDynamic.last_login_at)

Index('idx_user_embeddings_user_id_type', UserEmbedding.user_id, UserEmbedding.embedding_type)
Index('idx_user_embeddings_expires_at', UserEmbedding.expires_at)
Index('idx_user_embeddings_model_version', UserEmbedding.model_version)
Index('idx_user_embeddings_confidence', UserEmbedding.confidence_score)

Index('idx_user_features_user_id_name', UserFeature.user_id, UserFeature.feature_name)
Index('idx_user_features_change_freq', UserFeature.change_frequency)

Index('idx_user_experiments_user_id', UserExperiment.user_id)
Index('idx_user_experiments_status', UserExperiment.status)
Index('idx_user_experiments_assigned_at', UserExperiment.assigned_at)

# GIN indexes for JSONB columns (these would typically be in migration files)
Index('idx_user_profiles_static_preferences', UserProfileStatic.immutable_preferences, postgresql_using='gin')
Index('idx_user_profiles_static_goals', UserProfileStatic.long_term_goals, postgresql_using='gin')
Index('idx_user_profiles_dynamic_topics', UserProfileDynamic.recent_topics, postgresql_using='gin')
Index('idx_user_profiles_dynamic_feedback', UserProfileDynamic.real_time_feedback, postgresql_using='gin')
Index('idx_user_profiles_dynamic_metrics', UserProfileDynamic.session_metrics, postgresql_using='gin')
Index('idx_user_embeddings_metadata', UserEmbedding.meta_data, postgresql_using='gin')
Index('idx_user_features_value', UserFeature.feature_value, postgresql_using='gin')
Index('idx_user_experiments_metadata', UserExperiment.meta_data, postgresql_using='gin')
