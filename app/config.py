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
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
