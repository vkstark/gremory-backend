"""
This module provides a comprehensive database management system with:
- Connection pooling and session management
- Transaction handling with retry mechanisms
- Repository pattern implementation
- Advanced query builders
- Performance monitoring
- Security features
- GDPR compliance utilities
"""

import logging
import time
import uuid
import logging
import uuid
import time
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Union, Type, TypeVar, Generic, Callable
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
from common_utils.database.tables.orm_tables import Base

# Import your models here
T = TypeVar('T')

class TransactionIsolationLevel(Enum):
    """SQL transaction isolation levels"""
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


@dataclass
class QueryMetrics:
    """Query performance metrics"""
    query: str
    duration: float
    rows_affected: int
    timestamp: datetime
    session_id: str
    user_id: Optional[int] = None


class DatabaseException(Exception):
    """Base database exception"""
    pass


class ConnectionException(DatabaseException):
    """Database connection exception"""
    pass


class QueryException(DatabaseException):
    """Query execution exception"""
    pass


class TransactionException(DatabaseException):
    """Transaction management exception"""
    pass


class PerformanceMonitor:
    """Database performance monitoring"""
    
    def __init__(self):
        self.metrics: List[QueryMetrics] = []
        self.slow_queries: List[QueryMetrics] = []
        self._lock = threading.Lock()
    
    def record_query(self, metric: QueryMetrics):
        """Record query metrics"""
        with self._lock:
            self.metrics.append(metric)
            if len(self.metrics) > 10000:  # Keep only recent metrics
                self.metrics = self.metrics[-5000:]
    
    def record_slow_query(self, metric: QueryMetrics):
        """Record slow query"""
        with self._lock:
            self.slow_queries.append(metric)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        with self._lock:
            if not self.metrics:
                return {}
            
            durations = [m.duration for m in self.metrics]
            return {
                "total_queries": len(self.metrics),
                "avg_duration": sum(durations) / len(durations),
                "max_duration": max(durations),
                "min_duration": min(durations),
                "slow_queries_count": len(self.slow_queries),
                "queries_per_minute": len([m for m in self.metrics 
                                         if m.timestamp > datetime.now(timezone.utc) - timedelta(minutes=1)])
            }


