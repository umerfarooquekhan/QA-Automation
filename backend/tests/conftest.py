from collections.abc import Iterator

import pytest

from app.redaction import clear_registered_secrets


@pytest.fixture(autouse=True)
def _clean_secret_registry() -> Iterator[None]:
    """Every test starts and ends with no registered secrets."""
    clear_registered_secrets()
    yield
    clear_registered_secrets()
