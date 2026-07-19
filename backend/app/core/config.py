import os
import warnings
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

DEFAULT_API_KEY = "dev-api-key-change-in-production"


class Settings(BaseSettings):
    environment: str = Field(
        default="development",
        description="Deployment environment: development | production",
    )
    database_url: str = Field(
        default="postgresql+asyncpg://signum:signum_pass@localhost:5432/signum",
        description="PostgreSQL connection URL for async operations",
    )
    database_url_sync: str = Field(
        default="postgresql://signum:signum_pass@localhost:5432/signum",
        description="PostgreSQL connection URL for synchronous operations",
    )
    api_key: str = Field(
        default=DEFAULT_API_KEY,
        description="API authentication key",
    )
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="CORS allowed origins (comma-separated)",
    )
    log_level: str = Field(default="DEBUG", description="Logging level")
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    firecrawl_api_key: str = Field(
        default="", description="Firecrawl API key for India job scraping"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if v == DEFAULT_API_KEY:
            env = os.environ.get("ENVIRONMENT", "development").lower()
            if env == "production":
                raise ValueError(
                    "API key is still the default placeholder. Set SIGNUM_API_KEY "
                    "to a strong secret before deploying to production."
                )
            warnings.warn(
                "Using default API key. Set SIGNUM_API_KEY in production.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
