import httpx
from bs4 import BeautifulSoup
from soupsieve.util import SelectorSyntaxError

import asyncio
from urllib.parse import urlsplit
from app.url_validator import is_allowed_url
from app.dns_validator import resolves_to_public_ips

async def validate_scraping_destination(url: str) -> None:
    """
    Check the URL and its DNS results before requesting it.
    This is preliminary validation. Connection-time IP
    restrictions are still needed for complete SSRF protection
    """
    # verify HTTPs, hostname allowlist, port, and URL structure
    if not is_allowed_url(url):
        raise ValueError("URL is not an approved scraping target")
    
    # Extract the hostname from the validated URL
    hostname = urlsplit(url).hostname
    
    # DNS resolution is synchronous
    # run it in a separate thread so the asyncio event
    # loop can continue handling other scraping requests
    is_public = await asyncio.to_thread(
        resolves_to_public_ips,
        hostname,
    )
    
    # reject hostnames with unsafe or unresolved addresses
    if not is_public:
        raise ValueError("Scraping destination failed DNS validation")

async def extract_page(
    url: str,
    selectors: dict[str, str]
) -> dict:
    # reject unapproved URLs or unsafe DNS results
    await validate_scraping_destination(url)
    
    # Create an asynchronous HTTP client
    # Redirects are disabled so the request cannot silently
    # follow a redirect to an invalidated destination.
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