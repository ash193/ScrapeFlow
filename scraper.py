import httpx #HTTP client, similar to using fetch() in JS
from bs4 import BeautifulSoup #Library for parsing and searching HTML

URL = "https://books.toscrape.com/"

def scrape_books():
    #Send a synchronous GET request to retrieve the webpage
    #Unlike JS's fetch(), this blocks until the response arrives
    response = httpx.get(URL, timeout=10)
    
    #Raises an exception if the server returns an HTTP error
    response.raise_for_status()
    
    #Convert the raw HTML response into a searchable document
    #Similar to using a DOM parser in JS
    soup = BeautifulSoup(response.text, "html.parser")
    
    #Find all HTML elements matching this CSS selector
    #JS equivalent: document.querySelectorAll("article.product_prod")
    books = soup.select("article.product_pod")
    
    results = []
    
    for book in books:
        title = book.select_one("h3 a")["title"]
        price = book.select_one(".price_color").get_text(strip=True)
        
        results.append({
            "title": title,
            "price": price
        })
    
    return results

if __name__ == "__main__":
    books = scrape_books()
    
    for book in books:
        print(book)
        