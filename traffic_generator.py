import requests
from bs4 import BeautifulSoup
import time
import random
import urllib.parse
import logging
from datetime import datetime
import threading

# Import custom modules
from user_agents import get_random_user_agent
from proxy_manager import get_random_proxy

class TrafficGenerator:
    def __init__(self, base_url, max_visits, session_id, socketio):
        """
        Initialize the traffic generator
        
        Args:
            base_url (str): The starting URL
            max_visits (int): Maximum number of visits to generate
            session_id (str): Unique session identifier
            socketio: SocketIO instance for real-time updates
        """
        self.base_url = base_url
        self.base_domain = urllib.parse.urlparse(base_url).netloc
        self.max_visits = min(max_visits, 500)  # Cap at 500
        self.visits_completed = 0
        self.urls_visited = []
        self.session_id = session_id
        self.socketio = socketio
        self._active = False
        self._lock = threading.Lock()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(f'TrafficGenerator-{session_id}')
        
        # Create requests session for maintaining cookies
        self.session = requests.Session()
        
    def is_active(self):
        """Check if traffic generation is active"""
        with self._lock:
            return self._active
            
    def stop(self):
        """Stop traffic generation"""
        with self._lock:
            self._active = False
        self.logger.info(f"Traffic generation stopped after {self.visits_completed} visits")
            
    def start(self):
        """Start traffic generation"""
        with self._lock:
            self._active = True
        
        self.logger.info(f"Starting traffic generation for {self.base_url} with {self.max_visits} visits")
        
        # Visit the base URL first
        self._visit_url(self.base_url)
        
        # Continue visiting random links until max visits reached or stopped
        while self.is_active() and self.visits_completed < self.max_visits:
            # Get discovered links from previous visits
            if not self.urls_visited:
                break
                
            last_url = self.urls_visited[-1]['url']
            links = self._extract_links(last_url)
            
            if not links:
                # No links found, go back to base URL
                self._visit_url(self.base_url)
                continue
                
            # Select a random link to visit
            next_url = random.choice(links)
            self._visit_url(next_url)
            
            # Random delay between 5-15 seconds to mimic human behavior
            # But ensure minimum 5 seconds as per requirements
            delay = random.uniform(5, 15)
            time.sleep(delay)
        
        # Mark as inactive when done
        with self._lock:
            self._active = False
            
        self.logger.info(f"Traffic generation completed with {self.visits_completed} visits")
        
        # Notify clients that generation is complete
        self.socketio.emit('generation_complete', {
            'session_id': self.session_id,
            'visits_completed': self.visits_completed,
            'urls_visited': self.urls_visited
        })
            
    def _visit_url(self, url):
        """
        Visit a specific URL and record the visit
        
        Args:
            url (str): URL to visit
        """
        try:
            # Rotate user agent for each request
            headers = {
                'User-Agent': get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': self.urls_visited[-1]['url'] if self.urls_visited else self.base_url,
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
            }
            
            # Get proxy if available
            proxy = get_random_proxy()
            proxies = {'http': proxy, 'https': proxy} if proxy else None
            
            # Make the request
            self.logger.info(f"Visiting URL: {url}")
            response = self.session.get(
                url, 
                headers=headers, 
                proxies=proxies,
                timeout=30,
                allow_redirects=True
            )
            
            # Record the visit
            visit_data = {
                'url': response.url,  # Use final URL after redirects
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'status_code': response.status_code
            }
            
            self.urls_visited.append(visit_data)
            self.visits_completed += 1
            
            # Emit update to connected clients
            self.socketio.emit('visit_update', {
                'session_id': self.session_id,
                'visit': visit_data,
                'visits_completed': self.visits_completed,
                'max_visits': self.max_visits
            })
            
            return response.text
            
        except Exception as e:
            self.logger.error(f"Error visiting URL {url}: {str(e)}")
            return None
            
    def _extract_links(self, url):
        """
        Extract links from a web page
        
        Args:
            url (str): URL to extract links from
            
        Returns:
            list: List of valid URLs found on the page
        """
        try:
            # Get page content
            headers = {'User-Agent': get_random_user_agent()}
            response = self.session.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                return []
                
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all links
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                
                # Convert relative URLs to absolute
                absolute_url = urllib.parse.urljoin(url, href)
                parsed_url = urllib.parse.urlparse(absolute_url)
                
                # Only keep links to the same domain
                if parsed_url.netloc == self.base_domain:
                    # Filter out non-webpage links (e.g., images, pdfs)
                    if not any(absolute_url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.zip']):
                        links.append(absolute_url)
            
            return links
            
        except Exception as e:
            self.logger.error(f"Error extracting links from {url}: {str(e)}")
            return []