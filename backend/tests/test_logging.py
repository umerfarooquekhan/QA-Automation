import io
import logging
from collections.abc import Iterator

import pytest
from app.redaction import AgentStreamHandler, configure_logging

from app.redaction import register_secret

logger = logging.getLogger("qa_agent.test_logging")


@pytest.fixture
def log_stream() -> Iterator[io.StringIO]:
    root = logging.getLogger()
    previous_level = root.level
    stream = io.StringIO()
    configure_logging("INFO", stream)
    yield stream
    for handler in list(root.handlers):
        if isinstance(handler, AgentStreamHandler):
            root.removeHandler(handler)
    root.setLevel(previous_level)


def test_registered_secret_never_appears_in_logs(log_stream: io.StringIO) -> None:
    register_secret("Canary-Pass-42")
    logger.info("user typed %s into the form", "Canary-Pass-42")
    output = log_stream.getvalue()
    assert "Canary-Pass-42" not in output
    assert "user typed" in output


def test_pattern_secret_in_arguments_is_masked(log_stream: io.StringIO) -> None:
    logger.info("calling login with password=%s", "hunter2")
    assert "hunter2" not in log_stream.getvalue()


def test_secret_inside_exception_traceback_is_masked(log_stream: io.StringIO) -> None:
    try:
        raise ValueError("bad token=abc123xyz")
    except ValueError:
        logger.exception("operation failed")
    output = log_stream.getvalue()
    assert "abc123xyz" not in output
    assert "operation failed" in output


def test_configure_logging_replaces_its_own_handler(log_stream: io.StringIO) -> None:
    configure_logging("INFO", io.StringIO())
    handlers = [h for h in logging.getLogger().handlers if isinstance(h, AgentStreamHandler)]
    assert len(handlers) == 1


def test_level_is_respected_and_normal_messages_are_unchanged(log_stream: io.StringIO) -> None:
    logger.debug("hidden detail")
    logger.info("visible detail count=3")
    output = log_stream.getvalue()
    assert "hidden detail" not in output
    assert "visible detail count=3" in output
