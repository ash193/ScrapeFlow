import os

def get_allowed_hosts() -> set[str]:
    """
    Load approved scraping hostnames from the env
    
    Example:
    ALLOWED_HOSTS=books.toscrape.com, quotes.toscrape.com
    
    Returns:
        A set of normalized hostnames.
    """
    
    # use our testing website when no configuration is provided
    hosts = os.getenv(
        "ALLOWED_HOSTS",
        "books.toscrape.com"
    )
    
    # split the comma-separated string into individual hostnames
    return {
        host.strip().lower()
        for host in hosts.split(",")
        if host.strip()
    }

# shared application configuration
ALLOWED_HOSTS = get_allowed_hosts()
