from typing import Optional, Dict, Any, List
import json
import openai
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from common_utils.logger import logger
from common_utils.main_setting import settings


class EmbeddingService:
    """Service for creating and managing user embeddings"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the embedding service with OpenAI API key"""
        self.openai_api_key = openai_api_key or getattr(settings, 'OPENAI_API_KEY', None)
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required for embedding service")
        
        # Initialize OpenAI client
        openai.api_key = self.openai_api_key
        self.model_version = "text-embedding-3-small"  # Using the newer, more efficient model
        self.embedding_dimension = 1536
    
    def create_embedding(self, text: str) -> List[float]:
        """Create an embedding for the given text using OpenAI's API"""
        try:
            # Clean and prepare the text
            if not text or not text.strip():
                return []
            
            # Create embedding using OpenAI
            response = openai.embeddings.create(
                model=self.model_version,
                input=text.strip(),
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            logger.info(f"Successfully created embedding with dimension: {len(embedding)}")
            return embedding
            
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            raise
    
    def prepare_preferences_text(self, preferences: Dict[str, Any]) -> str:
        """Convert preferences dictionary to a text format suitable for embedding"""
        if not preferences:
            return ""
        
        # Create a structured text representation of preferences
        text_parts = []
        
        for key, value in preferences.items():
            if value is None:
                continue
                
            if isinstance(value, dict):
                # Handle nested dictionaries
                nested_text = self._dict_to_text(value, prefix=key)
                if nested_text:
                    text_parts.append(nested_text)
            elif isinstance(value, list):
                # Handle lists
                if value:
                    text_parts.append(f"{key}: {', '.join(str(item) for item in value)}")
            else:
                # Handle simple values
                text_parts.append(f"{key}: {str(value)}")
        
        return ". ".join(text_parts)
    
    def _dict_to_text(self, data: Dict[str, Any], prefix: str = "") -> str:
        """Convert nested dictionary to text format"""
        text_parts = []
        
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                nested_text = self._dict_to_text(value, full_key)
                if nested_text:
                    text_parts.append(nested_text)
            elif isinstance(value, list):
                if value:
                    text_parts.append(f"{full_key}: {', '.join(str(item) for item in value)}")
            else:
                text_parts.append(f"{full_key}: {str(value)}")
        
        return ". ".join(text_parts)
    
    def create_user_preference_embedding(
        self, 
        session: Session, 
        user_id: int, 
        preferences: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create embedding for user preferences and store in database"""
        try:
            # Check if preferences are empty
            if not preferences or not any(preferences.values()):
                logger.info(f"Skipping embedding creation for user {user_id} - empty preferences")
                return None
            
            # Convert preferences to text
            preferences_text = self.prepare_preferences_text(preferences)
            if not preferences_text:
                logger.info(f"Skipping embedding creation for user {user_id} - no meaningful preferences text")
                return None
            
            logger.info(f"Creating embedding for user {user_id} preferences: {preferences_text[:100]}...")
            
            # Create embedding
            embedding_vector = self.create_embedding(preferences_text)
            if not embedding_vector:
                logger.error(f"Failed to create embedding for user {user_id}")
                return None
            
            # Import here to avoid circular imports
            from personalization.database.orm_tables import UserEmbedding
            
            # Check if embedding already exists
            existing_embedding = session.query(UserEmbedding).filter(
                UserEmbedding.user_id == user_id,
                UserEmbedding.embedding_type == "fixed_preferences",
                UserEmbedding.model_version == self.model_version
            ).first()
            
            if existing_embedding:
                # Delete existing embedding and create new one (due to primary key constraints)
                session.delete(existing_embedding)
                session.flush()  # Ensure deletion is processed
                
                # Create new embedding with updated data
                new_embedding = UserEmbedding(
                    user_id=user_id,
                    embedding_type="fixed_preferences",
                    model_version=self.model_version,
                    embedding_vector=embedding_vector,
                    confidence_score=0.9,  # High confidence for direct user input
                    meta_data={
                        "preferences_text": preferences_text,
                        "preferences_keys": list(preferences.keys()),
                        "updated_at": datetime.utcnow().isoformat()
                    },
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(days=365)
                )
                
                session.add(new_embedding)
                logger.info(f"Updated existing embedding for user {user_id}")
                embedding_data = new_embedding
            else:
                # Create new embedding
                new_embedding = UserEmbedding(
                    user_id=user_id,
                    embedding_type="fixed_preferences",
                    model_version=self.model_version,
                    embedding_vector=embedding_vector,
                    confidence_score=0.9,  # High confidence for direct user input
                    meta_data={
                        "preferences_text": preferences_text,
                        "preferences_keys": list(preferences.keys()),
                        "created_at": datetime.utcnow().isoformat()
                    },
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(days=365)
                )
                
                session.add(new_embedding)
                logger.info(f"Created new embedding for user {user_id}")
                embedding_data = new_embedding
            
            session.commit()
            
            return {
                "user_id": user_id,
                "embedding_type": "fixed_preferences",
                "model_version": self.model_version,
                "embedding_dimension": len(embedding_vector),
                "confidence_score": 0.9,
                "preferences_text": preferences_text,
                "created_at": embedding_data.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating user preference embedding for user {user_id}: {str(e)}")
            session.rollback()
            raise

    def delete_user_embeddings(
        self, 
        session: Session, 
        user_id: int, 
        embedding_type: str = "fixed_preferences"
    ) -> int:
        """Delete existing embeddings for a user"""
        try:
            # Import here to avoid circular imports
            from personalization.database.orm_tables import UserEmbedding
            
            # Find and delete existing embeddings
            deleted_count = session.query(UserEmbedding).filter(
                UserEmbedding.user_id == user_id,
                UserEmbedding.embedding_type == embedding_type
            ).delete()
            
            session.commit()
            logger.info(f"Deleted {deleted_count} existing embeddings for user {user_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting embeddings for user {user_id}: {str(e)}")
            session.rollback()
            raise

    def update_user_preference_embedding(
        self, 
        session: Session, 
        user_id: int, 
        preferences: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update user preference embedding by deleting old and creating new"""
        try:
            # First delete existing embeddings
            deleted_count = self.delete_user_embeddings(session, user_id, "fixed_preferences")
            
            # If preferences are empty, just return after deletion
            if not preferences or not any(preferences.values()):
                logger.info(f"Deleted {deleted_count} embeddings for user {user_id} - no new preferences to embed")
                return {
                    "user_id": user_id,
                    "embedding_type": "fixed_preferences",
                    "action": "deleted",
                    "deleted_count": deleted_count,
                    "created_new": False
                }
            
            # Create new embedding
            embedding_result = self.create_user_preference_embedding(session, user_id, preferences)
            
            if embedding_result:
                embedding_result["action"] = "updated"
                embedding_result["deleted_count"] = deleted_count
                embedding_result["created_new"] = True
            
            return embedding_result
            
        except Exception as e:
            logger.error(f"Error updating user preference embedding for user {user_id}: {str(e)}")
            session.rollback()
            raise


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def create_preference_embedding(
    session: Session, 
    user_id: int, 
    preferences: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Convenience function to create preference embedding"""
    embedding_service = get_embedding_service()
    return embedding_service.create_user_preference_embedding(session, user_id, preferences)
