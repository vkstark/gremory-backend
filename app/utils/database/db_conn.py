# from sqlalchemy import create_engine, text, inspect, MetaData, Table, Column, Integer, String, DateTime, Boolean
# from sqlalchemy.engine import Engine
# from sqlalchemy.orm import sessionmaker, Session, declarative_base
# from sqlalchemy.pool import QueuePool
# from sqlalchemy.exc import SQLAlchemyError
# import logging
# import json
# import threading
# from typing import List, Dict, Any, Optional, Union, Type
# from contextlib import contextmanager
# from dataclasses import dataclass
# from datetime import datetime
# import os

# from app.config import Settings

# # SQLAlchemy Base for ORM models
# Base = declarative_base()

# @dataclass
# class DatabaseConfig:
#     """Database configuration dataclass"""
#     host: str
#     port: int
#     database: str
#     user: str
#     password: str
#     schema: str = "public"
#     min_connections: int = 1
#     max_connections: int = 20
#     pool_timeout: int = 30
#     pool_recycle: int = 3600
#     echo: bool = False
    
#     @classmethod
#     def from_settings(cls, settings: Settings) -> 'DatabaseConfig':
#         """Create DatabaseConfig from Pydantic Settings"""
#         if not all([settings.DB_HOST, settings.DB_NAME, settings.DB_USER]):
#             raise ValueError("DB_HOST, DB_NAME, and DB_USER must be provided")
        
#         return cls(
#             host=settings.DB_HOST,
#             port=settings.DB_PORT,
#             database=settings.DB_NAME,
#             user=settings.DB_USER,
#             password=settings.DB_PASSWORD or "",
#             schema=settings.DB_SCHEMA or "public",
#             min_connections=settings.DB_MIN_CONNECTIONS,
#             max_connections=settings.DB_MAX_CONNECTIONS,
#             echo=getattr(settings, 'DB_ECHO', False)
#         )
    
#     def get_database_url(self) -> str:
#         """Generate SQLAlchemy database URL"""
#         password_part = f":{self.password}" if self.password else ""
#         return f"postgresql://{self.user}{password_part}@{self.host}:{self.port}/{self.database}"


# class DatabaseManager:
#     """
#     Production-ready SQLAlchemy database manager with connection pooling,
#     thread safety, error handling, and CRUD operations.
#     """
    
#     def __init__(self, config: DatabaseConfig):
#         self.config = config
#         self.engine: Optional[Engine] = None
#         self.SessionLocal: Optional[sessionmaker] = None
#         self.metadata = MetaData(schema=config.schema if config.schema != "public" else None)
#         self.logger = self._setup_logging()
        
#         # Thread safety locks
#         self._engine_lock = threading.RLock()
#         self._logging_lock = threading.Lock()
#         self._stats_lock = threading.Lock()
        
#         # Connection statistics
#         self._stats = {
#             'total_connections': 0,
#             'active_connections': 0,
#             'failed_connections': 0,
#             'queries_executed': 0,
#             'transactions_committed': 0,
#             'transactions_rolled_back': 0
#         }
        
#         self._create_engine()
    
#     def _setup_logging(self) -> logging.Logger:
#         """Setup thread-safe logging for database operations"""
#         logger = logging.getLogger(f'DatabaseManager-{id(self)}')
#         logger.setLevel(logging.INFO)
        
#         if not logger.handlers:
#             handler = logging.StreamHandler()
#             formatter = logging.Formatter(
#                 '%(asctime)s - %(name)s - %(levelname)s - [Thread-%(thread)d] - %(message)s'
#             )
#             handler.setFormatter(formatter)
#             logger.addHandler(handler)
        
#         return logger
    
#     def _log_safely(self, level: str, message: str):
#         """Thread-safe logging method"""
#         with self._logging_lock:
#             getattr(self.logger, level.lower())(message)
    
#     def _update_stats(self, stat_name: str, increment: int = 1):
#         """Thread-safe statistics update"""
#         with self._stats_lock:
#             self._stats[stat_name] += increment
    
#     def _format_table_name(self, table: str) -> str:
#         """Format table name with schema prefix if needed"""
#         if '.' in table:
#             return table
#         return f"{self.config.schema}.{table}" if self.config.schema != "public" else table
    
#     def _validate_identifier(self, identifier: str) -> bool:
#         """Validate SQL identifier (table/column name) to prevent injection"""
#         parts = identifier.split('.')
#         if len(parts) > 2:
#             return False
        
#         for part in parts:
#             if not part.replace('_', '').isalnum() or part.startswith('_'):
#                 return False
#         return True
    
