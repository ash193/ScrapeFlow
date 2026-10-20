import asyncio
import time

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/catalogue/page-{}.html"

URLS = [BASE_URL.format(page) for page in range(1, 6)]

async def scrape_page(client: httpx.AsyncClient, url: str):
    # Send an async HTTP request
    # While waiting for the response, other tasks can run
    response = await client.get(url)
    
    # raises an exception if the websites returns a 4xx or 5xx error
    response.raise_for_status()
    
    # Parse the HTML returned by the website
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Select all book cards from the page
    books = soup.select("article.product_pod")
    
    results = []
    
    for book in books:
        # Extract the book title and its displayed price
        title = book.select_one("h3 a")["title"]
        price = book.select_one(".price_color").get_text(strip=True)
        
        # Store the extracted info into a dict
        results.append({
            "title", title,
            "price", price
        })
    
    return results

async def main():
    # Record the starting time to measure performances
    start_time = time.perf_counter()
    
    # Create one reusable async HTTP client
    # Similar to opening and closing a shared network connection manager
    async with httpx.AsyncClient(timeout=15) as client:
        # Create a list of coroutine objects, one for each URL
        tasks = [scrape_page(client, url) for url in URLS]
        
        # Run all scraping operations concurrently
        # JS equivalent: await Promise.all(tasks)
        results = await asyncio.gather(*tasks)
    
    # Each item in results is a list of books from one webpage
    # Flatten the nested lists into a single list
    all_books = [book for page in results for book in page]
    
    # Measure the elapsed execution time
    elapsed = time.perf_counter() - start_time
    print(f"Total books scraped: {len(all_books)}")
    print(f"Execution time: {elapsed:.2f} seconds")
    
    # Display the first 5 books to verify our results
    for book in all_books[:5]:
        print(book)

if __name__ == "__main__":
    # Start Python's asyncio event loop 
    asyncio.run(main())