from pydantic import BaseModel, Field, HttpUrl

class ExtractionRequest(BaseModel):
    # The website the user wants to scrape
    # HttpUrl checks that the input has valid HTTP/HTTPS url syntax
    url: HttpUrl
    
    # A dictionary mapping field names to CSS selectors
    # Example: {"title": "h3 a", "price": ".price_color"}
    # default_factory creates a new empty dictionary for each request
    selectors: dict[str, str] = Field(
        default_factory=dict,
        max_length=10
    )
    
class ExtractionResponse(BaseModel):
    # The URL we retrieved
    url: str
    
    # Generic page information
    title: str | None
    description: str | None
    
    # Data extracted using user-provided CSS selectors
    # A field may be None if its selectors matches nothing
    extracted: dict[str, str | None]

class BatchExtractionRequest(BaseModel):
    # accepts a list of urls rather than a single url
    urls: list[HttpUrl] = Field(
        min_length=1,
        max_length=10
    )
    
    # css selectors applied to every URL in the batch
    # default_factory creates a separate dictionary per request
    selectors: dict[str, str] = Field(
        default_factory=dict,
        max_length=10
    )
    