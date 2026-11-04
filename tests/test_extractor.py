import pytest
import httpx
import respx

from app.extractor import extract_page
from soupsieve.util import SelectorSyntaxError

@pytest.fixture(autouse=True)
def mock_destination_validation(monkeypatch):
    """
    Mock destination validation for all extractor tests.
    These test focus on HTTP responses and HTML parsing,
    not security validation, which is tested separately.
    """
    
    # approve example.com only within this test module
    monkeypatch.setattr(
        "app.url_validator.ALLOWED_HOSTS",
        {"example.com"},
    )
    
    # simulate successful DNS validation
    # this avoids making real DNS requests during testing
    monkeypatch.setattr(
        "app.extractor.resolves_to_public_ips",
        lambda hostname: True,
    )

# this HTML represents a small webpage
# using fixed HTML makes our tests predictable
SAMPLE_HTML = """
<html>
    <head>
        <title>Python Testing Guide</title>
        <meta name="description"
              content="Learn how to test Python applications">
    </head>
    <body>
        <h1>Welcome to Python Testing</h1>
        <p class="author">Ashley</p>
    </body>
</html>
"""
@pytest.mark.asyncio
@respx.mock
async def test_extract_page_success():
    # intercept the HTTPx request and return our sample HTML
    # no real network request will occur
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            status_code=200,
            text=SAMPLE_HTML
        )
    )
    
    # call the same function our application uses
    result = await extract_page(
        url="https://example.com/",
        selectors={
            "heading": "h1",
            "author": ".author" 
        }
    )
    
    # check the extracted metadata
    assert result["title"] == "Python Testing Guide"
    assert result["description"] == (
        "Learn how to test Python applications"
    )
    
    # verify that CSS selectors extracted the correct text
    assert result["extracted"]["heading"] == (
        "Welcome to Python Testing"
    )
    assert result["extracted"]["author"] == "Ashley"
    
    # ensure the original URL is preserved
    assert result["url"] == "https://example.com/"
    
@pytest.mark.asyncio
@respx.mock
async def test_extract_page_missing_elements():
    # simulate a webpage containing no requested elements
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text="<html><body><p>Hello</p></body></html>"
        )
    )
    
    result = await extract_page(
        url="https://example.com/",
        selectors={"missing": ".does-not-exist"}
    )
    
    # our scraper should return None for missing elements
    assert result["title"] is None
    assert result["description"] is None
    assert result["extracted"]["missing"] is None
    
@pytest.mark.asyncio
@respx.mock
async def test_extract_page_http_error():
    # simulate a website returning HTTP 500
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(status_code=500)
    )
    
    # httpx should raise an exception because
    # extract_page() calls response.raise_for_status()
    with pytest.raises(httpx.HTTPStatusError):
        await extract_page(
            url="https://example.com/",
            selectors={"heading": "h1"}
        )

@pytest.mark.asyncio
@respx.mock
async def test_invalid_css_selector():
    # simulate a successful HTTP response
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text="<html><body><h1>Test</h1></body></html>"
        )
    )
    
    # an unclosed attribute selector is invalid CSS
    # beautiful soup should raise a selector syntax error
    with pytest.raises(SelectorSyntaxError):
        await extract_page(
            url="https://example.com/",
            selectors={"title": "h1["}
        )
        
@pytest.mark.asyncio
@respx.mock
async def test_redirect_is_not_followed():
    # simulate an HTTP redirect to another website
    # redirects are disabled in our extractor
    route = respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            302,
            headers={"Location": "https://other-site.com/"}
        )
    )
    
    # our current extractor raises HTTPStatusError
    # for a redirect because it calls raise_for_status()
    with pytest.raises(httpx.HTTPStatusError):
        await extract_page(
            url="https://example.com/",
            selectors={"heading": "h1"}
        )
    
    # confirm that the original request was made once
    assert route.call_count == 1
    
@pytest.mark.asyncio
@respx.mock
async def test_network_connection_failure():
    # simulate a network connection failure
    # no real network request occurs
    respx.get("https://example.com/").mock(
        side_effect=httpx.ConnectError("Connection failed")
    )
    
    # httpx should propagate the connection exception
    with pytest.raises(httpx.ConnectError):
        await extract_page(
            url="https://example.com/",
            selectors={"heading": "h1"}
        )
        
@pytest.mark.asyncio
@respx.mock
async def test_rejects_unsafe_dns_destination(monkeypatch):
    """
    Verify that the extractor refuses unsafe DNS results
    before sending an HTTP request
    """
    
    # override our test fixture's successful DNS response
    # simulate a hostname resolving to an unsafe address
    monkeypatch.setattr(
        "app.extractor.resolves_to_public_ips",
        lambda hostname: False,
    )
    
    # register a mock HTTP endpoint
    # it should never receive a request
    route = respx.get("https://example.com/").mock(
        return_value=httpx.Response(200, text="<h1>Test</h1>")
    )
    
    # the extractor should reject the destination
    with pytest.raises(
        ValueError,
        match="Scraping destination failed DNS validation"
    ):
        await extract_page(
            url="https://example.com/",
            selectors={"heading": "h1"}
        )
    
    # confirm no network request was attempted
    assert route.call_count == 0
    
     