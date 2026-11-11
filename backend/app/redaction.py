"""Secret masking and safe logging.

Goal: passwords, OTPs, API keys and tokens must never reach logs or LLM prompts.

Two complementary mechanisms:

1. Exact masking of *registered* secrets. When the program receives a real secret (a
   password, an API key) it registers the value here. Any later occurrence of that exact
   value is masked, however it got there.
2. Pattern masking for common secret shapes: ``password=...``, authorization and cookie
   headers, bearer tokens, JWTs, API keys, URL credentials and sensitive query parameters.

Pattern masking is a safety net, not a guarantee. It cannot recognise a secret it has never
seen, so real secrets must also be registered.
"""

import logging
import re
import threading
from collections.abc import Mapping
from typing import Any, TextIO

REDACTED = "[REDACTED]"
MIN_SECRET_LENGTH = 4

_registry_lock = threading.Lock()
_registered_secrets: set[str] = set()


def register_secret(value: str) -> None:
    """Remember an exact secret value so it is masked everywhere from now on."""
    if len(value) < MIN_SECRET_LENGTH:
        # Masking very short strings would damage ordinary text, so refuse loudly
        # instead of silently failing to protect the value.
        raise ValueError(f"secret must be at least {MIN_SECRET_LENGTH} characters to mask safely")
    with _registry_lock:
        _registered_secrets.add(value)


def unregister_secret(value: str) -> None:
    with _registry_lock:
        _registered_secrets.discard(value)


def clear_registered_secrets() -> None:
    with _registry_lock:
        _registered_secrets.clear()


# Names that indicate a sensitive value. The match must be a whole word, so
# "token" matches but "tokens_in", "max_tokens" and "token_count" do not.
_KEY_NAMES = (
    r"password|passwd|pwd|secret|token|api[_-]?key|authorization|cookie|"
    r"credentials?|private[_-]?key|session[_-]?id"
)

# Authorization and cookie headers: mask everything to the end of the line.
_HEADER_RE = re.compile(
    r"(?P<key>(?<![A-Za-z0-9])(?:set-cookie|cookie|authorization)[\"']?\s*[:=]\s*[\"']?)"
    r"(?P<value>[^\r\n]*)",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"\b(?P<key>bearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_KEY_VALUE_RE = re.compile(
    rf"(?P<key>(?<![A-Za-z0-9])(?:{_KEY_NAMES})(?![A-Za-z0-9]))"
    r"(?P<sep>[\"']?\s*[:=]\s*[\"']?)"
    r"(?P<value>[^\s\"',;&]+)",
    re.IGNORECASE,
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}")
_API_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")
_URL_CREDENTIALS_RE = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)(?P<user>[^/\s:@]+):(?P<password>[^/\s@]+)@"
)
_SENSITIVE_KEY_RE = re.compile(rf"(?:^|[_-])(?:{_KEY_NAMES})$", re.IGNORECASE)


def redact_text(text: str) -> str:
    """Return ``text`` with registered secrets and common secret patterns masked."""
    with _registry_lock:
        secrets = sorted(_registered_secrets, key=len, reverse=True)
    for secret in secrets:
        text = text.replace(secret, REDACTED)

    text = _HEADER_RE.sub(lambda m: m.group("key") + REDACTED, text)
    text = _BEARER_RE.sub(lambda m: m.group("key") + REDACTED, text)
    text = _KEY_VALUE_RE.sub(lambda m: m.group("key") + m.group("sep") + REDACTED, text)
    text = _JWT_RE.sub(REDACTED, text)
    text = _API_KEY_RE.sub(REDACTED, text)
    return _URL_CREDENTIALS_RE.sub(
        lambda m: f"{m.group('scheme')}{m.group('user')}:{REDACTED}@", text
    )


def is_sensitive_key(key: str) -> bool:
    """True if a dictionary key name suggests its value is a secret."""
    return _SENSITIVE_KEY_RE.search(key) is not None


def redact_data(data: Any) -> Any:
    """Return a copy of ``data`` with secrets masked.

    Handles dicts, lists, tuples and strings. Values under sensitive keys are always
    masked. Other value types are returned unchanged. The input is never modified.
    """
    if isinstance(data, Mapping):
        return {
            key: REDACTED if isinstance(key, str) and is_sensitive_key(key) else redact_data(value)
            for key, value in data.items()
        }
    if isinstance(data, str):
        return redact_text(data)
    if isinstance(data, list):
        return [redact_data(item) for item in data]
    if isinstance(data, tuple):
        return tuple(redact_data(item) for item in data)
    return data


# ---------------------------------------------------------------------------
# Safe logging: every log line passes through redact_text.
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class RedactingFilter(logging.Filter):
    """Masks secrets in the message of every record before it is formatted."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


class RedactingFormatter(logging.Formatter):
    """Masks secrets in the final text, including exception tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))


class AgentStreamHandler(logging.StreamHandler):
    """Marker subclass so configure_logging can find and replace its own handler."""


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> logging.Handler:
    """Send all logs through one redacting handler. Safe to call more than once."""
    root = logging.getLogger()
    for existing in list(root.handlers):
        if isinstance(existing, AgentStreamHandler):
            root.removeHandler(existing)

    handler = AgentStreamHandler(stream)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(RedactingFormatter(LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(level.upper())
    return handler