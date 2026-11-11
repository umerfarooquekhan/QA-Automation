"""The FastAPI application."""

from fastapi import FastAPI

from qa_agent import __version__
from qa_agent.core.config import get_settings
from qa_agent.core.logging_setup import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="QA Agent", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Tells you the application is running."""
        return {"status": "ok", "version": __version__, "env": settings.app_env}

    return app


app = create_app()