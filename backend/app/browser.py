"""Playwright: everything that touches the browser lives here.

Playwright's sync API is bound to the thread that started it. All browser calls therefore
happen inside the run's own thread (see explorer.py). No other code may touch these objects.
"""

import json
import re
from pathlib import Path
from urllib.parse import unquote_plus, urlsplit

from playwright.sync_api import Error as PlaywrightError

READ_METHODS = {"GET", "HEAD", "OPTIONS"}
DESTRUCTIVE_WORDS = {
    "logout", "signout", "delete", "remove", "unsubscribe",
    "destroy", "deactivate", "terminate", "revoke",
}
DESTRUCTIVE_PAIRS = {("log", "out"), ("sign", "out"), ("close", "account")}
READ_WORDS = {"search", "query", "filter", "list", "autocomplete", "suggest", "lookup", "find"}
KEEPALIVE_WORDS = {"refresh", "keepalive", "heartbeat", "ping"}
TELEMETRY_WORDS = {"analytics", "track", "tracking", "collect", "beacon", "telemetry", "metrics", "pixel"}


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


# ---------------------------------------------------------------------------
# Request guard: decides what the browser may send. Pure logic, no browser needed.
# ---------------------------------------------------------------------------


def _tokens(path: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", path)  # deleteUser -> delete User
    return [t for t in re.split(r"[^a-z0-9]+", spaced.lower()) if t]


def _is_destructive(tokens: list[str]) -> bool:
    if any(t in DESTRUCTIVE_WORDS for t in tokens):
        return True
    return any(pair in DESTRUCTIVE_PAIRS for pair in zip(tokens, tokens[1:]))


def _json_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)


def _is_graphql_query(body: str | None) -> bool:
    """True only if every operation in the body is clearly a read-only query."""
    if not body:
        return False
    try:
        data = json.loads(body)
    except ValueError:
        return False
    items = data if isinstance(data, list) else [data]
    if not items:
        return False
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("query"), str):
            return False
        query = item["query"]
        if not re.match(r"\s*(query\b|\{)", query):
            return False
        if re.search(r"\bmutation\b|\bsubscription\b", query):
            return False
    return True


class RequestGuard:
    """Decides, for every request the browser makes: allow, drop (quietly) or block."""

    def __init__(self, site_host: str) -> None:
        self.site_host = site_host.lower()
        self._base = self.site_host.removeprefix("www.")
        self.login_window = False
        self._login_secrets: list[str] = []
        self.blocked: list[str] = []

    def open_login_window(self, secrets: list[str]) -> None:
        self._login_secrets = [s for s in secrets if s]
        self.login_window = True

    def close_login_window(self) -> None:
        self.login_window = False
        self._login_secrets = []

    def same_site(self, host: str) -> bool:
        host = host.lower()
        return host == self._base or host == "www." + self._base or host.endswith("." + self._base)

    def _carries_login_secret(self, body: str | None) -> bool:
        if not body:
            return False
        candidates = [body, unquote_plus(body)]
        try:
            candidates.extend(_json_strings(json.loads(body)))
        except ValueError:
            pass
        return any(secret in text for secret in self._login_secrets for text in candidates)

    def decide(self, method: str, url: str, post_data: str | None = None) -> tuple[str, str]:
        method = method.upper()
        parts = urlsplit(url)
        tokens = _tokens(parts.path)
        same_site = self.same_site(parts.hostname or "")
        telemetry = any(t in TELEMETRY_WORDS for t in tokens)

        if method in READ_METHODS:
            if same_site and _is_destructive(tokens):
                return "block", "destructive address"
            return "allow", "read"

        if not same_site:
            return ("drop", "telemetry") if telemetry else ("block", "write to another site")
        if self.login_window and self._carries_login_secret(post_data):
            return "allow", "login request"
        if _is_destructive(tokens):
            return "block", "destructive address"
        if telemetry:
            return "drop", "telemetry"
        if _is_graphql_query(post_data):
            return "allow", "graphql query"
        if tokens and tokens[-1] in READ_WORDS | KEEPALIVE_WORDS:
            return "allow", "read-only request"
        return "block", "write request"

    @staticmethod
    def describe(method: str, url: str) -> str:
        """A short description with no query string (it could contain a token)."""
        parts = urlsplit(url)
        return f"{method.upper()} {parts.hostname or ''}{parts.path}"


