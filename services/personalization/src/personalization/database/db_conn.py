"""
Personalization schema database management with:
- Specialized repositories for personalization tables
- ML/AI specific query operations
- A/B testing utilities
- User preference management
- Performance optimized queries for personalization features
"""

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Union, Type, TypeVar
from datetime import datetime, timedelta, timezone
from functools import wraps
from dataclasses import dataclass
import threading
from enum import Enum

from sqlalchemy import (
    create_engine, MetaData, event, text, inspect, 
    and_, or_, desc, asc, func, select, update, delete
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    sessionmaker, Session, scoped_session, 
    declarative_base, relationship
)
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import (
    SQLAlchemyError, IntegrityError, OperationalError, 
    DisconnectionError, TimeoutError
)
from sqlalchemy.dialects.postgresql import insert
import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential

from common_utils.main_setting import settings, Settings
from common_utils.database.db_conn import (
    DatabaseManager, BaseRepository, AdvancedQueryBuilder, 
    TransactionManager, with_retry, QueryException, DatabaseException
)
from personalization.database.orm_tables import (
    UserProfileStatic, UserProfileDynamic, UserEmbedding, 
    UserFeature, UserExperiment, EmbeddingType, ChangeFrequency, ExperimentStatus
)

T = TypeVar('T')


class PersonalizationException(DatabaseException):
    """Personalization specific exception"""
    pass


class EmbeddingException(PersonalizationException):
    """Embedding related exception"""
    pass


class ExperimentException(PersonalizationException):
    """A/B testing related exception"""
    pass


class PersonalizationDatabaseManager(DatabaseManager):
    """Extended database manager for personalization schema"""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.logger = logging.getLogger("chatbot.personalization.database")
        
        # Setup personalization specific event listeners
        self._setup_personalization_listeners()
    
    def _setup_personalization_listeners(self):
        """Setup personalization specific event listeners"""
        
        @event.listens_for(UserProfileDynamic, 'before_insert')
        def set_expires_at(mapper, connection, target):
            """Automatically set expires_at for dynamic profiles"""
            if not target.expires_at:
                target.expires_at = datetime.utcnow() + timedelta(days=90)
        
        @event.listens_for(UserEmbedding, 'before_insert')
        def set_embedding_expires_at(mapper, connection, target):
            """Automatically set expires_at for embeddings"""
            if not target.expires_at:
                target.expires_at = datetime.utcnow() + timedelta(days=30)
    
    def cleanup_expired_data(self) -> Dict[str, int]:
        """Clean up expired personalization data"""
        with self.get_session() as session:
            now = datetime.utcnow()
            
            # Clean expired dynamic profiles
            dynamic_deleted = session.query(UserProfileDynamic).filter(
                UserProfileDynamic.expires_at < now
            ).delete()
            
            # Clean expired embeddings
            embeddings_deleted = session.query(UserEmbedding).filter(
                UserEmbedding.expires_at < now
            ).delete()
            
            # Clean expired features
            features_deleted = session.query(UserFeature).filter(
                and_(
                    UserFeature.expires_at.isnot(None),
                    UserFeature.expires_at < now
                )
            ).delete()
            
            self.logger.info(f"Cleaned up expired data - Dynamic profiles: {dynamic_deleted}, "
                           f"Embeddings: {embeddings_deleted}, Features: {features_deleted}")
            
            return {
                "dynamic_profiles": dynamic_deleted,
                "embeddings": embeddings_deleted,
                "features": features_deleted
            }


