import asyncio
from app.celery_app import celery_app
from app.extractor import extract_page
import httpx
from soupsieve.util import SelectorSyntaxError
from app.url_validator import is_allowed_url

@celery_app.task(name="scraperflow.extract")
def extract_task(url: str, selectors: dict[str,str]):
    # revalidate the URL inside the Celery worker
    # tasks can be submitted independently of FastAPI
    if not is_allowed_url(url):
        raise ValueError("Url is not an approved scraping target")
    
    # celery tasks are synchronous, but our extractor is async
    # asyncio.run() creates an event loop to execute it
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
            # revalidate each URL before making a network request
            if not is_allowed_url(url):
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
                    SelectorSyntaxError,
                    ValueError
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
    