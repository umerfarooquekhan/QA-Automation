import pytest
from pydantic import ValidationError

from qa_agent.core.config import Settings, get_settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QA_APP_ENV", raising=False)
    monkeypatch.delenv("QA_LOG_LEVEL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"


def test_environment_overrides_and_normalizes_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_APP_ENV", "test")
    monkeypatch.setenv("QA_LOG_LEVEL", "debug")
    settings = Settings(_env_file=None)
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"


def test_invalid_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_returns_cached_instance() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()