#     def _create_engine(self):
#         """Create SQLAlchemy engine with connection pooling"""
#         with self._engine_lock:
#             try:
#                 if self.engine is not None:
#                     self._log_safely('warning', "Engine already exists, disposing existing engine")
#                     self.engine.dispose()
                
#                 database_url = self.config.get_database_url()
                
#                 self.engine = create_engine(
#                     database_url,
#                     poolclass=QueuePool,
#                     pool_size=self.config.min_connections,
#                     max_overflow=self.config.max_connections - self.config.min_connections,
#                     pool_timeout=self.config.pool_timeout,
#                     pool_recycle=self.config.pool_recycle,
#                     pool_pre_ping=True,  # Verify connections before use
#                     echo=self.config.echo,
#                     connect_args={
#                         "options": f"-csearch_path={self.config.schema}"
#                     } if self.config.schema != "public" else {}
#                 )
                
#                 # Create session factory
#                 self.SessionLocal = sessionmaker(
#                     bind=self.engine,
#                     autocommit=False,
#                     autoflush=False
#                 )
                
#                 self._log_safely('info', "SQLAlchemy engine created successfully")
                
#             except Exception as e:
#                 self._update_stats('failed_connections')
#                 self._log_safely('error', f"Failed to create engine: {e}")
#                 raise
    
#     @contextmanager
#     def get_session(self, autocommit: bool = True):
#         """Thread-safe context manager for database sessions"""
#         if not self.SessionLocal:
#             raise RuntimeError("Database engine is not initialized")
        
#         session = None
#         try:
#             session = self.SessionLocal()
#             self._update_stats('total_connections')
#             self._update_stats('active_connections')
            
#             yield session
            
#             if autocommit:
#                 session.commit()
#                 self._update_stats('transactions_committed')
            
#         except Exception as e:
#             if session:
#                 session.rollback()
#                 self._update_stats('transactions_rolled_back')
#             self._update_stats('failed_connections')
#             self._log_safely('error', f"Database session operation failed: {e}")
#             raise
#         finally:
#             if session:
#                 session.close()
#                 self._update_stats('active_connections', -1)
    
#     @contextmanager
#     def get_connection(self):
#         """Thread-safe context manager for raw database connections"""
#         if not self.engine:
#             raise RuntimeError("Database engine is not initialized")
        
#         connection = None
#         try:
#             connection = self.engine.connect()
#             self._update_stats('total_connections')
#             self._update_stats('active_connections')
            
#             yield connection
            
#         except Exception as e:
#             if connection:
#                 connection.rollback()
#             self._update_stats('failed_connections')
#             self._log_safely('error', f"Database connection operation failed: {e}")
#             raise
#         finally:
#             if connection:
#                 connection.close()
#                 self._update_stats('active_connections', -1)
    
#     def execute_query(self, query: str, params: Dict[str, Any] = None, fetch: bool = True) -> Optional[List[Dict]]:
#         """
#         Execute a SQL query with optional parameters (thread-safe)
        
#         Args:
#             query: SQL query string
#             params: Query parameters dictionary
#             fetch: Whether to fetch results
            
#         Returns:
#             Query results as list of dictionaries if fetch=True, None otherwise
#         """
#         try:
#             with self.get_connection() as connection:
#                 result = connection.execute(text(query), params or {})
#                 self._update_stats('queries_executed')
                
#                 if fetch and result.returns_rows:
#                     # Convert results to list of dictionaries
#                     columns = result.keys()
#                     rows = result.fetchall()
#                     return [dict(zip(columns, row)) for row in rows]
                
#                 return None
                
#         except Exception as e:
#             self._log_safely('error', f"Query execution failed: {query[:100]}... Error: {e}")
#             raise
    
#     def insert(self, table: str, data: Dict[str, Any], returning: str = None) -> Optional[Any]:
#         """
#         Insert a record into a table using SQLAlchemy Core
        
#         Args:
#             table: Table name (can include schema: 'schema.table' or just 'table')
#             data: Dictionary of column-value pairs
#             returning: Column to return after insert (e.g., 'id')
            
#         Returns:
#             Value of returning column if specified, None otherwise
#         """
#         if not data:
#             raise ValueError("Data dictionary cannot be empty")
        
#         if not self._validate_identifier(table):
#             raise ValueError("Invalid table name")
        
#         try:
#             with self.get_session() as session:
#                 # Reflect the table
#                 table_obj = Table(
#                     table.split('.')[-1],  # Remove schema prefix for table name
#                     self.metadata,
#                     autoload_with=self.engine,
#                     schema=self.config.schema if self.config.schema != "public" else None
#                 )
                
