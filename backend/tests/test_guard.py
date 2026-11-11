import pytest

from app.browser import RequestGuard

SITE = "app.example.com"
USER = "alice@example.com"
PASSWORD = "S3cret!pass"


def guard(login: bool = False) -> RequestGuard:
    g = RequestGuard(SITE)
    if login:
        g.open_login_window([USER, PASSWORD])
    return g


def action(g: RequestGuard, method: str, url: str, body: str | None = None) -> str:
    return g.decide(method, url, body)[0]


def test_plain_reads_are_allowed() -> None:
    assert action(guard(), "GET", "https://app.example.com/employees") == "allow"


def test_scripts_from_other_sites_are_allowed() -> None:
    assert action(guard(), "GET", "https://cdn.other.com/app.js") == "allow"


@pytest.mark.parametrize(
    "url",
    [
        "https://app.example.com/logout",
        "https://app.example.com/api/deleteUser?id=3",
        "https://app.example.com/account/sign-out",
    ],
)
def test_destructive_get_addresses_are_blocked(url: str) -> None:
    assert action(guard(), "GET", url) == "block"


def test_post_is_blocked_outside_the_login_window() -> None:
    assert action(guard(), "POST", "https://app.example.com/api/employees", '{"n":"x"}') == "block"


def test_login_post_with_typed_credentials_is_allowed_form_encoded() -> None:
    body = "username=alice%40example.com&password=S3cret%21pass"
    assert action(guard(True), "POST", "https://app.example.com/login", body) == "allow"


def test_login_post_with_typed_credentials_is_allowed_json() -> None:
    body = '{"email": "alice@example.com", "password": "S3cret!pass"}'
    assert action(guard(True), "POST", "https://app.example.com/api/auth", body) == "allow"


def test_login_window_does_not_allow_other_posts() -> None:
    assert action(guard(True), "POST", "https://app.example.com/api/employees", '{"n":"x"}') == "block"


def test_closed_login_window_blocks_a_login_post() -> None:
    g = guard(True)
    g.close_login_window()
    body = f"password={PASSWORD}"
    assert action(g, "POST", "https://app.example.com/login", body) == "block"


def test_credentials_are_never_sent_to_another_site() -> None:
    body = f"password={PASSWORD}"
    assert action(guard(True), "POST", "https://evil.example.net/steal", body) == "block"


def test_graphql_query_is_allowed() -> None:
    body = '{"query": "query { employees { id } }"}'
    assert action(guard(), "POST", "https://app.example.com/graphql", body) == "allow"


def test_graphql_mutation_is_blocked() -> None:
    body = '{"query": "mutation { deleteEmployee(id: 1) { id } }"}'
    assert action(guard(), "POST", "https://app.example.com/graphql", body) == "block"


def test_read_only_search_post_is_allowed() -> None:
    assert action(guard(), "POST", "https://app.example.com/api/employees/search", '{"q":"x"}') == "allow"


def test_telemetry_post_is_dropped_quietly() -> None:
    assert action(guard(), "POST", "https://app.example.com/analytics/collect", "{}") == "drop"


def test_description_has_no_query_string() -> None:
    text = RequestGuard.describe("post", "https://app.example.com/api/x?token=abc123")
    assert text == "POST app.example.com/api/x"