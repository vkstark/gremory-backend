from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    GOOGLE_API_KEY: Optional[str] = None
    INCLUDE_REASONING: bool = False
    LOG_LEVEL: str = "INFO"
    # Model Settings
    MAX_HISTORY_LENGTH: int = 10
    ENABLE_SUMMARIZATION: bool = True
    SUMMARY_THRESHOLD: int = 10
    
    # OPENAI MODEL SETTINGS
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 2048
    OPENAI_TIMEOUT: int = 60

    # DATABASE SETTINGS
    DB_HOST: str = None
    DB_PORT: int = 5432
    DB_NAME: str = None
    DB_USER: str = None
    DB_PASSWORD: str = None
    DB_SCHEMA: str = "public"
    DB_MIN_CONNECTIONS: int = 1
    DB_MAX_CONNECTIONS: int = 10
    # Connection pool settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True
    
    # Query settings
    DB_QUERY_TIMEOUT: int = 30
    DB_SLOW_QUERY_THRESHOLD: float = 1.0
    
    # Retry settings
    DB_MAX_RETRIES: int = 3
    DB_RETRY_DELAY: float = 0.5
    
    # Security
    DB_ENABLE_SSL: bool = True
    DB_SSL_CERT_PATH: Optional[str] = None
    
    # Logging
    DB_LOG_LEVEL: str = "INFO"
    DB_LOG_QUERIES: bool = False
    DB_LOG_SLOW_QUERIES: bool = True

    # URL Structure
    CHAT_SERVICE_URL: Optional[str] = Field(
        default="http://localhost:8000/chat",
        description="Base URL for the chat service"
    )
    PERSONALIZATION_SERVICE_URL: Optional[str] = Field(
        default="http://localhost:8004/personalization",
        description="Base URL for the personalization service"
    )
    USER_HISTORY_SERVICE_URL: Optional[str] = Field(
        default="http://localhost:8003/user-history",
        description="Base URL for the user history service"
    )
    USERS_SERVICE_URL: Optional[str] = Field(
        default="http://localhost:8002/users",
        description="Base URL for the users service"
    )
    EXT_TOOLS_SERVICE_URL: Optional[str] = Field(
        default="http://localhost:8005/ext-tools",
        description="Base URL for the external tools service"
    )
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
