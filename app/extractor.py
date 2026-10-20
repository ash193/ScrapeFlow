import httpx
from bs4 import BeautifulSoup
from soupsieve.util import SelectorSyntaxError

async def extract_page(
    url: str,
    selectors: dict[str, str]
) -> dict:
    # Create an asynchronous HTTP client
    # Redirects are disabled so the request cannot silently
    # follow a redirect to an unvalidated destination.
    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=False
    ) as client:
        # Download the page without blocking the event loop 
        # while the network request is in progress
        response = await client.get(url)
        response.raise_for_status()
        
    # Parse the downloaded HTML
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Extract the page's HTML title, if available
    title = soup.title.get_text(strip=True) if soup.title else None
    
    # Extract its meta description, if one exists
    meta = soup.select_one('meta[name="description"]')
    description = meta.get("content") if meta else None
    
    # store custom extracted fields here
    extracted = {}
    
    for field_name, css_selector in selectors.items():
        # Find the first HTML element matching the selector
        element = soup.select_one(css_selector)
        
        # extract visible text if an element was found
        extracted[field_name] = (
            element.get_text(strip=True) if element else None
        )
        
    # Return a regular python dict
    return {
        "url": url,
        "title": title,
        "description": description,
        "extracted": extracted
        
    }