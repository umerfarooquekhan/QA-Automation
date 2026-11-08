"""Smoke test: proves the package is installed and the test tooling works."""

import qa_agent


def test_package_has_version() -> None:
    assert qa_agent.__version__ == "0.1.0"