class DatabaseManager:
    """Main database manager with connection pooling and session management"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = self._setup_logging()
        self.performance_monitor = PerformanceMonitor()
        
        # Create engine with connection pooling
        self.engine = self._create_engine()
        
        # Create session factory
        self.session_factory = scoped_session(
            sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
        )
        
        # Setup event listeners
        self._setup_event_listeners()
        
        self.logger.info("Database manager initialized successfully")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup database logging"""
        logger = logging.getLogger("chatbot.database")
        logger.setLevel(getattr(logging, self.settings.DB_LOG_LEVEL.upper()))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def get_database_url(self) -> str:
        """Generate SQLAlchemy database URL"""
        password_part = f":{self.settings.DB_PASSWORD}" if self.settings.DB_PASSWORD else ""
        return f"postgresql://{self.settings.DB_USER}{password_part}@{self.settings.DB_HOST}:{self.settings.DB_PORT}/{self.settings.DB_NAME}"

    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with optimized settings"""
        connect_args = {
            "options": f"-csearch_path={self.settings.DB_SCHEMA}",
            "connect_timeout": self.settings.DB_POOL_TIMEOUT,
        }
        
        if self.settings.DB_ENABLE_SSL and self.settings.DB_SSL_CERT_PATH:
            connect_args.update({
                "sslmode": "require",
                "sslcert": self.settings.DB_SSL_CERT_PATH
            })
    
        engine = create_engine(
            self.get_database_url(),
            poolclass=QueuePool,
            pool_size=self.settings.DB_POOL_SIZE,
            max_overflow=self.settings.DB_MAX_OVERFLOW,
            pool_timeout=self.settings.DB_POOL_TIMEOUT,
            pool_recycle=self.settings.DB_POOL_RECYCLE,
            pool_pre_ping=self.settings.DB_POOL_PRE_PING,
            connect_args=connect_args,
            echo=self.settings.DB_LOG_QUERIES,
            future=True
        )
        
        return engine
    
    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for monitoring"""
        
        @event.listens_for(self.engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
            context._query_statement = statement
        
        @event.listens_for(self.engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            duration = time.time() - context._query_start_time
            
            # Fix: Use getattr instead of context.get()
            session_id = getattr(context, 'session_id', 'unknown')
            if hasattr(context, '_sa_orm_events') and hasattr(context._sa_orm_events, 'session_id'):
                session_id = context._sa_orm_events.session_id
            
            metric = QueryMetrics(
                query=statement[:200] + "..." if len(statement) > 200 else statement,
                duration=duration,
                rows_affected=cursor.rowcount,
                timestamp=datetime.now(timezone.utc),
                session_id=str(session_id)
            )
            
            self.performance_monitor.record_query(metric)
            
            if duration > self.settings.DB_SLOW_QUERY_THRESHOLD:
                self.performance_monitor.record_slow_query(metric)
                if self.settings.DB_LOG_SLOW_QUERIES:
                    self.logger.warning(f"Slow query detected: {duration:.2f}s - {statement[:100]}")
    
    @contextmanager
    def get_session(self, isolation_level: Optional[TransactionIsolationLevel] = None):
        """Get database session with automatic cleanup"""
        session = self.session_factory()
        session_id = str(uuid.uuid4())
        
        try:
            if isolation_level:
                session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level.value}"))
            
            # Fix: Set session_id properly for tracking
            session.info['session_id'] = session_id
            yield session
            session.commit()
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"Session {session_id} rolled back due to error: {str(e)}")
            raise
        finally:
            session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def close(self):
        """Close all database connections"""
        self.session_factory.remove()
        self.engine.dispose()
        self.logger.info("Database connections closed")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                
            pool_status = self.engine.pool.status()
            performance_stats = self.performance_monitor.get_performance_stats()
            
            return {
                "status": "healthy",
                "pool_status": pool_status,
                "performance": performance_stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }


def create_db_manager_from_settings(settings: Settings) -> DatabaseManager:
    """Factory function to create database manager from settings"""
    return DatabaseManager(settings)


