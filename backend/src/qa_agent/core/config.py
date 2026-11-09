"""Application settings.

Values come from environment variables prefixed with ``QA_`` (for example
``QA_LOG_LEVEL``) or from a local ``.env`` file. The ``.env`` file is never committed.

Secrets such as passwords do NOT belong in settings. They go through the
SecretStore, which is added in a later step.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Typed, validated settings. Invalid values stop the application at startup."""

    model_config = SettingsConfigDict(
        env_prefix="QA_",
        # Works whether the program is started from the project root or from backend/.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnv = "development"
    log_level: LogLevel = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        # Accept "debug", "Debug" and "DEBUG".
        return value.upper() if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    """Return the settings, loading them only once per process."""
    return Settings()
