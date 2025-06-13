import asyncio
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from common_utils.logger import logger
from .embedding_service import EmbeddingService


class AsyncEmbeddingService:
    """Async wrapper for the embedding service to handle async operations"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.embedding_service = EmbeddingService(openai_api_key)
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def create_preference_embedding_async(
        self, 
        session: Session, 
        user_id: int, 
        preferences: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Async wrapper for creating preference embedding"""
        try:
            # Run the synchronous embedding creation in a thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self.embedding_service.create_user_preference_embedding,
                session,
                user_id,
                preferences
            )
            return result
        except Exception as e:
            logger.error(f"Error in async embedding creation for user {user_id}: {str(e)}")
            return None
    
    async def update_preference_embedding_async(
        self, 
        session: Session, 
        user_id: int, 
        preferences: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Async wrapper for updating preference embedding (delete old, create new)"""
        try:
            # Run the synchronous embedding update in a thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self.embedding_service.update_user_preference_embedding,
                session,
                user_id,
                preferences
            )
            return result
        except Exception as e:
            logger.error(f"Error in async embedding update for user {user_id}: {str(e)}")
            return None

    def __del__(self):
        """Cleanup the thread pool executor"""
        try:
            self.executor.shutdown(wait=False)
        except:
            pass


# Global async embedding service instance
_async_embedding_service: Optional[AsyncEmbeddingService] = None


def get_async_embedding_service() -> AsyncEmbeddingService:
    """Get or create the global async embedding service instance"""
    global _async_embedding_service
    if _async_embedding_service is None:
        _async_embedding_service = AsyncEmbeddingService()
    return _async_embedding_service
