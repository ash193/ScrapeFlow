import httpcore
import pytest
import httpx
from app.secure_network import SecureNetworkBackend
from app.secure_transport import SecureHTTPTransport

@pytest.mark.asyncio
async def test_transport_uses_secure_network_backend():
    """
    Verify that HTTPX's transport is configured to use
    our restricted TCP networking implementation.
    """
    transport = SecureHTTPTransport()
    
    try:
        # the transport should use an HTTP Core connection pool
        assert isinstance(
            transport._pool,
            httpcore.AsyncConnectionPool,
        )
        
        # verify that the pool uses our secure backend
        assert isinstance(
            transport._pool._network_backend,
            SecureNetworkBackend,
        )
        
        # confirm that our pool has a TLS context
        assert transport._pool._ssl_context.verify_mode != 0
    
    finally:
        # release connections and other transport resources
        await transport.aclose()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://books.toscrape.com:443/",
        "https://books.toscrape.com:8443/",
        "https://example.com/",
        "https://user:pass@books.toscrape.com/",
        "https://127.0.0.1/",
    ]
)
async def test_transport_rejects_unsafe_requests(url):
    """
    The transport must reject unsafe requests
    before allowing a network connection.
    """
    async with httpx.AsyncClient(
        transport=SecureHTTPTransport(),
        trust_env=False,
    ) as client:
        with pytest.raises(
            httpx.ConnectError,
            match="Request destination is not approved"
        ):
            await client.get(url)