class UserProfileStaticRepository(BaseRepository[UserProfileStatic]):
    """Repository for static user profile data"""
    
    def get_by_user_id(self, user_id: int) -> Optional[UserProfileStatic]:
        """Get static profile by user ID"""
        return self.get_by_field("user_id", user_id)
    
    def create_or_update_profile(self, user_id: int, **profile_data) -> UserProfileStatic:
        """Create or update static profile"""
        existing = self.get_by_user_id(user_id)
        
        if existing:
            return self.update(existing.id, **profile_data)
        else:
            return self.create(user_id=user_id, **profile_data)
    
    def get_profiles_by_language(self, language: str) -> List[UserProfileStatic]:
        """Get profiles by language preference"""
        return self.get_multiple(filters={"language_preference": language})
    
    def get_profiles_by_timezone(self, timezone: str) -> List[UserProfileStatic]:
        """Get profiles by timezone"""
        return self.get_multiple(filters={"timezone": timezone})
    
    def search_by_goals(self, goal_keywords: List[str]) -> List[UserProfileStatic]:
        """Search profiles by long-term goals"""
        builder = AdvancedQueryBuilder(self.session, self.model_class)
        
        for keyword in goal_keywords:
            builder.filter(
                func.jsonb_path_exists(
                    UserProfileStatic.long_term_goals,
                    f'$.*[*] ? (@ like_regex "{keyword}" flag "i")'
                )
            )
        
        return builder.execute()