def with_retry(max_attempts: int = 3, delay: float = 0.5):
    """Decorator for database operations with retry logic"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DisconnectionError, TimeoutError) as e:
                    if attempt == max_attempts - 1:
                        raise DatabaseException(f"Database operation failed after {max_attempts} attempts: {str(e)}")
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
            return None
        return wrapper
    return decorator


class BaseRepository(Generic[T]):
    """Base repository class with common CRUD operations"""
    
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
        self.logger = logging.getLogger(f"chatbot.repository.{model_class.__name__}")
    
    @with_retry()
    def create(self, **kwargs) -> T:
        """Create a new record"""
        try:
            obj = self.model_class(**kwargs)
            self.session.add(obj)
            self.session.flush()
            self.logger.debug(f"Created {self.model_class.__name__} with id: {getattr(obj, 'id', 'unknown')}")
            return obj
        except IntegrityError as e:
            self.session.rollback()
            raise QueryException(f"Integrity error creating {self.model_class.__name__}: {str(e)}")
    
    @with_retry()
    def get_by_id(self, obj_id: Union[int, str]) -> Optional[T]:
        """Get record by ID"""
        return self.session.get(self.model_class, obj_id)
    
    @with_retry()
    def get_by_field(self, field_name: str, value: Any) -> Optional[T]:
        """Get record by specific field"""
        field = getattr(self.model_class, field_name)
        return self.session.query(self.model_class).filter(field == value).first()
    
    @with_retry()
    def get_multiple(self, 
                    filters: Optional[Dict[str, Any]] = None,
                    order_by: Optional[str] = None,
                    limit: Optional[int] = None,
                    offset: Optional[int] = None) -> List[T]:
        """Get multiple records with filtering and pagination"""
        query = self.session.query(self.model_class)
        
        if filters:
            for field_name, value in filters.items():
                field = getattr(self.model_class, field_name)
                if isinstance(value, list):
                    query = query.filter(field.in_(value))
                elif isinstance(value, dict) and 'op' in value:
                    # Support for complex operations
                    op = value['op']
                    val = value['value']
                    if op == 'gt':
                        query = query.filter(field > val)
                    elif op == 'lt':
                        query = query.filter(field < val)
                    elif op == 'gte':
                        query = query.filter(field >= val)
                    elif op == 'lte':
                        query = query.filter(field <= val)
                    elif op == 'like':
                        query = query.filter(field.like(f"%{val}%"))
                else:
                    query = query.filter(field == value)
        
        if order_by:
            if order_by.startswith('-'):
                query = query.order_by(desc(getattr(self.model_class, order_by[1:])))
            else:
                query = query.order_by(asc(getattr(self.model_class, order_by)))
        
        if offset:
            query = query.offset(offset)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @with_retry()
    def update(self, obj_id: Union[int, str], **kwargs) -> Optional[T]:
        """Update record by ID"""
        obj = self.get_by_id(obj_id)
        if not obj:
            return None
        
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        
        # Update timestamp if model has updated_at field
        if hasattr(obj, 'updated_at'):
            setattr(obj, 'updated_at', datetime.now(timezone.utc))
        
        self.session.flush()
        self.logger.debug(f"Updated {self.model_class.__name__} with id: {obj_id}")
        return obj
    
    @with_retry()
    def delete(self, obj_id: Union[int, str]) -> bool:
        """Delete record by ID"""
        obj = self.get_by_id(obj_id)
        if not obj:
            return False
        
        self.session.delete(obj)
        self.session.flush()
        self.logger.debug(f"Deleted {self.model_class.__name__} with id: {obj_id}")
        return True
    
    @with_retry()
    def soft_delete(self, obj_id: Union[int, str]) -> bool:
        """Soft delete record (if model supports it)"""
        obj = self.get_by_id(obj_id)
        if not obj:
            return False
        
        if hasattr(obj, 'is_deleted'):
            setattr(obj, 'is_deleted', True)
            if hasattr(obj, 'deleted_at'):
                setattr(obj, 'deleted_at', datetime.now(timezone.utc))
            self.session.flush()
            self.logger.debug(f"Soft deleted {self.model_class.__name__} with id: {obj_id}")
            return True
        
        return False
    
    @with_retry()
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filtering"""
        query = self.session.query(self.model_class)
        
        if filters:
            for field_name, value in filters.items():
                field = getattr(self.model_class, field_name)
                query = query.filter(field == value)
        
        return query.count()
    
    @with_retry()
    def exists(self, **kwargs) -> bool:
        """Check if record exists"""
        query = self.session.query(self.model_class)
        for field_name, value in kwargs.items():
            field = getattr(self.model_class, field_name)
            query = query.filter(field == value)
        
        return query.first() is not None
    
    @with_retry()
    def bulk_create(self, objects_data: List[Dict[str, Any]]) -> List[T]:
        """Bulk create multiple records"""
        objects = [self.model_class(**data) for data in objects_data]
        self.session.add_all(objects)
        self.session.flush()
        self.logger.debug(f"Bulk created {len(objects)} {self.model_class.__name__} records")
        return objects
    
    @with_retry()
    def bulk_update(self, updates: List[Dict[str, Any]]) -> int:
        """Bulk update multiple records"""
        if not updates or 'id' not in updates[0]:
            return 0
        
        stmt = update(self.model_class)
        result = self.session.execute(stmt, updates)
        affected_rows = result.rowcount
        self.logger.debug(f"Bulk updated {affected_rows} {self.model_class.__name__} records")
        return affected_rows


