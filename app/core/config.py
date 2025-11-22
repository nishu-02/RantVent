from pydantic_settings import BaseSettings
from pydantic import AnyUrl
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "Vent API"
    ENV: str = "dev"

    # Database
    DATABASE_URL: AnyUrl

    # GEMINI
    GEMINI_API_KEY: str

    # media
    MEDIA_ROOT: str = "media"
    AUDIO_SUBDIR: str = "audio"

    AUDIO_RETENTION_DAYS: int = 21

    DEBUG: bool = True
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()