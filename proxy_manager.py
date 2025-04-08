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
    'proxies': [],
    'failed_attempts': 0,  # Track failed connection attempts
    'proxies_disabled': False  # Flag to disable proxies completely
}

def get_random_proxy():
    """
    Get a random working proxy, or None to use direct connection
    
    Returns:
        str: Proxy in format "http://ip:port" or None to use direct connection
    """
    # Check if proxies are disabled via environment variable or after too many failures
    if os.environ.get('DISABLE_PROXIES', 'false').lower() == 'true' or proxy_cache['proxies_disabled']:
        if proxy_cache['proxies_disabled']:
            logger.info("Proxies are disabled due to multiple connection failures. Using direct connection.")
        else:
            logger.info("Proxy usage is disabled by environment variable. Using direct connection.")
        return None
    
    # Check if we need to refresh the proxy list (every 30 minutes)
    now = datetime.now()
    
    if (proxy_cache['last_updated'] is None or 
        now - proxy_cache['last_updated'] > timedelta(minutes=30) or
        not proxy_cache['proxies']):
        refresh_proxy_list()
    
    # Return a random proxy if we have any, otherwise increment failure count
    if proxy_cache['proxies']:
        proxy = random.choice(proxy_cache['proxies'])
        logger.info(f"Using proxy: {proxy}")
        return proxy
    else:
        # Increment failure counter
        proxy_cache['failed_attempts'] += 1
        logger.warning(f"No working proxies found (attempt {proxy_cache['failed_attempts']} of 3). Using direct connection.")
        
        # If we've had 3 failures, disable proxies completely
        if proxy_cache['failed_attempts'] >= 3:
            proxy_cache['proxies_disabled'] = True
            logger.warning("Proxy connection failed 3 times. Disabling proxies completely for this session.")
        
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
            proxy = proxy.strip()
            if is_proxy_working(proxy):
                proxies.append(proxy)
    
    # If we don't have environment proxies, try to fetch from free proxy lists
    # But only if fetching free proxies is enabled
    if not proxies and os.environ.get('FETCH_FREE_PROXIES', 'true').lower() == 'true':
        proxies = fetch_free_proxies()
    
    # Update the cache
    proxy_cache['proxies'] = proxies
    proxy_cache['last_updated'] = datetime.now()
    
    if proxies:
        logger.info(f"Proxy list refreshed. Found {len(proxies)} working proxies.")
        # Reset failed attempts counter if we found working proxies
        proxy_cache['failed_attempts'] = 0
    else:
        logger.warning("No working proxies found. Will use direct connection.")

def fetch_free_proxies():
    """
    Fetch proxies from free proxy lists
    
    Returns:
        list: List of working proxies
    """
    working_proxies = []
    max_proxies_to_check = 20  # Limit how many we check to avoid long delays
    proxies_checked = 0
    
    try:
        # Try to get from public API (example only - may not work)
        response = requests.get('https://www.proxy-list.download/api/v1/get?type=http', timeout=10)
        if response.status_code == 200:
            potential_proxies = response.text.strip().split('\r\n')
            
            for proxy in potential_proxies:
                if not proxy:  # Skip empty lines
                    continue
                    
                proxy_url = f"http://{proxy}"
                logger.info(f"Testing proxy: {proxy_url}")
                
                proxies_checked += 1
                if is_proxy_working(proxy_url):
                    working_proxies.append(proxy_url)
                    logger.info(f"Found working proxy: {proxy_url}")
                    
                    # Limit to 5 working proxies to avoid taking too long
                    if len(working_proxies) >= 5:
                        break
                        
                # Stop checking after max_proxies_to_check
                if proxies_checked >= max_proxies_to_check:
                    break
    except Exception as e:
        logger.warning(f"Error fetching proxies: {str(e)}")
    
    return working_proxies

def is_proxy_working(proxy_url):
    """
    Test if a proxy is working by making a test request
    
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
        
        # Shorter timeout to avoid long delays
        response = requests.get(
            'https://httpbin.org/ip', 
            proxies=proxies, 
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"Proxy {proxy_url} is working")
            return True
        else:
            logger.info(f"Proxy {proxy_url} returned status code {response.status_code}")
            return False
    except Exception as e:
        logger.info(f"Proxy {proxy_url} is not working: {str(e)}")
        return False

def reset_proxy_failures():
    """Reset the failure counter and re-enable proxies"""
    proxy_cache['failed_attempts'] = 0
    proxy_cache['proxies_disabled'] = False
    logger.info("Proxy failure counter reset. Proxies re-enabled.")