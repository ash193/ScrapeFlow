import asyncio
import time
import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/catalogue/page-{}.html"

URLS = [BASE_URL.format(page) for page in range(1, 6)]

def count_books(html: str) -> int:
    # Parse the HTML and count the book elements
    # Both approaches use the same function for a fair comparison
    soup = BeautifulSoup(html, "html.parser")
    return len(soup.select("article.product_pod"))

def scrape_sync():
    total_books = 0
    
    # A reusable synchronous HTTP client
    # Requests inside this loop happen one after another
    with httpx.Client(timeout=15) as client:
        for url in URLS:
            response = client.get(url)
            response.raise_for_status()
            
            total_books += count_books(response.text)
    
    return total_books

async def scrape_async():
    # A reusable async HTTP client
    async with httpx.AsyncClient(timeout=15) as client:
        
        async def fetch_page(url):
            # await allows other requests to progress while
            # this request waits for a network response
            response = await client.get(url)
            response.raise_for_status()
            
            return count_books(response.text)
        
        # similar to promise.all() in js
        # schedule all 5 requests concurrently
        tasks = [fetch_page(url) for url in URLS]
        results = await asyncio.gather(*tasks)

    return sum(results)

def main():
    # measures how long the sync scraper takes
    start = time.perf_counter()
    sync_count = scrape_sync()
    sync_time = time.perf_counter() - start
    
    # measure how low the async scraper takes
    start = time.perf_counter()
    async_count = asyncio.run(scrape_async())
    async_time = time.perf_counter() - start
    
    print(f"Synchronous: {sync_count} books in {sync_time:.2f}s")
    print(f"Asynchronous: {async_count} books in {async_time:.2f}s")
    
    # verify that both implementation fetched the same amount
    assert sync_count == async_count, "Book counts do not match!"
    
    # calculates how many times faster or slower async execution was
    if async_time > 0:
        speedup = sync_time / async_time
        print(f"Speedup: {speedup:.2f}x")

if __name__ == "__main__":
    main()
            