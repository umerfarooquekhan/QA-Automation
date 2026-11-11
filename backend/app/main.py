"""The FastAPI application."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, SecretStr

from app import __version__, browser, explorer
from app.config import get_settings
from app.redaction import MIN_SECRET_LENGTH, configure_logging, register_secret


class StartRunRequest(BaseModel):
    url: str
    username: str | None = None
    password: SecretStr | None = None
    confirm_test_environment: bool


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.deepseek_api_key is not None:
        register_secret(settings.deepseek_api_key.get_secret_value())

    api = FastAPI(title="QA Agent", version=__version__)

    @api.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # The default 422 answer repeats the submitted values (passwords included). Ours does not.
        errors = [
            {"field": ".".join(str(p) for p in e.get("loc", ())), "message": e.get("msg", "invalid")}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @api.get("/health")
    def health() -> dict[str, str]:
        """Tells you the application is running."""
        return {"status": "ok", "version": __version__, "env": settings.app_env}

    @api.post("/runs", status_code=201)
    def start_run(request: StartRunRequest) -> dict:
        """Open a visible browser on the URL and, if credentials are given, log in."""
        if not request.confirm_test_environment:
            raise HTTPException(400, "Confirm that this is a test environment you may test.")
        try:
            url = browser.validate_url(request.url)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        credentials = None
        if request.username or request.password:
            password = request.password.get_secret_value() if request.password else ""
            if not request.username or not password:
                raise HTTPException(400, "Provide both username and password, or neither.")
            if len(password) < MIN_SECRET_LENGTH:
                raise HTTPException(
                    400, f"The password needs at least {MIN_SECRET_LENGTH} characters."
                )
            # Register before anything can log them, so they are masked everywhere.
            register_secret(password)
            if len(request.username) >= MIN_SECRET_LENGTH:
                register_secret(request.username)
            credentials = (request.username, password)

        try:
            state = explorer.start_run(url, credentials)
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