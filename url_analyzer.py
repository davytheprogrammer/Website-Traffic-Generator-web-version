import requests
from bs4 import BeautifulSoup
import urllib.parse
import logging
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from user_agents import get_random_user_agent
from urllib.robotparser import RobotFileParser

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
        parsed_url = urllib.parse.urlparse(base_url)
        self.base_domain = parsed_url.netloc
        self.base_scheme = parsed_url.scheme or 'http'
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.discovered_urls = set()
        self.visited_urls = set()
        self.session = requests.Session()
        self.robots_parser = RobotFileParser()
        self.robots_parser.set_url(urllib.parse.urljoin(base_url, '/robots.txt'))
        try:
            self.robots_parser.read()
        except Exception as e:
            logger.warning(f"Could not read robots.txt: {str(e)}")
        
    def discover_urls(self):
        """
        Discover URLs starting from the base URL
        
        Returns:
            list: List of discovered URLs
        """
        logger.info(f"Starting URL discovery from {self.base_url}")
        
        # Start with the base URL
        self.discovered_urls.add(self.base_url)
        
        # Try multiple crawling strategies
        strategies = [
            self._crawl_with_bfs,
            self._crawl_with_sitemap,
            self._crawl_with_alternative_methods
        ]
        
        for strategy in strategies:
            if len(self.discovered_urls) >= self.max_urls:
                break
            try:
                strategy()
            except Exception as e:
                logger.error(f"Strategy {strategy.__name__} failed: {str(e)}")
                continue
        
        # Convert to list and sort
        urls_list = sorted(list(self.discovered_urls))
        
        logger.info(f"Discovered {len(urls_list)} URLs")
        return urls_list
    
    def _crawl_with_bfs(self):
        """Breadth-first search crawling strategy"""
        self._crawl(self.base_url, depth=0)
    
    def _crawl_with_sitemap(self):
        """Try to find and parse sitemap.xml"""
        sitemap_urls = [
            urllib.parse.urljoin(self.base_url, 'sitemap.xml'),
            urllib.parse.urljoin(self.base_url, 'sitemap_index.xml'),
            urllib.parse.urljoin(self.base_url, 'sitemap/sitemap.xml'),
            urllib.parse.urljoin(self.base_url, 'sitemap.txt'),
            urllib.parse.urljoin(self.base_url, 'sitemap.gz'),
        ]
        
        for sitemap_url in sitemap_urls:
            if len(self.discovered_urls) >= self.max_urls:
                return
                
            try:
                headers = {'User-Agent': get_random_user_agent()}
                response = self.session.get(sitemap_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    # Handle different sitemap formats
                    if sitemap_url.endswith('.xml'):
                        soup = BeautifulSoup(response.text, 'lxml')
                        urls = [loc.text for loc in soup.find_all('loc')]
                    elif sitemap_url.endswith('.txt'):
                        urls = response.text.splitlines()
                    else:
                        continue
                    
                    for url in urls:
                        if len(self.discovered_urls) >= self.max_urls:
                            return
                            
                        parsed_url = urllib.parse.urlparse(url)
                        if parsed_url.netloc == self.base_domain:
                            clean_url = url.split('#')[0]
                            self.discovered_urls.add(clean_url)
                            
            except Exception as e:
                logger.warning(f"Could not parse sitemap at {sitemap_url}: {str(e)}")
    
    def _crawl_with_alternative_methods(self):
        """Alternative crawling methods when standard methods fail"""
        logger.info("Attempting alternative crawling methods")
        
        # Try common URL patterns
        common_paths = [
            '', 'index', 'home', 'main', 'about', 'contact',
            'products', 'services', 'blog', 'news', 'articles'
        ]
        
        for path in common_paths:
            if len(self.discovered_urls) >= self.max_urls:
                return
                
            test_url = urllib.parse.urljoin(self.base_url, path)
            if test_url not in self.visited_urls:
                self._crawl(test_url, depth=0)
    
    def _is_allowed(self, url):
        """Check if URL is allowed by robots.txt"""
        try:
            return self.robots_parser.can_fetch('*', url)
        except:
            return True  # Assume allowed if robots.txt can't be read
    
    def _crawl(self, url, depth):
        """
        Recursively crawl the website to discover URLs
        
        Args:
            url (str): Current URL to crawl
            depth (int): Current depth
        """
        # Check if we've reached the limits
        if (depth > self.max_depth or 
            len(self.discovered_urls) >= self.max_urls or 
            url in self.visited_urls or
            not self._is_allowed(url)):
            return
        
        # Mark as visited
        self.visited_urls.add(url)
        
        try:
            # Get page content with random delay
            time.sleep(random.uniform(0.5, 1.5))
            headers = {'User-Agent': get_random_user_agent()}
            response = self.session.get(url, headers=headers, timeout=15)
            
            # Handle redirects
            if response.url != url and response.url not in self.visited_urls:
                self.discovered_urls.add(response.url)
                if depth < self.max_depth:
                    self._crawl(response.url, depth + 1)
                return
            
            if response.status_code != 200:
                logger.warning(f"Got status code {response.status_code} for {url}")
                return
            
            # Check if this is HTML content
            content_type = response.headers.get('content-type', '')
            if 'text/html' not in content_type:
                return
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract and add links
            self._extract_and_add_links(soup, url)
            
            # Crawl discovered links
            if depth < self.max_depth:
                # Use multithreading for faster crawling
                with ThreadPoolExecutor(max_workers=5) as executor:
                    # Get recent links that haven't been visited yet
                    recent_links = [link for link in self.discovered_urls 
                                  if link not in self.visited_urls][:20]
                    
                    futures = [executor.submit(self._crawl, link, depth + 1) 
                              for link in recent_links]
                    for future in as_completed(futures):
                        try:
                            future.result()  # We don't need the results but want to catch exceptions
                        except Exception as e:
                            logger.error(f"Error in crawling thread: {str(e)}")
                        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error crawling {url}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error crawling {url}: {str(e)}")
    
    def _extract_and_add_links(self, soup, base_url):
        """Extract links from HTML and add them to discovered URLs"""
        links = set()
        
        # Check <a> tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            if self._is_valid_link(href):
                absolute_url = urllib.parse.urljoin(base_url, href)
                clean_url = self._clean_url(absolute_url)
                if clean_url:
                    links.add(clean_url)
        
        # Check <link> tags
        for link_tag in soup.find_all('link', href=True):
            href = link_tag['href'].strip()
            if self._is_valid_link(href):
                absolute_url = urllib.parse.urljoin(base_url, href)
                clean_url = self._clean_url(absolute_url)
                if clean_url:
                    links.add(clean_url)
        
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
    
    def _is_valid_link(self, href):
        """Check if a link should be processed"""
        if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            return False
        if any(href.endswith(ext) for ext in [
            '.jpg', '.jpeg', '.png', '.gif', '.pdf', '.zip', '.rar',
            '.exe', '.dmg', '.mp3', '.mp4', '.avi', '.mov', '.css',
            '.js', '.svg', '.ico', '.webp', '.woff', '.woff2'
        ]):
            return False
        return True
    
    def _clean_url(self, url):
        """Clean and normalize a URL"""
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc != self.base_domain:
            return None
        
        # Remove fragments and query parameters we don't care about
        clean_url = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            '',  # Remove params
            '',  # Remove query
            ''   # Remove fragment
        ))
        
        # Remove trailing slashes
        clean_url = clean_url.rstrip('/')
        
        return clean_url

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