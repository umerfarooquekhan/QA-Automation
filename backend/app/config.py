"""Settings, read from environment variables prefixed with QA_ or from the project's .env file.

Secrets are held as SecretStr so they are not printed by accident. Website passwords are
NOT settings: they are typed into the New Run form and kept in memory for one run only.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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

    # MongoDB (used from the step that saves runs and test cases).
    mongodb_uri: SecretStr = SecretStr("mongodb://127.0.0.1:27017")
    mongodb_db: str = Field(default="qa_agent", pattern=r"^[A-Za-z0-9_-]{1,40}$")

    # DeepSeek (used from the step that generates test cases).
    deepseek_api_key: SecretStr | None = None

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        # Accept "debug", "Debug" and "DEBUG".
        return value.upper() if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    """Return the settings, loading them only once per process."""
    return Settings()