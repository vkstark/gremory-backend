"""
Simplified Personalization Database Management
Streamlined repositories and services for the unified schema
"""
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
import logging

from sqlalchemy import and_, or_, desc, text, func
from sqlalchemy.dialects.postgresql import insert

from common_utils.main_setting import Settings
from common_utils.database.db_conn import DatabaseManager, BaseRepository, DatabaseException
from personalization.database.orm_tables import (
    UserProfile, UserEmbedding, UserConfiguration, UserEvent, UserRecommendation
)


class PersonalizationException(DatabaseException):
    """Personalization specific exception"""
    pass


class PersonalizationDatabaseManager(DatabaseManager):
    """Simplified database manager for personalization schema"""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.logger = logging.getLogger("chatbot.personalization.database")
    
    def cleanup_expired_data(self) -> Dict[str, int]:
        """Clean up expired personalization data"""
        with self.get_session() as session:
            deleted_counts = {}
            
            # Clean expired embeddings
            deleted_embeddings = session.query(UserEmbedding).filter(
                UserEmbedding.expires_at < datetime.utcnow()
            ).delete()
            deleted_counts['embeddings'] = deleted_embeddings
            
            # Clean expired configurations
            deleted_configs = session.query(UserConfiguration).filter(
                and_(
                    UserConfiguration.expires_at.isnot(None),
                    UserConfiguration.expires_at < datetime.utcnow()
                )
            ).delete()
            deleted_counts['configurations'] = deleted_configs
            
            # Clean expired recommendations
            deleted_recommendations = session.query(UserRecommendation).filter(
                UserRecommendation.expires_at < datetime.utcnow()
            ).delete()
            deleted_counts['recommendations'] = deleted_recommendations
            
            session.commit()
            
            total_deleted = sum(deleted_counts.values())
            self.logger.info(f"Cleaned up {total_deleted} expired records: {deleted_counts}")
            
            return deleted_counts