class TransactionManager:
    """Advanced transaction management with savepoints and nested transactions"""
    
    def __init__(self, session: Session):
        self.session = session
        self.savepoints = []
        self.logger = logging.getLogger("chatbot.transaction")
    
    @contextmanager
    def savepoint(self, name: Optional[str] = None):
        """Create a savepoint within transaction"""
        savepoint_name = name or f"sp_{len(self.savepoints) + 1}"
        savepoint = self.session.begin_nested()
        self.savepoints.append(savepoint_name)
        
        try:
            self.logger.debug(f"Created savepoint: {savepoint_name}")
            yield savepoint
            savepoint.commit()
            self.logger.debug(f"Committed savepoint: {savepoint_name}")
        except Exception as e:
            savepoint.rollback()
            self.logger.warning(f"Rolled back savepoint {savepoint_name}: {str(e)}")
            raise
        finally:
            if savepoint_name in self.savepoints:
                self.savepoints.remove(savepoint_name)
    
    @contextmanager
    def read_only_transaction(self):
        """Create read-only transaction"""
        self.session.execute(text("SET TRANSACTION READ ONLY"))
        try:
            yield
        finally:
            # Reset to default
            self.session.execute(text("SET TRANSACTION READ WRITE"))


class AdvancedQueryBuilder:
    """Advanced query builder with fluent interface"""
    
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
        self.query = session.query(model_class)
        self._joins = []
        self._filters = []
        self._order_by = []
        self._group_by = []
        self._having = []
    
    def join(self, *args, **kwargs):
        """Add join to query"""
        self.query = self.query.join(*args, **kwargs)
        return self
    
    def filter(self, *criterion):
        """Add filter criteria"""
        self.query = self.query.filter(*criterion)
        return self
    
    def filter_by(self, **kwargs):
        """Add filter by keyword arguments"""
        self.query = self.query.filter_by(**kwargs)
        return self
    
    def order_by(self, *criterion):
        """Add order by criteria"""
        self.query = self.query.order_by(*criterion)
        return self
    
    def group_by(self, *criterion):
        """Add group by criteria"""
        self.query = self.query.group_by(*criterion)
        return self
    
    def having(self, *criterion):
        """Add having criteria"""
        self.query = self.query.having(*criterion)
        return self
    
    def limit(self, limit: int):
        """Add limit"""
        self.query = self.query.limit(limit)
        return self
    
    def offset(self, offset: int):
        """Add offset"""
        self.query = self.query.offset(offset)
        return self
    
    def distinct(self, *criterion):
        """Add distinct"""
        self.query = self.query.distinct(*criterion)
        return self
    
    def with_entities(self, *entities):
        """Select specific entities"""
        self.query = self.query.with_entities(*entities)
        return self
    
    def paginate(self, page: int, per_page: int = 20):
        """Add pagination"""
        offset = (page - 1) * per_page
        self.query = self.query.offset(offset).limit(per_page)
        return self
    
    def text_search(self, field_name: str, search_term: str):
        """Add full-text search (PostgreSQL specific)"""
        field = getattr(self.model_class, field_name)
        self.query = self.query.filter(
            func.to_tsvector('english', field).match(search_term)
        )
        return self
    
    def execute(self):
        """Execute the query"""
        return self.query.all()
    
    def first(self):
        """Get first result"""
        return self.query.first()
    
    def one(self):
        """Get exactly one result"""
        return self.query.one()
    
    def one_or_none(self):
        """Get one result or None"""
        return self.query.one_or_none()
    
    def count(self):
        """Count results"""
        return self.query.count()
    
    def exists(self):
        """Check if any results exist"""
        return self.session.query(self.query.exists()).scalar()


