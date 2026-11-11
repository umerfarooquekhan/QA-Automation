"""Logging setup: every log line passes through secret redaction."""

import logging
from typing import TextIO

from qa_agent.core.redaction import redact_text

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