#                 # Insert data
#                 insert_stmt = table_obj.insert().values(**data)
                
#                 if returning:
#                     insert_stmt = insert_stmt.returning(getattr(table_obj.c, returning))
#                     result = session.execute(insert_stmt)
#                     returned_value = result.scalar()
                    
#                     self._log_safely('info', f"Successfully inserted record into {table}")
#                     return returned_value
#                 else:
#                     session.execute(insert_stmt)
#                     self._log_safely('info', f"Successfully inserted record into {table}")
#                     return None
                
#         except Exception as e:
#             self._log_safely('error', f"Insert failed for table {table}: {e}")
#             raise
    
#     def update(self, table: str, data: Dict[str, Any], where_clause: str, where_params: Dict[str, Any] = None) -> int:
#         """
#         Update records in a table using SQLAlchemy Core
        
#         Args:
#             table: Table name (can include schema: 'schema.table' or just 'table')
#             data: Dictionary of column-value pairs to update
#             where_clause: WHERE clause condition
#             where_params: Parameters for WHERE clause
            
#         Returns:
#             Number of affected rows
#         """
#         if not data:
#             raise ValueError("Data dictionary cannot be empty")
        
#         if not self._validate_identifier(table):
#             raise ValueError("Invalid table name")
        
#         try:
#             with self.get_session() as session:
#                 # Reflect the table
#                 table_obj = Table(
#                     table.split('.')[-1],
#                     self.metadata,
#                     autoload_with=self.engine,
#                     schema=self.config.schema if self.config.schema != "public" else None
#                 )
                
#                 # Build update statement
#                 update_stmt = table_obj.update().values(**data)
                
#                 if where_clause:
#                     update_stmt = update_stmt.where(text(where_clause))
                
#                 result = session.execute(update_stmt, where_params or {})
#                 affected_rows = result.rowcount
                
#                 self._log_safely('info', f"Updated {affected_rows} rows in {table}")
#                 return affected_rows
                
#         except Exception as e:
#             self._log_safely('error', f"Update failed for table {table}: {e}")
#             raise
    
#     def delete(self, table: str, where_clause: str, where_params: Dict[str, Any] = None) -> int:
#         """
#         Delete records from a table using SQLAlchemy Core
        
#         Args:
#             table: Table name (can include schema: 'schema.table' or just 'table')
#             where_clause: WHERE clause condition
#             where_params: Parameters for WHERE clause
            
#         Returns:
#             Number of deleted rows
#         """
#         if not self._validate_identifier(table):
#             raise ValueError("Invalid table name")
        
#         try:
#             with self.get_session() as session:
#                 # Reflect the table
#                 table_obj = Table(
#                     table.split('.')[-1],
#                     self.metadata,
#                     autoload_with=self.engine,
#                     schema=self.config.schema if self.config.schema != "public" else None
#                 )
                
#                 # Build delete statement
#                 delete_stmt = table_obj.delete()
                
#                 if where_clause:
#                     delete_stmt = delete_stmt.where(text(where_clause))
                
#                 result = session.execute(delete_stmt, where_params or {})
#                 deleted_rows = result.rowcount
                
#                 self._log_safely('info', f"Deleted {deleted_rows} rows from {table}")
#                 return deleted_rows
                
#         except Exception as e:
#             self._log_safely('error', f"Delete failed for table {table}: {e}")
#             raise
    
#     def select(self, table: str, columns: List[str] = None, where_clause: str = None, 
#               where_params: Dict[str, Any] = None, order_by: str = None, limit: int = None) -> List[Dict]:
#         """
#         Select records from a table using SQLAlchemy Core
        
#         Args:
#             table: Table name (can include schema: 'schema.table' or just 'table')
#             columns: List of columns to select (default: all columns)
#             where_clause: WHERE clause condition
#             where_params: Parameters for WHERE clause
#             order_by: ORDER BY clause
#             limit: LIMIT value
            
#         Returns:
#             List of dictionaries representing rows
#         """
#         if not self._validate_identifier(table):
#             raise ValueError("Invalid table name")
        
#         try:
#             with self.get_session(autocommit=False) as session:
#                 # Reflect the table
#                 table_obj = Table(
#                     table.split('.')[-1],
#                     self.metadata,
#                     autoload_with=self.engine,
#                     schema=self.config.schema if self.config.schema != "public" else None
#                 )
                
