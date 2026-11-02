from app.config import get_allowed_hosts

def test_multiple_allowed_hosts(monkeypatch):
    # simulate environment configuration without changing
    # the actual .env docker file
    monkeypatch.setenv(
        "ALLOWED_HOSTS",
        "books.toscrape.com,quotes.toscrape.com"
    )
    
    assert get_allowed_hosts() == {
        "books.toscrape.com",
        "quotes.toscrape.com"
    }

def test_allowed_hosts_normalization(monkeypatch):
    # verify that whitespace and capitalization are normalized
    # duplicate hosts should also be removed by the set
    monkeypatch.setenv(
        "ALLOWED_HOSTS",
        " Books.ToScrape.Com , quotes.toscrape.com,books.toscrape.com"
    )
    
    assert get_allowed_hosts() == {
        "books.toscrape.com",
        "quotes.toscrape.com",
    }

def test_default_allowed_hosts(monkeypatch):
    # remove the variable to simulate a missing configuration
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    
    assert get_allowed_hosts() == {"books.toscrape.com"}
    