import pytest
from fastapi.testclient import TestClient

from app.browser import validate_url
from app.explorer import RunState
from app.main import app
from app.redaction import register_secret


def test_validate_url_accepts_http_and_https() -> None:
    assert validate_url(" https://example.com/login ") == "https://example.com/login"
    assert validate_url("http://localhost:3000") == "http://localhost:3000"


@pytest.mark.parametrize(
    "bad", ["example.com", "ftp://example.com", "https://", "https://user:pw@example.com"]
)
def test_validate_url_rejects_bad_urls(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_url(bad)


def test_run_events_never_contain_registered_secrets() -> None:
    register_secret("Canary-Pass-42")
    state = RunState("https://example.com")
    state.add_event("typed Canary-Pass-42 somewhere")
    assert "Canary-Pass-42" not in str(state.snapshot())


def test_start_run_requires_confirmation() -> None:
    response = TestClient(app).post(
        "/runs", json={"url": "https://example.com", "confirm_test_environment": False}
    )
    assert response.status_code == 400