import ipaddress
from urllib.parse import urlsplit
from app.config import ALLOWED_HOSTS

def is_allowed_url(url: str) -> bool:
    """
    Check whether a URL meets our scraping restrictions
    
    Requirements:
    - HTTPS only
    - Hostname must be explicitly approved
    - No IP-address literals
    - No embedded credentials
    - No custom ports
    """
    
    try:
        # parse the URL into its components
        parsed = urlsplit(url)
        
        # require HTTPs for scraping
        if parsed.scheme != "https":
            return False
        
        # reject URLs without a hostname
        if not parsed.hostname:
            return False
        
        # reject embedded credentials, such as user:password@host
        if parsed.username is not None or parsed.password is not None:
            return False

        # only allow the standard HTTPs port
        if parsed.port not in (None, 443):
            return False
        
        # normalize a trailing dot in fully qualified domain names
        hostname = parsed.hostname.rstrip(".")
        
        # reject IP addresses, including IPv4 and IPv6
        try:
            ipaddress.ip_address(hostname)
            return False
        except ValueError:
            # a ValueError here means the hostname is not an IP literal
            pass
        
        # reject any hostname not explicitly configured
        if hostname not in ALLOWED_HOSTS:
            return False
        
        return True
    
    except ValueError:
        # malformed URLs can raise ValueError during parsing
        return False
    
        