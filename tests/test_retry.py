import asyncio
import httpx
import pytest
from app import retry

def test_retry_after_timeout(monkeypatch):
    # keep track of how many times the scraper runs
    attempts = 0
    delays = []
    
    async def fake_extract(url, selectors):
        nonlocal attempts
        attempts += 1
        
        # simulate 2 network timeouts
        if attempts < 3:
            raise httpx.ReadTimeout("Simulated timeout")
        
        # simulate a successful 3rd attempt
        return {"title": "Test Book"}
    
    async def fake_sleep(seconds):
        # record delays without actually waiting
        delays.append(seconds)
    
    # replace real HTTP requests with our fake scraper
    # this is similar to mocking functions with Jest
    monkeypatch.setattr(retry, "extract_page", fake_extract)
    
    # replace asyncio.sleep to keep the test fast
    monkeypatch.setattr(retry.asyncio, "sleep", fake_sleep)
    
    # execute our async function in a test
    result = asyncio.run(
        retry.extract_with_retry(
            "https://books.toscrape.com/",
            {}
        )
    )
    
    # confirm the retry logic worked as intended
    assert attempts == 3
    assert delays == [1, 2]
    assert result == {"title": "Test Book"}

def test_success_without_retry(monkeypatch):
    attempts = 0
    
    async def fake_extract(url, selectors):
        nonlocal attempts
        attempts += 1
        
        # simulate a successful first attempt
        return {"title": "Test Book"}
    
    monkeypatch.setattr(retry, "extract_page", fake_extract)
    
    result = asyncio.run(
        retry.extract_with_retry(
            "https://books.toscrape.com/",
            {}
        )
    )
    
    # no retries should be necessary
    assert attempts == 1
    assert result == {"title": "Test Book"}
    
def test_all_retries_exhausted(monkeypatch):
    attempts = 0
    delays = []
    
    async def fake_extract(url, selectors):
        nonlocal attempts
        attempts += 1
        
        # every attempt fails
        raise httpx.ReadTimeout("Simulated timeout")
    
    async def fake_sleep(seconds):
        # record requested delays without waiting
        delays.append(seconds)
        
    monkeypatch.setattr(retry, "extract_page", fake_extract)
    monkeypatch.setattr(retry.asyncio, "sleep", fake_sleep)
    
    # after three failed attempts, the error must propagate
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(
            retry.extract_with_retry(
                "https://books.toscrape.com/",
                {}
            )
        )
    
    assert attempts == 3
    assert delays == [1, 2]
    
def test_non_retryable_http_error(monkeypatch):
    attempts = 0
    
    async def fake_extract(url, selectors):
        nonlocal attempts
        attempts += 1
        
        # construct a simulate HTTP 404 response
        request = httpx.Request("GET", url)
        response = httpx.Response(404, request=request)
        
        # HTTPStatusError isn't in RETRYABLE_ERRORS
        raise httpx.HTTPStatusError(
            "Not Found",
            request=request,
            response=response
        )
    
    monkeypatch.setattr(retry, "extract_page", fake_extract)
    
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            retry.extract_with_retry(
                "https://books.toscrape.com/",
                {}
            )
        )
    
    # non-retryable errors should fail immediately
    assert attempts == 1
    