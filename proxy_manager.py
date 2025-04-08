import requests
import random
import time
import os
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('proxy_manager')

# Cache for proxies
proxy_cache = {
    'last_updated': None,
    'proxies': []
}

def get_random_proxy():
    """
    Get a random working proxy
    
    Returns:
        str: Proxy in format "http://ip:port" or None if no proxies available
    """
    # Check if we need to refresh the proxy list (every 30 minutes)
    now = datetime.now()
    
    if (proxy_cache['last_updated'] is None or 
        now - proxy_cache['last_updated'] > timedelta(minutes=30) or
        not proxy_cache['proxies']):
        refresh_proxy_list()
    
    # Return a random proxy if we have any
    if proxy_cache['proxies']:
        return random.choice(proxy_cache['proxies'])
    
    return None

def refresh_proxy_list():
    """Refresh the list of working proxies"""
    logger.info("Refreshing proxy list...")
    
    proxies = []
    
    # Try to get proxies from environment variable first
    env_proxies = os.environ.get('PROXY_LIST', '')
    if env_proxies:
        proxy_list = env_proxies.split(',')
        for proxy in proxy_list:
            if is_proxy_working(proxy.strip()):
                proxies.append(proxy.strip())
    
    # If we don't have environment proxies, try to fetch from free proxy lists
    if not proxies:
        proxies = fetch_free_proxies()
    
    # Update the cache
    proxy_cache['proxies'] = proxies
    proxy_cache['last_updated'] = datetime.now()
    
    logger.info(f"Proxy list refreshed. Found {len(proxies)} working proxies.")

def fetch_free_proxies():
    """
    Fetch proxies from free proxy lists
    
    Returns:
        list: List of working proxies
    """
    working_proxies = []
    
    try:
        # Try to get from public API (example only - may not work)
        response = requests.get('https://www.proxy-list.download/api/v1/get?type=http', timeout=10)
        if response.status_code == 200:
            potential_proxies = response.text.strip().split('\r\n')
            for proxy in potential_proxies:
                proxy_url = f"http://{proxy}"
                if is_proxy_working(proxy_url):
                    working_proxies.append(proxy_url)
                    
                # Limit to 10 working proxies to avoid taking too long
                if len(working_proxies) >= 10:
                    break
    except Exception as e:
        logger.warning(f"Error fetching proxies: {str(e)}")
    
    return working_proxies

def is_proxy_working(proxy_url):
    """
    Test if a proxy is working
    
    Args:
        proxy_url (str): Proxy URL to test
        
    Returns:
        bool: True if proxy is working, False otherwise
    """
    try:
        # Test proxy with a request to a reliable service
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        response = requests.get(
            'https://httpbin.org/ip', 
            proxies=proxies, 
            timeout=5
        )
        
        return response.status_code == 200
    except:
        return False

# Provide a fallback method that doesn't use proxies
# This is important for environments like PythonAnywhere where proxies might not work
def use_proxies_if_available():
    """Determine whether to use proxies based on environment"""
    # Check for environment variable flag
    return os.environ.get('USE_PROXIES', 'false').lower() == 'true'