#                 # Build select statement
#                 if columns:
#                     select_columns = [getattr(table_obj.c, col) for col in columns]
#                     select_stmt = session.query(*select_columns)
#                 else:
#                     select_stmt = session.query(table_obj)
                
#                 if where_clause:
#                     select_stmt = select_stmt.filter(text(where_clause))
#                     if where_params:
#                         select_stmt = select_stmt.params(**where_params)
                
#                 if order_by:
#                     select_stmt = select_stmt.order_by(text(order_by))
                
#                 if limit:
#                     select_stmt = select_stmt.limit(limit)
                
#                 result = select_stmt.all()
                
#                 # Convert to list of dictionaries
#                 if columns:
#                     return [dict(zip(columns, row)) for row in result]
#                 else:
#                     return [row._asdict() if hasattr(row, '_asdict') else dict(row._mapping) for row in result]
                
#         except Exception as e:
#             self._log_safely('error', f"Select failed for table {table}: {e}")
#             raise
    
#     def bulk_insert(self, table: str, data_list: List[Dict[str, Any]]) -> None:
#         """
#         Bulk insert multiple records using SQLAlchemy Core
        
#         Args:
#             table: Table name (can include schema: 'schema.table' or just 'table')
#             data_list: List of dictionaries with column-value pairs
#         """
#         if not data_list:
#             return
        
#         if not self._validate_identifier(table):
#             raise ValueError("Invalid table name")
        
#         try:
#             with self.get_session() as session:
#                 # Reflect the table
#                 table_obj = Table(
#                     table.split('.')[-1],
#                     self.metadata,
#                     autoload_with=self.engine,
#                     schema=self.config.schema if self.config.schema != "public" else None
#                 )
                
#                 # Bulk insert
#                 session.execute(table_obj.insert(), data_list)
#                 self._log_safely('info', f"Bulk inserted {len(data_list)} records into {table}")
                
#         except Exception as e:
#             self._log_safely('error', f"Bulk insert failed for table {table}: {e}")
#             raise
    
#     def table_exists(self, table_name: str) -> bool:
#         """Check if a table exists using SQLAlchemy Inspector"""
#         try:
#             inspector = inspect(self.engine)
#             schema = self.config.schema if self.config.schema != "public" else None
#             tables = inspector.get_table_names(schema=schema)
#             return table_name in tables
#         except Exception as e:
#             self._log_safely('error', f"Error checking table existence: {e}")
#             return False
    
#     def get_table_columns(self, table_name: str) -> List[Dict]:
#         """Get column information for a table using SQLAlchemy Inspector"""
#         try:
#             inspector = inspect(self.engine)
#             schema = self.config.schema if self.config.schema != "public" else None
#             columns = inspector.get_columns(table_name, schema=schema)
            
#             # Convert to format similar to original
#             return [
#                 {
#                     'column_name': col['name'],
#                     'data_type': str(col['type']),
#                     'is_nullable': col['nullable'],
#                     'column_default': col.get('default')
#                 }
#                 for col in columns
#             ]
#         except Exception as e:
#             self._log_safely('error', f"Error getting table columns: {e}")
#             return []
    
#     def get_connection_stats(self) -> Dict[str, Any]:
#         """Get connection pool statistics (thread-safe)"""
#         with self._stats_lock:
#             stats = self._stats.copy()
        
#         # Add pool-specific stats if available
#         with self._engine_lock:
#             if self.engine and self.engine.pool:
#                 try:
#                     pool = self.engine.pool
#                     stats.update({
#                         'pool_size': pool.size(),
#                         'pool_checked_in': pool.checkedin(),
#                         'pool_checked_out': pool.checkedout(),
#                         'pool_overflow': pool.overflow(),
#                         'pool_invalid': pool.invalid()
#                     })
#                 except Exception as e:
#                     self._log_safely('warning', f"Could not get pool stats: {e}")
        
#         return stats
    
#     def health_check(self) -> bool:
#         """Perform a health check on the database connection"""
#         try:
#             result = self.execute_query("SELECT 1 as health_check")
#             return result is not None and len(result) > 0
#         except Exception as e:
#             self._log_safely('error', f"Health check failed: {e}")
#             return False
    
#     def create_tables(self, models: List[Type[Base]] = None):
#         """Create tables for given models or all models"""
#         try:
#             if models:
#                 for model in models:
#                     model.__table__.create(bind=self.engine, checkfirst=True)
#             else:
#                 Base.metadata.create_all(bind=self.engine)
#             self._log_safely('info', "Tables created successfully")
#         except Exception as e:
#             self._log_safely('error', f"Failed to create tables: {e}")
#             raise
    
