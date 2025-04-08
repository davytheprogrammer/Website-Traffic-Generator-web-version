import requests
from bs4 import BeautifulSoup
import urllib.parse
import logging
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from user_agents import get_random_user_agent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('url_analyzer')

class UrlAnalyzer:
    def __init__(self, base_url, max_depth=2, max_urls=200):
        """
        Initialize the URL analyzer
        
        Args:
            base_url (str): The starting URL
            max_depth (int): Maximum depth to crawl
            max_urls (int): Maximum number of URLs to discover
        """
        self.base_url = base_url
        self.base_domain = urllib.parse.urlparse(base_url).netloc
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.discovered_urls = set()
        self.visited_urls = set()
        self.session = requests.Session()
        
    def discover_urls(self):
        """
        Discover URLs starting from the base URL
        
        Returns:
            list: List of discovered URLs
        """
        logger.info(f"Starting URL discovery from {self.base_url}")
        
        # Start with the base URL
        self.discovered_urls.add(self.base_url)
        
        # Crawl the website to discover URLs
        self._crawl(self.base_url, depth=0)
        
        # Convert to list and sort
        urls_list = sorted(list(self.discovered_urls))
        
        logger.info(f"Discovered {len(urls_list)} URLs")
        return urls_list
    
    def _crawl(self, url, depth):
        """
        Recursively crawl the website to discover URLs
        
        Args:
            url (str): Current URL to crawl
            depth (int): Current depth
        """
        # Check if we've reached the limits
        if depth > self.max_depth or len(self.discovered_urls) >= self.max_urls or url in self.visited_urls:
            return
        
        # Mark as visited
        self.visited_urls.add(url)
        
        try:
            # Get page content
            headers = {'User-Agent': get_random_user_agent()}
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Got status code {response.status_code} for {url}")
                return
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all links
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                
                # Skip empty links
                if not href or href == '#' or href.startswith('javascript:'):
                    continue
                
                # Convert relative URLs to absolute
                absolute_url = urllib.parse.urljoin(url, href)
                parsed_url = urllib.parse.urlparse(absolute_url)
                
                # Only keep links to the same domain
                if parsed_url.netloc == self.base_domain:
                    # Filter out non-webpage links and fragments
                    if not any(absolute_url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.zip']):
                        # Remove fragments from URLs
                        clean_url = absolute_url.split('#')[0]
                        links.append(clean_url)
            
            # Add discovered links
            for link in links:
                if link not in self.discovered_urls:
                    self.discovered_urls.add(link)
                    
                    # Log progress
                    if len(self.discovered_urls) % 10 == 0:
                        logger.info(f"Discovered {len(self.discovered_urls)} URLs so far")
                    
                    # Stop if we've reached the limit
                    if len(self.discovered_urls) >= self.max_urls:
                        logger.info(f"Reached maximum URL limit ({self.max_urls})")
                        return
            
            # Crawl discovered links
            if depth < self.max_depth:
                # Use multithreading for faster crawling
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(self._crawl, link, depth + 1) for link in links[:10]]
                    for future in as_completed(futures):
                        pass  # We don't need the results
                        
        except Exception as e:
            logger.error(f"Error crawling {url}: {str(e)}")

def discover_urls(url, max_depth=2, max_urls=200):
    """
    Discover URLs starting from a base URL
    
    Args:
        url (str): The starting URL
        max_depth (int): Maximum depth to crawl
        max_urls (int): Maximum number of URLs to discover
        
    Returns:
        list: List of discovered URLs
    """
    analyzer = UrlAnalyzer(url, max_depth, max_urls)
    return analyzer.discover_urls()