class UserProfileRepository(BaseRepository[UserProfile]):
    """Repository for unified user profiles"""
    
    def get_by_user_id(self, user_id: int) -> Optional[UserProfile]:
        """Get profile by user ID"""
        return self.session.query(self.model_class).filter(
            self.model_class.user_id == user_id
        ).first()
    
    def create_or_update_profile(self, user_id: int, **profile_data) -> UserProfile:
        """Create or update user profile"""
        existing = self.get_by_user_id(user_id)
        
        if existing:
            # Update existing profile using bulk update
            self.session.query(self.model_class).filter(
                self.model_class.user_id == user_id
            ).update({**profile_data, 'updated_at': datetime.utcnow()})
            self.session.commit()
            return self.get_by_user_id(user_id)
        else:
            new_profile = self.model_class(
                user_id=user_id,
                **profile_data
            )
            self.session.add(new_profile)
            self.session.commit()
            return new_profile
    
    def update_activity_summary(self, user_id: int, activity_data: Dict[str, Any]) -> Optional[UserProfile]:
        """Update activity summary for user"""
        profile = self.get_by_user_id(user_id)
        if profile:
            current_summary = profile.activity_summary or {}
            current_summary.update(activity_data)
            
            self.session.query(self.model_class).filter(
                self.model_class.user_id == user_id
            ).update({
                'activity_summary': current_summary,
                'last_login_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            })
            self.session.commit()
            return self.get_by_user_id(user_id)
        return None
    
    def get_active_users(self, hours: int = 24) -> List[UserProfile]:
        """Get users active in the last N hours"""
        since_time = datetime.utcnow() - timedelta(hours=hours)
        return self.session.query(self.model_class).filter(
            self.model_class.last_login_at >= since_time
        ).order_by(desc(self.model_class.last_login_at)).all()


class UserEmbeddingRepository(BaseRepository[UserEmbedding]):
    """Repository for user embeddings"""
    
    def get_by_user_and_type(self, user_id: int, embedding_type: str, model_version: str) -> Optional[UserEmbedding]:
        """Get embedding by user ID, type, and model version"""
        return self.session.query(self.model_class).filter(
            and_(
                self.model_class.user_id == user_id,
                self.model_class.embedding_type == embedding_type,
                self.model_class.model_version == model_version
            )
        ).first()
    
    def create_or_update_embedding(self, user_id: int, embedding_type: str, 
                                  model_version: str, embedding_vector: List[float], 
                                  confidence_score: Optional[float] = None, **kwargs) -> UserEmbedding:
        """Create or update user embedding"""
        existing = self.get_by_user_and_type(user_id, embedding_type, model_version)
        
        if existing:
            # Update existing embedding
            update_data = {
                'embedding_vector': embedding_vector,
                'confidence_score': confidence_score,
                'expires_at': datetime.utcnow() + timedelta(days=30),
                **kwargs
            }
            self.session.query(self.model_class).filter(
                and_(
                    self.model_class.user_id == user_id,
                    self.model_class.embedding_type == embedding_type,
                    self.model_class.model_version == model_version
                )
            ).update(update_data)
            self.session.commit()
            return self.get_by_user_and_type(user_id, embedding_type, model_version)
        else:
            new_embedding = self.model_class(
                user_id=user_id,
                embedding_type=embedding_type,
                model_version=model_version,
                embedding_vector=embedding_vector,
                confidence_score=confidence_score,
                expires_at=datetime.utcnow() + timedelta(days=30),
                **kwargs
            )
            self.session.add(new_embedding)
            self.session.commit()
            return new_embedding
    
    def find_similar_users(self, user_id: int, embedding_type: str, model_version: str,
                          similarity_threshold: float = 0.8, limit: int = 10) -> List[Dict[str, Any]]:
        """Find users with similar embeddings using cosine similarity"""
        target_embedding = self.get_by_user_and_type(user_id, embedding_type, model_version)
        
        if not target_embedding or not target_embedding.embedding_vector:
            return []
        
        # PostgreSQL cosine similarity query
        query = text("""
            SELECT user_id, 
                   1 - (embedding_vector <=> :target_vector) as similarity,
                   confidence_score,
                   created_at
            FROM personalization.user_embeddings
            WHERE user_id != :user_id 
              AND embedding_type = :embedding_type
              AND model_version = :model_version
              AND embedding_vector IS NOT NULL
              AND expires_at > NOW()
              AND 1 - (embedding_vector <=> :target_vector) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """)
        
        result = self.session.execute(query, {
            'target_vector': target_embedding.embedding_vector,
            'user_id': user_id,
            'embedding_type': embedding_type,
            'model_version': model_version,
            'threshold': similarity_threshold,
            'limit': limit
        })
        
        return [dict(row) for row in result]


class UserConfigurationRepository(BaseRepository[UserConfiguration]):
    """Repository for user configurations (features, experiments, settings)"""
    
    def get_user_config(self, user_id: int, config_type: str, config_key: str) -> Optional[UserConfiguration]:
        """Get specific configuration for user"""
        return self.session.query(self.model_class).filter(
            and_(
                self.model_class.user_id == user_id,
                self.model_class.config_type == config_type,
                self.model_class.config_key == config_key
            )
        ).first()
    
    def get_user_configurations(self, user_id: int, config_type: Optional[str] = None, 
                              status: str = 'active') -> List[UserConfiguration]:
        """Get all configurations for user"""
        query = self.session.query(self.model_class).filter(
            and_(
                self.model_class.user_id == user_id,
                self.model_class.status == status
            )
        )
        
        if config_type:
            query = query.filter(self.model_class.config_type == config_type)
        
        # Filter out expired configurations
        now = datetime.utcnow()
        query = query.filter(
            or_(
                self.model_class.expires_at.is_(None),
                self.model_class.expires_at > now
            )
        )
        
        return query.all()
    
    def set_configuration(self, user_id: int, config_type: str, config_key: str,
                         config_value: Dict[str, Any], expires_at: Optional[datetime] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> UserConfiguration:
        """Set configuration for user"""
        existing = self.get_user_config(user_id, config_type, config_key)
        
        if existing:
            # Update existing configuration
            update_data = {
                'config_value': config_value,
                'meta_data': metadata or {},
                'expires_at': expires_at,
                'updated_at': datetime.utcnow()
            }
            self.session.query(self.model_class).filter(
                and_(
                    self.model_class.user_id == user_id,
                    self.model_class.config_type == config_type,
                    self.model_class.config_key == config_key
                )
            ).update(update_data)
            self.session.commit()
            return self.get_user_config(user_id, config_type, config_key)
        else:
            new_config = self.model_class(
                user_id=user_id,
                config_type=config_type,
                config_key=config_key,
                config_value=config_value,
                meta_data=metadata or {},
                expires_at=expires_at
            )
            self.session.add(new_config)
            self.session.commit()
            return new_config
    
    def get_feature_stats(self, config_key: str) -> Dict[str, Any]:
        """Get usage statistics for a feature/experiment"""
        total_users = self.session.query(self.model_class).filter(
            and_(
                self.model_class.config_key == config_key,
                self.model_class.status == 'active'
            )
        ).count()
        
        # Get type distribution
        type_stats = self.session.query(
            self.model_class.config_type,
            func.count(self.model_class.user_id)
        ).filter(
            self.model_class.config_key == config_key
        ).group_by(self.model_class.config_type).all()
        
        return {
            "total_users": total_users,
            "type_distribution": {row[0]: row[1] for row in type_stats},
            "config_key": config_key
        }


class UserEventRepository(BaseRepository[UserEvent]):
    """Repository for user events"""
    
    def create_event(self, user_id: int, event_type: str, event_data: Optional[Dict[str, Any]] = None) -> UserEvent:
        """Create a user event"""
        event = self.model_class(
            user_id=user_id,
            event_type=event_type,
            event_data=event_data or {}
        )
        self.session.add(event)
        self.session.commit()
        return event
    
    def get_user_events(self, user_id: int, event_type: Optional[str] = None, 
                       since: Optional[datetime] = None, limit: int = 100) -> List[UserEvent]:
        """Get user events with optional filtering"""
        query = self.session.query(self.model_class).filter(
            self.model_class.user_id == user_id
        )
        
        if event_type:
            query = query.filter(self.model_class.event_type == event_type)
        
        if since:
            query = query.filter(self.model_class.created_at >= since)
        
        return query.order_by(desc(self.model_class.created_at)).limit(limit).all()


class UserRecommendationRepository(BaseRepository[UserRecommendation]):
    """Repository for user recommendations"""
    
    def get_recommendations(self, user_id: int, recommendation_type: str = 'general') -> Optional[UserRecommendation]:
        """Get cached recommendations for user"""
        recommendation = self.session.query(self.model_class).filter(
            and_(
                self.model_class.user_id == user_id,
                self.model_class.recommendation_type == recommendation_type,
                self.model_class.expires_at > datetime.utcnow()
            )
        ).first()
        
        return recommendation
    
    def set_recommendations(self, user_id: int, recommendations: Dict[str, Any],
                           recommendation_type: str = 'general', 
                           expires_in_hours: int = 1) -> UserRecommendation:
        """Set/update recommendations for user"""
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        # Use upsert pattern
        stmt = insert(self.model_class).values(
            user_id=user_id,
            recommendation_type=recommendation_type,
            recommendations=recommendations,
            expires_at=expires_at
        )
        
        stmt = stmt.on_conflict_do_update(
            index_elements=['user_id'],
            set_=dict(
                recommendations=stmt.excluded.recommendations,
                expires_at=stmt.excluded.expires_at,
                created_at=func.now()
            )
        )
        
        self.session.execute(stmt)
        self.session.commit()
        
        return self.get_recommendations(user_id, recommendation_type)


class PersonalizationService:
    """High-level service for personalization operations"""
    
    def __init__(self, db_manager: PersonalizationDatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger("chatbot.personalization.service")
    
    def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """Get complete user profile"""
        with self.db_manager.get_session() as session:
            repo = UserProfileRepository(session, UserProfile)
            return repo.get_by_user_id(user_id)
    
    def update_user_activity(self, user_id: int, activity_data: Dict[str, Any]) -> Optional[UserProfile]:
        """Update user activity metrics"""
        with self.db_manager.get_session() as session:
            repo = UserProfileRepository(session, UserProfile)
            return repo.update_activity_summary(user_id, activity_data)
    
    def set_user_feature(self, user_id: int, feature_name: str, feature_value: Dict[str, Any],
                        expires_at: Optional[datetime] = None) -> UserConfiguration:
        """Set a feature flag for user"""
        with self.db_manager.get_session() as session:
            repo = UserConfigurationRepository(session, UserConfiguration)
            return repo.set_configuration(
                user_id=user_id,
                config_type='feature',
                config_key=feature_name,
                config_value=feature_value,
                expires_at=expires_at
            )
    
    def get_user_features(self, user_id: int) -> List[UserConfiguration]:
        """Get all active features for user"""
        with self.db_manager.get_session() as session:
            repo = UserConfigurationRepository(session, UserConfiguration)
            return repo.get_user_configurations(user_id, config_type='feature')
    
    def assign_experiment(self, user_id: int, experiment_name: str, variant: str,
                         metadata: Optional[Dict[str, Any]] = None) -> UserConfiguration:
        """Assign user to an A/B test experiment"""
        with self.db_manager.get_session() as session:
            repo = UserConfigurationRepository(session, UserConfiguration)
            return repo.set_configuration(
                user_id=user_id,
                config_type='experiment',
                config_key=experiment_name,
                config_value={"variant": variant},
                metadata=metadata
            )
    
    def log_event(self, user_id: int, event_type: str, event_data: Optional[Dict[str, Any]] = None) -> UserEvent:
        """Log a user event"""
        with self.db_manager.get_session() as session:
            repo = UserEventRepository(session, UserEvent)
            return repo.create_event(user_id, event_type, event_data)
    
    def get_personalization_data(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive personalization data for user"""
        with self.db_manager.get_session() as session:
            profile_repo = UserProfileRepository(session, UserProfile)
            config_repo = UserConfigurationRepository(session, UserConfiguration)
            
            profile = profile_repo.get_by_user_id(user_id)
            configurations = config_repo.get_user_configurations(user_id)
            
            # Group configurations by type
            features = {c.config_key: c.config_value for c in configurations if c.config_type == 'feature'}
            experiments = {c.config_key: c.config_value for c in configurations if c.config_type == 'experiment'}
            settings = {c.config_key: c.config_value for c in configurations if c.config_type == 'setting'}
            
            return {
                "profile": profile,
                "features": features,
                "experiments": experiments,
                "settings": settings
            }


def create_personalization_db_manager(settings: Settings) -> PersonalizationDatabaseManager:
    """Factory function to create personalization database manager"""
    return PersonalizationDatabaseManager(settings)


# Example usage:
"""
from common_utils.main_setting import settings
from personalization.database.db_conn import create_personalization_db_manager

# Create personalization database manager
db_manager = create_personalization_db_manager(settings)

# Create service
service = PersonalizationService(db_manager)

# Get user personalization data
user_data = service.get_personalization_data(user_id=123)

# Update user activity
service.update_user_activity(123, {
    "daily_messages": 15,
    "session_duration": 600,
    "topics": ["ai", "programming"]
})

# Set feature flag
service.set_user_feature(123, "new_ui", {"enabled": True, "version": "v2"})

# Assign to A/B test
service.assign_experiment(123, "chat_interface_test", "variant_b")

# Log user event
service.log_event(123, "message_sent", {"content_length": 50, "topic": "ai"})
"""
