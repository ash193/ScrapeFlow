import asyncio
from app.celery_app import celery_app
from app.extractor import extract_page
import httpx
from soupsieve.util import SelectorSyntaxError

ALLOWED_HOSTS = {"books.toscrape.com"}

@celery_app.task(name="scraperflow.extract")
def extract_task(url: str, selectors: dict[str,str]):
    # celery's standard task function is synchronous
    # asyncio.run() executes our existing async extractor
    # using an event loop inside the worker process
    
    from urllib.parse import urlsplit
    
    parsed = urlsplit(url)
    
    # restrict both the protocol and destination hostname
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Url is not an approved scraping target")
    
    # run the async scraper and return its result
    # celery stores the returned dictionary in its result backend
    return asyncio.run(
        extract_page(url, selectors)
    )

@celery_app.task(name="scraperflow.extract_batch")
def extract_batch_task(
    urls: list[str],
    selectors: dict[str, str]
):
    # celery tasks are synchronous by default
    # we'll use asyncio.run() to execute concurrent
    # http requests inside this background worker
    
    async def process_batch():
        # limit simultaneous scraping operations
        semaphore = asyncio.Semaphore(5)
        
        async def process_url(url: str):
            from urllib.parse import urlsplit
            
            # validate the dest inside the worker too
            parsed = urlsplit(url)
            
            if (
                parsed.scheme != "https"
                or parsed.hostname not in ALLOWED_HOSTS
            ):
                return {
                    "url": url,
                    "status": "failed",
                    "error": "URL is not approved"
                }
            
            async with semaphore:
                try:
                    # call our existing async extractor
                    data = await extract_page(url, selectors)
                    
                    return {
                        "url": url,
                        "status": "completed",
                        "data": data
                    }
                except (
                    httpx.RequestError,
                    httpx.HTTPStatusError,
                    SelectorSyntaxError
                ) as error:
                    return {
                        "url": url,
                        "status": "failed",
                        "error": type(error).__name__
                    }
    
        tasks = [process_url(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        completed = sum(
            result["status"] == "completed"
            for result in results
        )
        
        return {
            "total_urls": len(urls),
            "completed": completed,
            "failed": len(urls) - completed,
            "results": results
        }
    
    return asyncio.run(process_batch())
    