import ipaddress
import socket

def resolves_to_public_ips(hostname: str) -> bool:
    """
    Check whether a hostname resolves exclusively
    to globally routable IP addresses
    
    Reject the hostname if:
    - DNS resolution fails
    - No addresses are returned
    - Any resolved address is non-global
    """
    try:
        # resolve the hostname into IPv4/IPv6 addresses
        # SOCK_STREAM requests TCP-compatible addresses
        addresses = socket.getaddrinfo(
            hostname,
            443,
            type=socket.SOCK_STREAM
        )
    
    except (socket.gaierror, OSError):
        # fail closed when DNS cannot be resolved 
        return False
    
    # do not accept a hostname without resolved addresses
    if not addresses:
        return False
    
    for address in addresses:
        # sockaddr contains the resolved IP and port
        ip_string = address[4][0]
        
        # convert the IP string into an IPv4/IPv6
        ip = ipaddress.ip_address(ip_string)
        
        # reject private, loopback, link-local, reserved
        # and other addresses that are not globally routable
        if not ip.is_global:
            return False
    
    # every resolved IP passed our checks
    return True

        