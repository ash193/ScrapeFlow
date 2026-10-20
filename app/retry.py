import asyncio
import logging
import httpx
from app.extractor import extract_page

# create a logger for recording retry attempts
# similar to using a structured logger in Node.js
logger = logging.getLogger(__name__)

# max number of attempts, including the first request
MAX_ATTEMPTS = 3

# retry only potentially temp network failures
# do not automatically retry invalid CSS selectors
# malformed input, or every possible HTTP error
RETRYABLE_ERRORS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError
)

async def extract_with_retry(
    url: str,
    selectors: dict[str, str]
) -> dict:
    # range(1, 4) produces attempts 1, 2, and 3
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # call our existing async extraction engine
            return await extract_page(url, selectors)
        
        except RETRYABLE_ERRORS as error:
            # on the final attempt, allow the error to
            # propagate so the worker records a failure
            if attempt == MAX_ATTEMPTS:
                logger.error(
                    "URL failed after %s attempts: %s",
                    attempt,
                    url
                )
                raise
            
            # exponential backoff:
            # attempt 1 fails -> wait 1 sec
            # attempt 2 fails -> wait 2 sec
            delay = 2 ** (attempt - 1)
            
            logger.warning(
                "Attempt %s failed for %s: %s. "
                "Retrying in %s seconds.",
                attempt,
                url,
                type(error).__name__,
                delay
            )
            
            # unlike time.sleep(), asyncio.sleep() doesn't 
            # block the event loop while waiting
            # JS equivalent: await new Promise(resolve => setTimeout(resolve, delay * 1000))
            await asyncio.sleep(delay)