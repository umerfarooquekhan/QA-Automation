import pytest

from qa_agent.core.redaction import (
    REDACTED,
    is_sensitive_key,
    redact_data,
    redact_text,
    register_secret,
    unregister_secret,
)


def test_key_value_password_is_masked() -> None:
    result = redact_text("login failed for user=admin password=hunter2 retrying")
    assert "hunter2" not in result
    assert "user=admin" in result


def test_json_password_is_masked() -> None:
    result = redact_text('{"username": "admin", "password": "hunter2"}')
    assert "hunter2" not in result
    assert '"username": "admin"' in result


def test_authorization_header_is_masked() -> None:
    result = redact_text("Authorization: Bearer abc123def456ghi789")
    assert "abc123def456ghi789" not in result
    assert result == f"Authorization: {REDACTED}"


def test_standalone_bearer_token_is_masked() -> None:
    result = redact_text("request used Bearer abc123def456ghi789 and failed")
    assert "abc123def456ghi789" not in result
    assert "and failed" in result


def test_jwt_is_masked() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghij"
    result = redact_text(f"response included {jwt} in body")
    assert jwt not in result
    assert REDACTED in result


def test_api_key_is_masked() -> None:
    key = "sk-abcdefghijklmnop1234"
    assert key not in redact_text(f"llm call with {key}")


def test_url_credentials_are_masked() -> None:
    result = redact_text("connect https://user:pa55word@example.com/path now")
    assert "pa55word" not in result
    assert "example.com/path" in result


def test_sensitive_query_parameter_is_masked() -> None:
    result = redact_text("GET https://x.test/cb?token=abc123&page=2")
    assert "abc123" not in result
    assert "page=2" in result


def test_prefixed_token_name_is_masked() -> None:
    assert "abc123" not in redact_text("form csrf_token=abc123 submitted")


def test_counters_and_normal_text_are_not_touched() -> None:
    text = "tokens_in=120 max_tokens=500 token_count=7 cost=0.01"
    assert redact_text(text) == text


def test_cookie_header_is_masked_to_end_of_line() -> None:
    assert "abc123" not in redact_text("Cookie: sid=abc123; theme=dark")


def test_registered_secret_is_masked_anywhere() -> None:
    register_secret("Canary-Pass-42")
    result = redact_text("typed Canary-Pass-42 into the form")
    assert result == f"typed {REDACTED} into the form"


def test_unregistered_secret_is_no_longer_masked() -> None:
    register_secret("Canary-Pass-42")
    unregister_secret("Canary-Pass-42")
    assert redact_text("Canary-Pass-42") == "Canary-Pass-42"


def test_too_short_secret_is_refused() -> None:
    with pytest.raises(ValueError):
        register_secret("abc")


def test_is_sensitive_key_matches_names_but_not_counters() -> None:
    for key in (
        "password",
        "Authorization",
        "x-api-key",
        "client_secret",
        "access_token",
        "set-cookie",
    ):
        assert is_sensitive_key(key)
    for key in ("username", "tokens_in", "max_tokens", "state", "passwords_count"):
        assert not is_sensitive_key(key)


def test_redact_data_masks_nested_structures_without_changing_the_input() -> None:
    data = {
        "username": "admin",
        "password": "x1",
        "nested": {"api_key": "k-1", "ok": 5},
        "items": [{"token": "t-1"}, "password=abc12345"],
        "tokens_in": 120,
    }
    result = redact_data(data)
    assert result["username"] == "admin"
    assert result["password"] == REDACTED
    assert result["nested"] == {"api_key": REDACTED, "ok": 5}
    assert result["items"][0] == {"token": REDACTED}
    assert "abc12345" not in result["items"][1]
    assert result["tokens_in"] == 120
    assert data["password"] == "x1"
