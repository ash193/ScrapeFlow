import asyncio
import ipaddress
import socket
import httpcore
from app.url_validator import is_allowed_url

class SecureNetworkBackend(httpcore.AsyncNetworkBackend):
    """
    Restrict outbound TCP connections to approved,
    publicly routable HTTPS destinations
    """
    
    def __init__(self):
        # reuse HTTP Core's normal async socket handling
        self.backend = httpcore.AnyIOBackend()
        
    async def connect_tcp(self, host, port, timeout = None, local_address = None, socket_options = None):
        # only permit the standard HTTPS destination port
        if port != 443 or not is_allowed_url(f"https://{host}/"):
            raise httpcore.ConnectError(
                "Connection destination is not approved"
            )
        try: 
            # resolve the hostname before connecting
            # run sync DNS resolution in a thread
            addresses = await asyncio.to_thread(
                socket.getaddrinfo,
                host,
                port,
                type=socket.SOCK_STREAM,
            )
            if not addresses:
                raise httpcore.ConnectError(
                    "No destination addresses found"
                )
            
            validated_ips = []
            
            for address in addresses:
                ip_string = address[4][0]
                ip = ipaddress.ip_address(ip_string)
                
                # fail closed if any address is non-global
                if not ip.is_global:
                    raise httpcore.ConnectError(
                        "Destination resolves to a non-public IP"
                    )
                
                validated_ips.append(str(ip))
        
        except (OSError, ValueError) as error:
            raise httpcore.ConnectError(
                "Unable to validate destination DNS"
            ) from error
            
        # connect directly to the validated IP address
        # do not pass the original hostname here
        return await self.backend.connect_tcp(
            host=validated_ips[0],
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )
    
    async def connect_unix_socket(self, path, timeout = None, socket_options = None):
        # unix sockets are not permitted for scraping
        raise httpcore.ConnectError(
            "Unix socket connections are not allowed"
        )
    
    async def sleep(self, seconds):
        await self.backend.sleep(seconds)