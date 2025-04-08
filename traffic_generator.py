import requests
from bs4 import BeautifulSoup
import time
import random
import urllib.parse
import logging
from datetime import datetime
import threading
from collections import Counter

# Import custom modules
from user_agents import get_random_user_agent

class TrafficGenerator:
    def __init__(self, base_url, max_visits, session_id, socketio, url_list=None):
        """
        Initialize the traffic generator
        
        Args:
            base_url (str): The starting URL
            max_visits (int): Maximum number of visits to generate
            session_id (str): Unique session identifier
            socketio: SocketIO instance for real-time updates
            url_list (list): Optional list of pre-discovered URLs to visit
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
        
        # Pre-discovered URLs list
        self.url_list = url_list if url_list else []
        self.url_weights = {}  # For weighted selection
        
        # Browsing pattern tracking
        self.current_path = []  # Stack to track browsing path
        self.visit_history = Counter()  # Track visit count per URL
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(f'TrafficGenerator-{session_id}')
        
        # Create requests session for maintaining cookies
        self.session = requests.Session()
        
        # Calculate URL weights if we have pre-discovered URLs
        if self.url_list:
            self._calculate_url_weights()
        
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
        
        # Emit starting message
        self.socketio.emit('generation_start', {
            'session_id': self.session_id,
            'base_url': self.base_url,
            'max_visits': self.max_visits,
            'url_count': len(self.url_list)
        })
        
        # Visit the base URL first
        success = self._visit_url(self.base_url)
        
        # If first visit fails, report error and stop
        if not success:
            self.logger.error(f"Failed to visit base URL: {self.base_url}")
            self.socketio.emit('generation_error', {
                'session_id': self.session_id,
                'message': "Failed to access the base URL. Please check the URL and try again."
            })
            with self._lock:
                self._active = False
            return
        
        # Continue visiting random links until max visits reached or stopped
        while self.is_active() and self.visits_completed < self.max_visits:
            # Choose the next URL to visit
            next_url = self._choose_next_url()
            
            if next_url:
                success = self._visit_url(next_url)
                
                # If the visit fails, try another URL
                if not success and self.url_list:
                    # Try up to 3 more URLs before giving up
                    for _ in range(3):
                        next_url = self._choose_next_url()
                        if next_url and self._visit_url(next_url):
                            break
            else:
                # If no URLs are available, go back to base URL
                self.logger.warning("No URLs available, returning to base URL")
                self._visit_url(self.base_url)
            
            # Random delay between 5-15 seconds to mimic human behavior
            # But ensure minimum 5 seconds as per requirements
            delay = random.uniform(5, 15)
            self.logger.info(f"Waiting {delay:.1f} seconds before next request")
            
            # Send a waiting status update
            self.socketio.emit('waiting_update', {
                'session_id': self.session_id,
                'wait_time': round(delay, 1),
                'next_action': "Selecting next URL"
            })
            
            time.sleep(delay)
        
        # Mark as inactive when done
        with self._lock:
            self._active = False
            
        self.logger.info(f"Traffic generation completed with {self.visits_completed} visits")
        
        # Calculate and send statistics
        stats = self._calculate_statistics()
        
        # Notify clients that generation is complete
        self.socketio.emit('generation_complete', {
            'session_id': self.session_id,
            'visits_completed': self.visits_completed,
            'urls_visited': self.urls_visited,
            'statistics': stats
        })
    
    def _calculate_statistics(self):
        """Calculate statistics about the traffic generation session"""
        if not self.urls_visited:
            return {}
        
        # Count visits per URL
        url_counts = Counter()
        for visit in self.urls_visited:
            url_counts[visit['url']] += 1
        
        # Find most visited URLs
        most_visited = url_counts.most_common(5)
        
        # Calculate average time between visits
        timestamps = [datetime.strptime(visit['timestamp'], '%Y-%m-%d %H:%M:%S') 
                    for visit in self.urls_visited]
        if len(timestamps) > 1:
            time_diffs = [(timestamps[i] - timestamps[i-1]).total_seconds() 
                        for i in range(1, len(timestamps))]
            avg_time_between = sum(time_diffs) / len(time_diffs)
        else:
            avg_time_between = 0
            
        # Calculate status code distribution
        status_counts = Counter()
        for visit in self.urls_visited:
            status_counts[visit['status_code']] += 1
            
        return {
            'most_visited_urls': most_visited,
            'avg_time_between_visits': round(avg_time_between, 2),
            'status_code_distribution': {str(k): v for k, v in status_counts.items()},
            'unique_urls_visited': len(set(v['url'] for v in self.urls_visited)),
            'total_visits': len(self.urls_visited)
        }
    
    def _calculate_url_weights(self):
        """Calculate weights for URL selection based on URL structure"""
        for url in self.url_list:
            # Parse URL
            parsed = urllib.parse.urlparse(url)
            path_parts = parsed.path.split('/')
            
            # URLs with more path components might be deeper content pages
            # Give them lower weights to simulate more natural browsing
            depth = len([p for p in path_parts if p])
            
            # Base weight inversely proportional to depth
            # Deeper pages get less weight
            weight = max(1, 10 - depth)
            
            # Adjust weight based on URL features
            if 'index' in url or url.endswith('/'):
                weight += 3  # Index pages are more likely to be visited
            if 'category' in url or 'tag' in url:
                weight += 2  # Category pages are common navigation points
            if 'product' in url or 'item' in url:
                weight += 1  # Product pages are often targets
                
            self.url_weights[url] = weight
    
    def _choose_next_url(self):
        """
        Choose the next URL to visit based on a variety of factors
        
        Returns:
            str: URL to visit next
        """
        # Different strategies for choosing the next URL
        strategy = random.choices(
            ['weighted', 'recency', 'backtracking', 'popular', 'random'],
            weights=[0.4, 0.2, 0.2, 0.1, 0.1]
        )[0]
        
        self.logger.info(f"Using {strategy} selection strategy")
        
        if strategy == 'weighted' and self.url_list and self.url_weights:
            # Use weighted selection based on pre-calculated weights
            urls = list(self.url_weights.keys())
            weights = list(self.url_weights.values())
            return random.choices(urls, weights=weights)[0]
            
        elif strategy == 'recency' and self.urls_visited:
            # Choose from recently visited URLs (simulates browsing related content)
            recent_urls = [v['url'] for v in self.urls_visited[-5:]]
            # Extract new links from these recent pages
            potential_urls = []
            for url in recent_urls:
                links = self._extract_links(url)
                potential_urls.extend(links)
            
            if potential_urls:
                return random.choice(potential_urls)
                
        elif strategy == 'backtracking' and self.current_path:
            # Go back to a previous page (simulate using browser back button)
            self.logger.info("Backtracking to previous page")
            if len(self.current_path) > 1:
                self.current_path.pop()  # Remove current page
                return self.current_path[-1]  # Return previous page
                
        elif strategy == 'popular' and self.url_list:
            # Choose from the most popular pages in our pre-discovered list
            # This simulates popular content being more likely to be visited
            # For now, we'll use a simple heuristic based on the URL structure
            index_pages = [url for url in self.url_list if url.endswith('/') or 'index' in url]
            if index_pages:
                return random.choice(index_pages)
        
        # Default to random selection
        if self.url_list:
            # Use pre-discovered URLs if available
            return random.choice(self.url_list)
        elif self.urls_visited:
            # Extract links from the last visited URL
            last_url = self.urls_visited[-1]['url']
            links = self._extract_links(last_url)
            
            if links:
                return random.choice(links)
                
        # If all else fails, return to base URL
        return self.base_url
            
    def _visit_url(self, url):
        """
        Visit a specific URL and record the visit
        
        Args:
            url (str): URL to visit
            
        Returns:
            bool: Success status
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
            
            # Make the request
            self.logger.info(f"Visiting URL: {url}")
            
            # Send a preparatory status update
            self.socketio.emit('visit_preparing', {
                'session_id': self.session_id,
                'url': url,
                'using_proxy': False  # Always false since we're not using proxies
            })
            
            response = self.session.get(
                url, 
                headers=headers, 
                timeout=30,
                allow_redirects=True
            )
            
            # Record the visit
            visit_data = {
                'url': response.url,  # Use final URL after redirects
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'status_code': response.status_code,
                'using_proxy': False,  # Always false since we're not using proxies
                'content_type': response.headers.get('Content-Type', 'unknown'),
                'page_title': self._extract_title(response.text) if 'text/html' in response.headers.get('Content-Type', '') else None
            }
            
            # Update browsing path
            self.current_path.append(url)
            if len(self.current_path) > 10:  # Limit path history
                self.current_path = self.current_path[-10:]
                
            # Update visit history counter
            self.visit_history[url] += 1
            
            self.urls_visited.append(visit_data)
            self.visits_completed += 1
            
            # Discover new links if needed
            if not self.url_list or (self.visits_completed % 10 == 0 and len(self.url_list) < 100):
                new_links = self._extract_links(url)
                for link in new_links:
                    if link not in self.url_list:
                        self.url_list.append(link)
                        # Assign a default weight
                        self.url_weights[link] = 5
            
            # Emit update to connected clients
            self.socketio.emit('visit_update', {
                'session_id': self.session_id,
                'visit': visit_data,
                'visits_completed': self.visits_completed,
                'max_visits': self.max_visits,
                'discovered_urls_count': len(self.url_list)
            })
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error visiting URL {url}: {str(e)}")
            # Emit error update to connected clients
            self.socketio.emit('visit_error', {
                'session_id': self.session_id,
                'url': url,
                'error': str(e)
            })
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error visiting URL {url}: {str(e)}")
            return False
            
    def _extract_title(self, html_content):
        """Extract the page title from HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                return title_tag.text.strip()
        except:
            pass
        return "No title"
            
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
            
            # Make request
            response = self.session.get(
                url, 
                headers=headers, 
                timeout=15
            )
            
            if response.status_code != 200:
                self.logger.warning(f"Got status code {response.status_code} when extracting links from {url}")
                return []
                
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
                    # Filter out non-webpage links (e.g., images, pdfs)
                    if not any(absolute_url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.zip']):
                        # Remove fragments from URLs
                        clean_url = absolute_url.split('#')[0]
                        if clean_url not in links:
                            links.append(clean_url)
            
            self.logger.info(f"Found {len(links)} links on {url}")
            
            # Emit an update about discovered links
            if links:
                self.socketio.emit('links_discovered', {
                    'session_id': self.session_id,
                    'source_url': url,
                    'link_count': len(links)
                })
                
            return links
            
        except Exception as e:
            self.logger.error(f"Error extracting links from {url}: {str(e)}")
            return []