#     def drop_tables(self, models: List[Type[Base]] = None):
#         """Drop tables for given models or all models"""
#         try:
#             if models:
#                 for model in models:
#                     model.__table__.drop(bind=self.engine, checkfirst=True)
#             else:
#                 Base.metadata.drop_all(bind=self.engine)
#             self._log_safely('info', "Tables dropped successfully")
#         except Exception as e:
#             self._log_safely('error', f"Failed to drop tables: {e}")
#             raise
    
#     def get_engine(self) -> Engine:
#         """Get the SQLAlchemy engine instance"""
#         return self.engine
    
#     def get_session_factory(self) -> sessionmaker:
#         """Get the session factory"""
#         return self.SessionLocal
    
#     def close_all_connections(self):
#         """Close all connections and dispose of the engine"""
#         with self._engine_lock:
#             if self.engine:
#                 self.engine.dispose()
#                 self.engine = None
#                 self.SessionLocal = None
#                 self._log_safely('info', "All database connections closed and engine disposed")
    
#     def __enter__(self):
#         """Context manager entry"""
#         return self
    
#     def __exit__(self, exc_type, exc_val, exc_tb):
#         """Context manager exit"""
#         self.close_all_connections()


# # Example ORM Model
# class User(Base):
#     __tablename__ = 'users'
    
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     name = Column(String(100), nullable=False)
#     email = Column(String(255), unique=True, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     is_active = Column(Boolean, default=True)


# # Factory function to create DatabaseManager from Pydantic Settings
# def create_db_manager_from_settings(settings: Settings = None) -> DatabaseManager:
#     """Create DatabaseManager instance from Pydantic Settings"""
#     if settings is None:
#         settings = Settings()
    
#     config = DatabaseConfig.from_settings(settings)
#     return DatabaseManager(config)


# # Factory function to create DatabaseManager from config file
# def create_db_manager_from_config(config_path: str) -> DatabaseManager:
#     """Create DatabaseManager instance from JSON config file"""
#     with open(config_path, 'r') as f:
#         config_data = json.load(f)
    
#     config = DatabaseConfig(**config_data)
#     return DatabaseManager(config)


# # Dependency injection for FastAPI (if using FastAPI)
# def get_db_session(db_manager: DatabaseManager):
#     """Dependency function for FastAPI to get database session"""
#     with db_manager.get_session() as session:
#         yield session


# # Example usage
# if __name__ == "__main__":
#     # Using Pydantic Settings (recommended)
#     settings = Settings()
    
#     try:
#         with create_db_manager_from_settings(settings) as db:
#             # Health check
#             if db.health_check():
#                 print("Database connection is healthy")
                
#                 # Create tables
#                 db.create_tables([User])
                
#                 # Example operations using Core API
#                 # Create a user
#                 user_id = db.insert(
#                     'users', 
#                     {'name': 'John Doe', 'email': 'john@example.com'},
#                     returning='id'
#                 )
#                 print(f"Created user with ID: {user_id}")
                
#                 # Read users
#                 users = db.select('users', where_clause='id = :user_id', where_params={'user_id': user_id})
#                 print(f"Found user: {users}")
                
#                 # Update user
#                 affected_rows = db.update(
#                     'users', 
#                     {'name': 'Jane Doe'}, 
#                     'id = :user_id', 
#                     {'user_id': user_id}
#                 )
#                 print(f"Updated {affected_rows} rows")
                
#                 # Bulk insert
#                 bulk_data = [
#                     {'name': 'User 1', 'email': 'user1@example.com'},
#                     {'name': 'User 2', 'email': 'user2@example.com'},
#                     {'name': 'User 3', 'email': 'user3@example.com'}
#                 ]
#                 db.bulk_insert('users', bulk_data)
#                 print("Bulk insert completed")
                
#                 # Example using ORM
#                 with db.get_session() as session:
#                     # Query using ORM
#                     orm_users = session.query(User).filter(User.name.like('%User%')).all()
#                     print(f"ORM query found {len(orm_users)} users")
                    
#                     # Create user using ORM
#                     new_user = User(name='ORM User', email='orm@example.com')
#                     session.add(new_user)
#                     session.commit()
#                     print(f"Created ORM user with ID: {new_user.id}")
                
#                 # Get stats
#                 stats = db.get_connection_stats()
#                 print(f"Connection stats: {stats}")
                
#                 # Check table info
#                 columns = db.get_table_columns('users')
#                 print(f"Table columns: {columns}")
                
#             else:
#                 print("Database health check failed")
                
#     except Exception as e:
#         print(f"Database operation failed: {e}")