try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except Exception:
    from pydantic import BaseSettings

from pydantic import AnyUrl, field_validator
from functools import lru_cache
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    PROJECT_NAME: str = "Vent API"
    ENV: str = "dev"

    # Database
    DATABASE_URL: AnyUrl

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # GEMINI (optional - allow running without key in dev)
    GEMINI_API_KEY: Optional[str] = None

    # media
    MEDIA_ROOT: str = "media"
    AUDIO_SUBDIR: str = "audio"

    AUDIO_RETENTION_DAYS: int = 21

    # Voice anonymizer presets (semi-colon separated tuples of pitch,frequency_shift,time_factor)
    VOICE_PRESETS: str

    # JWT settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS origins: comma-separated string (e.g., "http://localhost:3000,http://example.com" or "*")
    CORS_ORIGINS: str = "*"
    DEBUG: bool = True

    model_config = SettingsConfigDict(env_file=str(Path(__file__).parent.parent.parent / ".env"))

    @property
    def cors_origins_list(self) -> list[str]:
        """Convert comma-separated CORS_ORIGINS string to a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def voice_presets(self) -> list[tuple[float, float, float]]:
        """Parse voice presets from environment variable string."""
        presets = []
        for preset_str in self.VOICE_PRESETS.split(";"):
            values = tuple(float(v.strip()) for v in preset_str.split(","))
            presets.append(values)
        return presets


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Module-level cached settings instance for convenient imports (e.g. `from app.core.config import settings`).
settings = get_settings()