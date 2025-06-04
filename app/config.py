from pydantic_settings import BaseSettings
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