def install_guard(context, guard: RequestGuard, on_blocked) -> None:
    """Route every request of the browser context through the guard."""

    def handle(route) -> None:
        request = route.request
        body = None
        if request.method.upper() not in READ_METHODS:
            try:
                body = request.post_data
            except Exception:
                body = None
        action, reason = guard.decide(request.method, request.url, body)
        try:
            if action == "allow":
                route.continue_()
            elif action == "drop":
                route.fulfill(status=204, body="")
            else:
                line = guard.describe(request.method, request.url)
                guard.blocked.append(line)
                on_blocked(f"Blocked {line} ({reason})")
                route.abort("blockedbyclient")
        except PlaywrightError:
            pass  # the page closed while the request was in flight

    context.route("**/*", handle)


# ---------------------------------------------------------------------------
# Browser actions
# ---------------------------------------------------------------------------


def launch(playwright):
    """Open a visible Chromium window. Returns (browser, context, page)."""
    browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])
    context = browser.new_context(viewport=None, service_workers="block", accept_downloads=False)
    page = context.new_page()
    return browser, context, page


def go(page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)


def screenshot(page, path: Path) -> None:
    page.screenshot(path=str(path))


def safe_location(page) -> str:
    """Host and path of the current page, without the query string."""
    parts = urlsplit(page.url)
    return f"{parts.hostname or ''}{parts.path}"


# ---------------------------------------------------------------------------
# Login: one attempt only (retrying could lock the account)
# ---------------------------------------------------------------------------

_TEXT_INPUTS = (
    "input:visible:not([type=password]):not([type=hidden]):not([type=checkbox])"
    ":not([type=radio]):not([type=submit]):not([type=button]):not([type=file])"
    ":not([type=image]):not([type=reset]):not([type=range]):not([type=color])"
)


class LoginProblem(Exception):
    """The login form is missing or unclear. The message is shown to the user."""


def _password_visible(page) -> bool:
    try:
        return page.locator("input[type=password]:visible").count() > 0
    except PlaywrightError:
        return True  # the page is navigating, look again


def _find_login_form(page):
    passwords = page.locator("input[type=password]:visible")
    try:
        passwords.first.wait_for(state="visible", timeout=8_000)
    except PlaywrightError:
        raise LoginProblem("No password field found on this page.") from None
    if passwords.count() != 1:
        raise LoginProblem("The page has more than one password field (maybe a sign-up form).")
    password_field = passwords.first
    form = password_field.locator("xpath=ancestor::form[1]")
    scope = form if form.count() > 0 else page
    users = scope.locator(_TEXT_INPUTS)
    if users.count() != 1:
        raise LoginProblem("Could not tell which field is the username.")
    return users.first, password_field, scope


def _wait_until_password_gone(page) -> bool:
    for _ in range(40):  # up to about 20 seconds
        page.wait_for_timeout(500)
        if not _password_visible(page):
            page.wait_for_timeout(1500)  # let the next page settle
            return True
    return False


def _login_error_text(page) -> str:
    try:
        selector = "[role=alert]:visible, .error:visible, .alert:visible, .flash:visible"
        text = " ".join(page.locator(selector).first.inner_text(timeout=1_000).split())[:150]
        if text:
            return f"Still on the login form. The site says: {text}"
    except PlaywrightError:
        pass
    return (
        "Still on the login form after submitting. The credentials may be wrong, "
        "or an extra step (OTP, CAPTCHA) may be needed."
    )


def try_login(page, guard: RequestGuard, username: str, password: str) -> tuple[bool, str]:
    """Fill the login form and submit it once. Returns (success, message)."""
    try:
        user_field, password_field, scope = _find_login_form(page)
    except LoginProblem as problem:
        return False, str(problem)

    guard.open_login_window([username, password])
    blocked_before = len(guard.blocked)
    try:
        user_field.fill(username)
        password_field.fill(password)
        submit = scope.locator("button[type=submit]:visible, input[type=submit]:visible")
        if submit.count() == 1:
            submit.first.click()
        else:
            password_field.press("Enter")
        success = _wait_until_password_gone(page)
    except PlaywrightError as exc:
        return False, f"The login step failed ({type(exc).__name__})."
    finally:
        guard.close_login_window()

    if success:
        return True, "Login looks successful"
    if len(guard.blocked) > blocked_before:
        return False, (
            "The login request was blocked by the safety rules (it did not carry the typed "
            "credentials). Sign in by hand in the browser window."
        )
    return False, _login_error_text(page)