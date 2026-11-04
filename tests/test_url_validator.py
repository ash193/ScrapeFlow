import pytest
from app.url_validator import is_allowed_url

@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://books.toscrape.com/", True),
        ("https://example.com/", False),
        ("http://books.toscrape.com/", False),
        ("https://127.0.0.1/", False),
        ("https://[::1]/", False),
        ("https://books.toscrape.com:8443/", False),
        ("https://user:pass@books.toscrape.com/", False),
        ("not-a-url", False),
        ("https://books.toscrape.com./", True),
    ],
)
def test_url_validation(url, expected):
    # check the result for each approved or rejected URL
    assert is_allowed_url(url) is expected