class UserProfileDynamicRepository(BaseRepository[UserProfileDynamic]):
    """Repository for dynamic user profile data"""
    
    def get_by_user_id_and_date(self, user_id: int, activity_date: datetime = None) -> Optional[UserProfileDynamic]:
        """Get dynamic profile by user ID and date"""
        if activity_date is None:
            activity_date = datetime.now().date()
        
        return self.session.query(self.model_class).filter(
            and_(
                self.model_class.user_id == user_id,
                self.model_class.activity_date == activity_date
            )
        ).first()
    
    def get_recent_activity(self, user_id: int, days: int = 30) -> List[UserProfileDynamic]:
        """Get recent activity for user"""
        since_date = datetime.now().date() - timedelta(days=days)
        
        return self.get_multiple(
            filters={
                "user_id": user_id,
                "activity_date": {"op": "gte", "value": since_date}
            },
            order_by="-activity_date"
        )
    
    def update_session_metrics(self, user_id: int, metrics: Dict[str, Any]) -> UserProfileDynamic:
        """Update session metrics for today"""
        today = datetime.now().date()
        profile = self.get_by_user_id_and_date(user_id, today)
        
        if not profile:
            profile = self.create(
                user_id=user_id,
                activity_date=today,
                session_metrics=metrics,
                session_message_count=metrics.get('message_count', 0),
                last_login_at=datetime.utcnow()
            )
        else:
            # Merge metrics
            existing_metrics = profile.session_metrics or {}
            existing_metrics.update(metrics)
            
            self.update(profile.id,
                       session_metrics=existing_metrics,
                       session_message_count=profile.session_message_count + metrics.get('message_count', 0),
                       last_login_at=datetime.utcnow())
        
        return profile
    
    def get_active_users(self, hours: int = 24) -> List[UserProfileDynamic]:
        """Get users active in the last N hours"""
        since_time = datetime.utcnow() - timedelta(hours=hours)
        
        return self.get_multiple(
            filters={"last_login_at": {"op": "gte", "value": since_time}},
            order_by="-last_login_at"
        )
    
    def get_user_activity_summary(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get activity summary for user"""
        activities = self.get_recent_activity(user_id, days)
        
        if not activities:
            return {"total_days": 0, "total_messages": 0, "avg_daily_messages": 0}
        
        total_messages = sum(a.session_message_count or 0 for a in activities)
        
        return {
            "total_days": len(activities),
            "total_messages": total_messages,
            "avg_daily_messages": total_messages / len(activities) if activities else 0,
            "most_active_day": max(activities, key=lambda x: x.session_message_count or 0).activity_date,
            "last_activity": max(activities, key=lambda x: x.last_login_at or datetime.min).last_login_at
        }


class UserEmbeddingRepository(BaseRepository[UserEmbedding]):
    """Repository for user embeddings"""
    
    def get_by_user_and_type(self, user_id: int, embedding_type: Union[str, EmbeddingType]) -> Optional[UserEmbedding]:
        """Get embedding by user ID and type"""
        type_str = embedding_type.value if isinstance(embedding_type, EmbeddingType) else embedding_type
        
        return self.session.query(self.model_class).filter(
            and_(
                self.model_class.user_id == user_id,
                self.model_class.embedding_type == type_str
            )
        ).first()
    
    def create_or_update_embedding(self, user_id: int, embedding_type: str, 
                                  embedding_vector: List[float], **kwargs) -> UserEmbedding:
        """Create or update user embedding"""
        existing = self.get_by_user_and_type(user_id, embedding_type)
        
        data = {
            "embedding_vector": embedding_vector,
            "updated_at": datetime.utcnow(),
            **kwargs
        }
        
        if existing:
            return self.update(existing.id, **data)
        else:
            return self.create(
                user_id=user_id,
                embedding_type=embedding_type,
                **data
            )
    
    def find_similar_users(self, user_id: int, embedding_type: str, 
                          similarity_threshold: float = 0.8, limit: int = 10) -> List[Dict[str, Any]]:
        """Find users with similar embeddings"""
        target_embedding = self.get_by_user_and_type(user_id, embedding_type)
        
        if not target_embedding or not target_embedding.embedding_vector:
            return []
        
        # PostgreSQL cosine similarity query
        query = text("""
            SELECT user_id, 
                   1 - (embedding_vector <=> :target_vector) as similarity,
                   confidence_score,
                   updated_at
            FROM personalization.user_embeddings
            WHERE user_id != :user_id 
              AND embedding_type = :embedding_type
              AND embedding_vector IS NOT NULL
              AND 1 - (embedding_vector <=> :target_vector) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """)
        
        result = self.session.execute(query, {
            'target_vector': target_embedding.embedding_vector,
            'user_id': user_id,
            'embedding_type': embedding_type,
            'threshold': similarity_threshold,
            'limit': limit
        })
        
        return [dict(row) for row in result]
    
    def get_embeddings_by_model_version(self, model_version: str) -> List[UserEmbedding]:
        """Get embeddings by model version"""
        return self.get_multiple(filters={"model_version": model_version})
    
    def cleanup_low_confidence_embeddings(self, min_confidence: float = 0.5) -> int:
        """Remove embeddings with low confidence scores"""
        deleted = self.session.query(self.model_class).filter(
            self.model_class.confidence_score < min_confidence
        ).delete()
        
        self.logger.info(f"Cleaned up {deleted} low confidence embeddings")
        return deleted


class UserFeatureRepository(BaseRepository[UserFeature]):
    """Repository for user features and feature flags"""
    
    def get_user_features(self, user_id: int) -> Dict[str, Any]:
        """Get all active features for a user"""
        features = self.get_multiple(
            filters={"user_id": user_id},
            order_by="-updated_at"
        )
        
        # Filter out expired features
        now = datetime.utcnow()
        active_features = {}
        
        for feature in features:
            if feature.expires_at is None or feature.expires_at > now:
                active_features[feature.feature_name] = {
                    "value": feature.feature_value,
                    "version": feature.feature_version,
                    "change_frequency": feature.change_frequency,
                    "updated_at": feature.updated_at
                }
        
        return active_features
    
    def set_feature(self, user_id: int, feature_name: str, feature_value: Dict[str, Any],
                   feature_version: str = "1.0", change_frequency: str = "dynamic",
                   expires_at: Optional[datetime] = None) -> UserFeature:
        """Set a feature for a user"""
        existing = self.session.query(self.model_class).filter(
            and_(
                self.model_class.user_id == user_id,
                self.model_class.feature_name == feature_name,
                self.model_class.feature_version == feature_version
            )
        ).first()
        
        if existing:
            return self.update(existing.id,
                             feature_value=feature_value,
                             change_frequency=change_frequency,
                             expires_at=expires_at)
        else:
            return self.create(
                user_id=user_id,
                feature_name=feature_name,
                feature_value=feature_value,
                feature_version=feature_version,
                change_frequency=change_frequency,
                expires_at=expires_at
            )
    
    def get_feature_usage_stats(self, feature_name: str) -> Dict[str, Any]:
        """Get usage statistics for a feature"""
        total_users = self.count(filters={"feature_name": feature_name})
        
        # Get version distribution
        version_query = self.session.query(
            self.model_class.feature_version,
            func.count(self.model_class.id)
        ).filter(
            self.model_class.feature_name == feature_name
        ).group_by(self.model_class.feature_version).all()
        
        return {
            "total_users": total_users,
            "version_distribution": dict(version_query),
            "feature_name": feature_name
        }
    
    def bulk_set_feature(self, user_ids: List[int], feature_name: str, 
                        feature_value: Dict[str, Any], **kwargs) -> List[UserFeature]:
        """Bulk set feature for multiple users"""
        features_data = []
        for user_id in user_ids:
            features_data.append({
                "user_id": user_id,
                "feature_name": feature_name,
                "feature_value": feature_value,
                **kwargs
            })
        
        return self.bulk_create(features_data)


class UserExperimentRepository(BaseRepository[UserExperiment]):
    """Repository for A/B testing experiments"""
    
    def assign_to_experiment(self, user_id: int, experiment_name: str, 
                           variant: str, metadata: Optional[Dict[str, Any]] = None) -> UserExperiment:
        """Assign user to experiment"""
        existing = self.session.query(self.model_class).filter(
            and_(
                self.model_class.user_id == user_id,
                self.model_class.experiment_name == experiment_name
            )
        ).first()
        
        if existing:
            return self.update(existing.id,
                             variant=variant,
                             status="active",
                             metadata=metadata)
        else:
            return self.create(
                user_id=user_id,
                experiment_name=experiment_name,
                variant=variant,
                status="active",
                metadata=metadata
            )
    
    def get_user_experiments(self, user_id: int, status: str = "active") -> List[UserExperiment]:
        """Get user's active experiments"""
        return self.get_multiple(
            filters={"user_id": user_id, "status": status},
            order_by="-assigned_at"
        )
    
    def get_experiment_results(self, experiment_name: str) -> Dict[str, Any]:
        """Get experiment results and statistics"""
        # Get variant distribution
        variant_query = self.session.query(
            self.model_class.variant,
            func.count(self.model_class.id)
        ).filter(
            self.model_class.experiment_name == experiment_name
        ).group_by(self.model_class.variant).all()
        
        # Get status distribution
        status_query = self.session.query(
            self.model_class.status,
            func.count(self.model_class.id)
        ).filter(
            self.model_class.experiment_name == experiment_name
        ).group_by(self.model_class.status).all()
        
        total_participants = self.count(filters={"experiment_name": experiment_name})
        
        return {
            "experiment_name": experiment_name,
            "total_participants": total_participants,
            "variant_distribution": dict(variant_query),
            "status_distribution": dict(status_query),
            "latest_assignment": self.session.query(func.max(self.model_class.assigned_at)).filter(
                self.model_class.experiment_name == experiment_name
            ).scalar()
        }
    
    def end_experiment(self, experiment_name: str) -> int:
        """End an experiment by marking all participants as completed"""
        updated = self.session.query(self.model_class).filter(
            and_(
                self.model_class.experiment_name == experiment_name,
                self.model_class.status == "active"
            )
        ).update({"status": "completed"})
        
        self.logger.info(f"Ended experiment {experiment_name} for {updated} users")
        return updated


class PersonalizationService:
    """High-level service for personalization operations"""
    
    def __init__(self, db_manager: PersonalizationDatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger("chatbot.personalization.service")
    
    def get_user_personalization_data(self, user_id: int) -> Dict[str, Any]:
        """Get complete personalization data for a user"""
        with self.db_manager.get_session() as session:
            static_repo = UserProfileStaticRepository(session, UserProfileStatic)
            dynamic_repo = UserProfileDynamicRepository(session, UserProfileDynamic)
            embedding_repo = UserEmbeddingRepository(session, UserEmbedding)
            feature_repo = UserFeatureRepository(session, UserFeature)
            experiment_repo = UserExperimentRepository(session, UserExperiment)
            
            # Get all user data
            static_profile = static_repo.get_by_user_id(user_id)
            recent_activity = dynamic_repo.get_recent_activity(user_id, days=7)
            embeddings = embedding_repo.get_multiple(filters={"user_id": user_id})
            features = feature_repo.get_user_features(user_id)
            experiments = experiment_repo.get_user_experiments(user_id)
            
            return {
                "user_id": user_id,
                "static_profile": static_profile,
                "recent_activity": recent_activity,
                "embeddings": {emb.embedding_type: emb for emb in embeddings},
                "features": features,
                "active_experiments": experiments,
                "activity_summary": dynamic_repo.get_user_activity_summary(user_id)
            }
    
    def update_user_activity(self, user_id: int, activity_data: Dict[str, Any]):
        """Update user activity and session metrics"""
        with self.db_manager.get_session() as session:
            dynamic_repo = UserProfileDynamicRepository(session, UserProfileDynamic)
            return dynamic_repo.update_session_metrics(user_id, activity_data)
    
    def find_similar_users_comprehensive(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Find similar users across all embedding types"""
        with self.db_manager.get_session() as session:
            embedding_repo = UserEmbeddingRepository(session, UserEmbedding)
            
            all_similarities = {}
            
            for embedding_type in EmbeddingType:
                similarities = embedding_repo.find_similar_users(
                    user_id, embedding_type.value, limit=limit*2
                )
                
                for sim in similarities:
                    uid = sim['user_id']
                    if uid not in all_similarities:
                        all_similarities[uid] = {"user_id": uid, "similarities": {}, "total_score": 0}
                    
                    all_similarities[uid]["similarities"][embedding_type.value] = sim['similarity']
                    all_similarities[uid]["total_score"] += sim['similarity']
            
            # Sort by total similarity score
            similar_users = sorted(
                all_similarities.values(),
                key=lambda x: x["total_score"],
                reverse=True
            )[:limit]
            
            return similar_users


def create_personalization_db_manager(settings: Settings) -> PersonalizationDatabaseManager:
    """Factory function to create personalization database manager"""
    return PersonalizationDatabaseManager(settings)


# Example usage:
"""
from common_utils.main_setting import settings
from common_utils.database.personalization_db_conn import create_personalization_db_manager

# Create personalization database manager
with create_personalization_db_manager(settings) as db_manager:
    # Create service
    service = PersonalizationService(db_manager)
    
    # Get user personalization data
    user_data = service.get_user_personalization_data(user_id=123)
    
    # Update user activity
    service.update_user_activity(123, {
        "message_count": 5,
        "session_duration": 300,
        "topics_discussed": ["ai", "programming"]
    })
    
    # Find similar users
    similar_users = service.find_similar_users_comprehensive(123, limit=5)
    
    # Direct repository usage
    with db_manager.get_session() as session:
        # Static profile operations
        static_repo = UserProfileStaticRepository(session, UserProfileStatic)
        static_repo.create_or_update_profile(
            user_id=123,
            name="John Doe",
            language_preference="en",
            timezone="UTC"
        )
        
        # Feature flag operations
        feature_repo = UserFeatureRepository(session, UserFeature)
        feature_repo.set_feature(
            user_id=123,
            feature_name="new_ui",
            feature_value={"enabled": True, "variant": "v2"}
        )
        
        # A/B testing
        experiment_repo = UserExperimentRepository(session, UserExperiment)
        experiment_repo.assign_to_experiment(
            user_id=123,
            experiment_name="chat_interface_test",
            variant="variant_b"
        )
"""
