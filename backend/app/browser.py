"""Playwright: everything that touches the browser lives here.

Playwright's sync API is bound to the thread that started it. All browser calls therefore
happen inside the run's own thread (see explorer.py). No other code may touch these objects.
"""

from pathlib import Path
from urllib.parse import urlsplit


def validate_url(raw: str) -> str:
    """Return a clean http(s) URL, or raise ValueError with a message for the user."""
    url = raw.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError("The URL must start with http:// or https://")
    if not parts.hostname:
        raise ValueError("The URL has no host name")
    if parts.username or parts.password:
        raise ValueError("Do not put a username or password in the URL")
    return url


def launch(playwright):
    """Open a visible Chromium window. Returns (browser, context, page)."""
    browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])
    context = browser.new_context(viewport=None)
    page = context.new_page()
    return browser, context, page


def go(page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)


def screenshot(page, path: Path) -> None:
    page.screenshot(path=str(path))