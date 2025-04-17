import requests
from bs4 import BeautifulSoup
import logging
import threading
import time
import random
from urllib.parse import urlparse, urljoin

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('web_scraper')

class WebScraper:
    def __init__(self, base_url, max_depth=2, max_urls=100):
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.visited_urls = set()
        self.discovered_urls = set()
        self.lock = threading.Lock()

    def fetch_html(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def extract_links(self, html, base_url):
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if not href.startswith(('http://', 'https://')):
                href = urljoin(base_url, href)
            if urlparse(href).netloc == self.base_domain:
                links.add(href)
        return links

    def scrape(self, url, depth):
        if depth > self.max_depth or len(self.discovered_urls) >= self.max_urls:
            return
        html = self.fetch_html(url)
        if html:
            links = self.extract_links(html, url)
            with self.lock:
                self.discovered_urls.update(links)
            for link in links:
                if link not in self.visited_urls:
                    with self.lock:
                        self.visited_urls.add(link)
                    self.scrape(link, depth + 1)

    def start_scraping(self):
        self.scrape(self.base_url, 0)
        logger.info(f"Discovered {len(self.discovered_urls)} URLs")

def main():
    base_url = 'https://example.com'
    scraper = WebScraper(base_url)
    scraper.start_scraping()

if __name__ == "__main__":
    main()
