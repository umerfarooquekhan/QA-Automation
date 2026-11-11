"""The FastAPI application."""

from fastapi import FastAPI

from app import __version__
from app.config import get_settings
from app.redaction import configure_logging, register_secret


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.deepseek_api_key is not None:
        register_secret(settings.deepseek_api_key.get_secret_value())

    api = FastAPI(title="QA Agent", version=__version__)

    @api.get("/health")
    def health() -> dict[str, str]:
        """Tells you the application is running."""
        return {"status": "ok", "version": __version__, "env": settings.app_env}

    return api


app = create_app()