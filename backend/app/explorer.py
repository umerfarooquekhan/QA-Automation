"""One run = one background thread that owns the whole browser lifecycle.

FastAPI endpoints never touch Playwright. They read and change a RunState, which is
protected by a lock, and they set two events: stop, and continue (used from step 3).
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from app import browser
from app.redaction import redact_text

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MAX_EVENTS = 200
MAX_RUN_SECONDS = 15 * 60
FINISHED = {"stopped", "failed", "done"}


class RunState:
    """Everything the API may read about a run. Safe to use from several threads."""

    def __init__(self, url: str) -> None:
        self.id = "run_" + uuid.uuid4().hex[:12]
        self.url = url
        self.stop_event = threading.Event()
        self.continue_event = threading.Event()
        self.screenshot: Path | None = None
        self._lock = threading.RLock()
        self._status = "starting"
        self._error: str | None = None
        self._events: list[dict[str, str]] = []

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._status not in FINISHED

    def add_event(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        with self._lock:
            self._events.append({"time": stamp, "message": redact_text(message)})
            del self._events[:-MAX_EVENTS]

    def set_status(self, status: str, message: str | None = None) -> None:
        with self._lock:
            self._status = status
        self.add_event(message or f"Status: {status}")

    def fail(self, error: str) -> None:
        with self._lock:
            self._error = redact_text(error)
        self.set_status("failed", f"Failed: {redact_text(error)}")

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "url": self.url,
                "status": self._status,
                "error": self._error,
                "has_screenshot": self.screenshot is not None,
                "events": list(self._events),
            }


_runs: dict[str, RunState] = {}
_runs_lock = threading.Lock()


def start_run(url: str) -> RunState:
    """Start a run in its own thread. Only one run may be active at a time."""
    with _runs_lock:
        if any(run.is_active for run in _runs.values()):
            raise RuntimeError("A run is already active. Stop it first.")
        state = RunState(url)
        _runs[state.id] = state
    threading.Thread(target=_run, args=(state,), name=state.id, daemon=True).start()
    return state


def get_run(run_id: str) -> RunState | None:
    with _runs_lock:
        return _runs.get(run_id)


def _run(state: RunState) -> None:
    """The run thread. Every Playwright object is created, used and closed here."""
    host = urlsplit(state.url).hostname
    try:
        shots = DATA_DIR / "runs" / state.id
        shots.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            chromium, context, page = browser.launch(playwright)
            try:
                state.add_event(f"Browser opened. Going to {host}")
                browser.go(page, state.url)
                path = shots / "start.png"
                browser.screenshot(page, path)
                state.screenshot = path
                state.set_status("browser_open", f"Page loaded: {page.title()}")

                deadline = time.time() + MAX_RUN_SECONDS
                while not state.stop_event.wait(1.0):
                    if page.is_closed() or not chromium.is_connected():
                        state.add_event("The browser window was closed")
                        break
                    if time.time() > deadline:
                        state.add_event("Time limit reached")
                        break
            finally:
                for closer in (context.close, chromium.close):
                    try:
                        closer()
                    except Exception:  # already closed by the user
                        pass
        state.set_status("stopped", "Run stopped. Browser closed.")
    except Exception as exc:
        log.warning("Run %s failed: %s", state.id, type(exc).__name__)
        state.fail(f"{type(exc).__name__}: {str(exc)[:300]}")