class CacheManager:
    """Simple in-memory cache for database queries"""
    
    def __init__(self, default_ttl: int = 300):
        self.cache = {}
        self.ttl = {}
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        with self._lock:
            if key in self.cache:
                if datetime.now(timezone.utc) < self.ttl[key]:
                    return self.cache[key]
                else:
                    # Expired
                    del self.cache[key]
                    del self.ttl[key]
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cached value"""
        ttl = ttl or self.default_ttl
        with self._lock:
            self.cache[key] = value
            self.ttl[key] = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    
    def delete(self, key: str) -> None:
        """Delete cached value"""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                del self.ttl[key]
    
    def clear(self) -> None:
        """Clear all cached values"""
        with self._lock:
            self.cache.clear()
            self.ttl.clear()


class SecurityManager:
    """Database security utilities"""
    
    @staticmethod
    def sanitize_input(value: str) -> str:
        """Basic input sanitization"""
        if not isinstance(value, str):
            return value
        
        # Remove potential SQL injection patterns
        dangerous_patterns = [
            ';', '--', '/*', '*/', 'xp_', 'sp_', 'exec', 'execute',
            'select', 'insert', 'update', 'delete', 'drop', 'alter',
            'create', 'union', 'script'
        ]
        
        sanitized = value
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern.lower(), '')
            sanitized = sanitized.replace(pattern.upper(), '')
        
        return sanitized
    
    @staticmethod
    def validate_permissions(user_id: int, resource_type: str, action: str) -> bool:
        """Validate user permissions (implement according to your auth system)"""
        # This would integrate with your actual permission system
        return True
    
    @staticmethod
    def audit_log(action: str, user_id: int, resource_type: str, resource_id: str, details: Dict[str, Any]):
        """Log security-relevant actions"""
        logger = logging.getLogger("chatbot.security")
        logger.info(f"AUDIT: {action} - User: {user_id}, Resource: {resource_type}:{resource_id}, Details: {details}")


# Example usage and specialized repositories

class UserRepository(BaseRepository):
    """Specialized repository for User operations"""
    
    def get_active_users(self) -> List:
        """Get all active users"""
        return self.get_multiple(filters={"status": "active"})
    
    def get_by_username(self, username: str) -> Optional[object]:
        """Get user by username"""
        return self.get_by_field("username", username)
    
    def get_by_email(self, email: str) -> Optional[object]:
        """Get user by email"""
        return self.get_by_field("email", email)
    
    def search_users(self, search_term: str, limit: int = 50):
        """Search users by username or display name"""
        builder = AdvancedQueryBuilder(self.session, self.model_class)
        # This would need the actual User model imported
        # builder.filter(or_(
        #     User.username.ilike(f"%{search_term}%"),
        #     User.display_name.ilike(f"%{search_term}%")
        # )).limit(limit)
        return builder.execute()


class ConversationRepository(BaseRepository):
    """Specialized repository for Conversation operations"""
    
    def get_user_conversations(self, user_id: int, include_archived: bool = False):
        """Get conversations for a user"""
        filters = {"created_by": user_id}
        if not include_archived:
            filters["is_archived"] = False
        return self.get_multiple(filters=filters, order_by="-updated_at")
    
    def get_recent_conversations(self, limit: int = 20):
        """Get most recent conversations"""
        return self.get_multiple(order_by="-updated_at", limit=limit)


class MessageRepository(BaseRepository):
    """Specialized repository for Message operations"""
    
    def get_conversation_messages(self, conversation_id: int, limit: int = 100):
        """Get messages for a conversation"""
        return self.get_multiple(
            filters={"conversation_id": conversation_id, "is_deleted": False},
            order_by="created_at",
            limit=limit
        )
    
    def search_messages(self, search_term: str, conversation_id: Optional[int] = None):
        """Search messages by content"""
        builder = AdvancedQueryBuilder(self.session, self.model_class)
        builder.text_search("content", search_term)
        
        if conversation_id:
            builder.filter_by(conversation_id=conversation_id)
        
        return builder.execute()


# Example usage:
"""
# Initialize settings
settings = DatabaseSettings()

# Create database manager
with create_db_manager_from_settings(settings) as db_manager:
    # Get a session
    with db_manager.get_session() as session:
        # Create repositories
        user_repo = UserRepository(session, User)
        conversation_repo = ConversationRepository(session, Conversation)
        message_repo = MessageRepository(session, Message)
        
        # Create a new user
        user = user_repo.create(
            username="john_doe",
            email="john@example.com",
            user_type="registered",
            display_name="John Doe"
        )
        
        # Create a conversation
        conversation = conversation_repo.create(
            type="direct",
            name="Test Conversation",
            created_by=user.id
        )
        
        # Create a message
        message = message_repo.create(
            conversation_id=conversation.id,
            sender_id=user.id,
            content="Hello, world!",
            message_type="text"
        )
        
        # Advanced queries
        recent_conversations = conversation_repo.get_recent_conversations(10)
        active_users = user_repo.get_active_users()
        
        # Performance monitoring
        health_status = db_manager.health_check()
        print(f"Database health: {health_status}")
"""