import requests
import validators
from urllib.parse import urlparse
import time
import random
from user_agents import get_random_user_agent

def validate_url(url):
    """
    Validate if a URL is properly formatted and accessible
    
    Args:
        url (str): The URL to validate
        
    Returns:
        tuple: (is_valid, message)
    """
    # Check if URL is properly formatted
    if not validators.url(url):
        return False, "Invalid URL format. Please enter a valid URL including http:// or https://"
    
    # Check if URL has a valid scheme
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ['http', 'https']:
        return False, "Only HTTP and HTTPS protocols are supported"
    
    # Try to access the URL to verify it's active
    try:
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Add random delay to mimic human behavior
        time.sleep(random.uniform(0.5, 1.5))
        
        response = requests.head(
            url, 
            headers=headers, 
            timeout=10,
            allow_redirects=True
        )
        
        # Check for success status code
        if response.status_code >= 200 and response.status_code < 300:
            return True, "URL is valid and accessible"
        elif response.status_code >= 300 and response.status_code < 400:
            return True, "URL is valid but redirects to another location"
        else:
            return False, f"URL returned status code {response.status_code}"
            
    except requests.exceptions.ConnectTimeout:
        return False, "Connection timed out. The website might be down or too slow."
    except requests.exceptions.ConnectionError:
        return False, "Failed to establish a connection. The website might be down."
    except requests.exceptions.ReadTimeout:
        return False, "Request timed out while reading the response."
    except requests.exceptions.TooManyRedirects:
        return False, "Too many redirects. The URL might be in a redirect loop."
    except Exception as e:
        return False, f"An error occurred: {str(e)}"