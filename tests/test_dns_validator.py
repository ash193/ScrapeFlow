import socket
from app.dns_validator import resolves_to_public_ips

def test_accepts_public_ipv4(monkeypatch):
    # simulate DNS returning a public IP address
    def fake_getaddrinfo(*args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("8.8.8.8", 443)
            )
        ]
    
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    
    assert resolves_to_public_ips("example.com") is True
    
def test_rejects_private_ipv4(monkeypatch):
    # simulate a hostname resolving to a private network
    def fake_getaddrinfo(*args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.1.10", 443),
            )
        ]
    
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    
    assert resolves_to_public_ips("example.com") is False
    
def test_rejects_mixed_addresses(monkeypatch):
    # reject the destination if even one IP is unsafe
    def fake_getaddrinfo(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]
    
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    
    assert resolves_to_public_ips("example.com") is False

def tests_rejects_dns_failure(monkeypatch):
    # simulate a hostname that cannot be resolved
    def fake_getaddrinfo(*args, **kwargs):
        raise socket.gaierror("DNS lookup failed")
    
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    
    assert resolves_to_public_ips("example.com") is False