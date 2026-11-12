import socket
from unittest.mock import AsyncMock
import httpcore
import pytest
from app.secure_network import SecureNetworkBackend

@pytest.mark.asyncio
async def test_connects_to_validated_public_ip(monkeypatch):
    # simulate the approved hostname resolving to a public IP
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("8.8.8.8", 443),
            )
        ]
    )
    
    backend = SecureNetworkBackend()
    
    # mock the actual TCP connection
    mock_connect = AsyncMock()
    monkeypatch.setattr(
        backend.backend,
        "connect_tcp",
        mock_connect,
    )
    
    await backend.connect_tcp(
        "books.toscrape.com",
        443,
    )
    
    # verify that the connection uses the validated IP
    assert mock_connect.await_args.kwargs["host"] == "8.8.8.8"

@pytest.mark.asyncio
async def test_rejects_private_destination(monkeypatch):
    # simulate a hostname resolving to an internal IP
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.1.10", 443),
            )
        ]
    )
    
    backend = SecureNetworkBackend()
    mock_connect = AsyncMock()
    monkeypatch.setattr(backend.backend, "connect_tcp", mock_connect)
    
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("books.toscrape.com", 443)
    
    # no tcp connection should have been attempted
    mock_connect.assert_not_awaited()

@pytest.mark.asyncio
async def test_rejects_unapproved_hostname():
    backend = SecureNetworkBackend()
    
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("example.com", 443)

@pytest.mark.asyncio
async def test_connection_uses_validated_ip_not_hostname(monkeypatch):
    """
    Verify that the TCP backend receives the validated IP,
    rather than the original hostname.
    This prevents an additional hostname lookup inside
    the underlying TCP connection method.
    """
    
    # the approved hostname resolves to this public IP
    validated_ip = "8.8.8.8"
    
    def fake_getaddrinfo(*args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (validated_ip, 443)
            )
        ]
    
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        fake_getaddrinfo,
    )
    
    backend = SecureNetworkBackend()
    
    # we don't open a real socket
    mock_connect = AsyncMock()
    monkeypatch.setattr(
        backend.backend,
        "connect_tcp",
        mock_connect,
    )
    
    await backend.connect_tcp(
        "books.toscrape.com",
        443
    )
    
    # the actual connection must receive the vetted IP
    mock_connect.assert_awaited_once()
    
    connection_host = mock_connect.await_args.kwargs["host"]
    
    assert connection_host == validated_ip
    assert connection_host != "books.toscrape.com"