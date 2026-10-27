from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.tasks import extract_task, extract_batch_task

# sample result returned by our mocked extractor 
# using fixed data makes our tests predictable
SAMPLE_RESULT = {
    "url": "https://books.toscrape.com/",
    "title": "Books to Scrape",
    "description": None,
    "extracted": {"heading": "Books"}
}

@patch("app.tasks.extract_page", new_callable=AsyncMock)
def test_single_task_success(mock_extract):
    # simulate a successful asynchronous scrape
    mock_extract.return_value = SAMPLE_RESULT
    
    # calling the task directly runs its synchronously
    # it does not publish a message to redis
    result = extract_task(
        "https://books.toscrape.com/",
        {"heading": "h1"}
    )
    
    assert result == SAMPLE_RESULT
    
@patch("app.tasks.extract_page", new_callable=AsyncMock)
def test_single_task_rejects_unapproved_url(mock_extract):
    # an unapproved URL should fail before scraping starts
    with pytest.raises(ValueError):
        extract_task(
            "https://example.com/",
            {"heading": "h1"}
        )
    
    # the extractor should never be called
    mock_extract.assert_not_awaited()
    
@patch("app.tasks.extract_page", new_callable=AsyncMock)
def test_single_task_http_failure(mock_extract):
    # simulate an unsuccessful HTTP request
    request = httpx.Request(
        "GET",
        "https://books.toscrape.com/"
    )
    
    response = httpx.Response(
        500,
        request=request
    )
    
    mock_extract.side_effect = httpx.HTTPStatusError(
        "Server error",
        request=request,
        response=response
    )
    
    # the single task currently propagates HTTP errors
    with pytest.raises(httpx.HTTPStatusError):
        extract_task(
            "https://books.toscrape.com/",
            {}
        )

@patch("app.tasks.extract_page", new_callable=AsyncMock)
def test_batch_task_success(mock_extract):
    # simulate successful scraping for both URLs
    mock_extract.return_value = SAMPLE_RESULT
    
    result = extract_batch_task(
        [
            "https://books.toscrape.com/",
            "https://books.toscrape.com/catalogue/page-2.html"
        ],
        {"heading": "h1"}
    )
    
    assert result["total_urls"] == 2
    assert result["completed"] == 2
    assert result["failed"] == 0
    assert len(result["results"]) == 2
    
    # both URLs should have been passed to the extractor
    assert mock_extract.await_count == 2

@patch("app.tasks.extract_page", new_callable=AsyncMock)
def test_batch_task_partial_failure(mock_extract):
    # simulate one successful scrape and one HTTP failure
    async def fake_extract(url, selectors):
        if "page-2" in url:
            raise httpx.ConnectError("Connection failed")
        
        return SAMPLE_RESULT
    
    mock_extract.side_effect = fake_extract
    
    result = extract_batch_task(
            [
                "https://books.toscrape.com/",
                "https://books.toscrape.com/catalogue/page-2.html"
            ],
            {"heading": "h1"}
    )
    
    assert result["total_urls"] == 2
    assert result["completed"] == 1
    assert result["failed"] == 1
    
    # confirm that the unsuccessful URL was recorded
    failed_result = next(
        item for item in result["results"]
        if item["status"] == "failed"
    )
    
    assert failed_result["error"] == "ConnectError"
    
    