import httpcore
import httpx
from app.secure_network import SecureNetworkBackend
from app.url_validator import is_allowed_url

class SecureHTTPTransport(httpx.AsyncHTTPTransport):
    """
    HTTPX transport using our restricted network backend.
    The connection pool retains normal HTTPs handling,
    but TCP connections go through SecureNetworkBackend.
    """
    
    def __init__(self):
        # initialize HTTPX's standard async transport
        super().__init__(verify=True, trust_env=False)
        
        # replace the default connection pool with one
        # using our restricted TCP network backend
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpcore.default_ssl_context(),
            network_backend=SecureNetworkBackend(),
            http1=True,
            http2=False,
            max_connections=10,
            max_keepalive_connections=5,
        )
    
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """
        Reject disallowed requests before they reach the HTTP Core connection pool.
        """
        # enforce HTTPS, approved hosts, safe ports,
        # and the other URL validation rules
        if not is_allowed_url(str(request.url)):
            raise httpx.ConnectError(
                "Request destination is not approved",
                request=request
            )
        
        # delegate approved requests to HTTPX's
        # existing transport implementation
        return await super().handle_async_request(request)