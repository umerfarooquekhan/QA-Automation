"""The FastAPI application."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import __version__, browser, explorer
from app.config import get_settings
from app.redaction import configure_logging, register_secret


class StartRunRequest(BaseModel):
    url: str
    confirm_test_environment: bool


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

    @api.post("/runs", status_code=201)
    def start_run(request: StartRunRequest) -> dict:
        """Open a visible browser on the URL."""
        if not request.confirm_test_environment:
            raise HTTPException(400, "Confirm that this is a test environment you may test.")
        try:
            url = browser.validate_url(request.url)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        try:
            state = explorer.start_run(url)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return state.snapshot()

    def _find(run_id: str) -> explorer.RunState:
        state = explorer.get_run(run_id)
        if state is None:
            raise HTTPException(404, "Unknown run")
        return state

    @api.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        return _find(run_id).snapshot()

    @api.post("/runs/{run_id}/stop")
    def stop_run(run_id: str) -> dict:
        state = _find(run_id)
        state.stop_event.set()
        return state.snapshot()

    @api.get("/runs/{run_id}/screenshot")
    def get_screenshot(run_id: str) -> FileResponse:
        state = _find(run_id)
        if state.screenshot is None or not state.screenshot.exists():
            raise HTTPException(404, "No screenshot yet")
        return FileResponse(state.screenshot, media_type="image/png")

    return api


app = create_app()