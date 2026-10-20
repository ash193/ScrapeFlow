import asyncio
import httpx
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