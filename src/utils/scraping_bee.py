import os
import requests
import logging
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class ScrapingBeeClient:
    """ScrapingBee API client for scraping JS-heavy websites"""
    
    def __init__(self):
        self.api_key = os.environ.get('SCRAPINGBEE_API_KEY')
        self.base_url = "https://app.scrapingbee.com/api/v1/"
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        if not self.api_key:
            logger.warning("SCRAPINGBEE_API_KEY not found in environment variables")
    
    def scrape_url(self, url: str, render_js: bool = True, premium_proxy: bool = False) -> Optional[str]:
        """
        Scrape a URL using ScrapingBee API.
        
        Args:
            url: URL to scrape
            render_js: Whether to render JavaScript (recommended for most sites)
            premium_proxy: Whether to use premium proxies (costs more credits)
            
        Returns:
            HTML content as string or None if failed
        """
        if not self.api_key:
            logger.error("ScrapingBee API key not configured")
            return None
        
        if not url:
            logger.error("No URL provided to scrape")
            return None
        
        # Prepare API parameters
        params = {
            'api_key': self.api_key,
            'url': url,
            'render_js': str(render_js).lower(),
            'premium_proxy': str(premium_proxy).lower(),
            'country_code': 'us',  # Use US proxies for automotive sites
            'wait': 3000,  # Wait 3 seconds for JS to load
            'wait_for': '#main, article, .content',  # Wait for content elements
            'block_ads': 'true',  # Block ads to speed up loading
            'block_resources': 'false'  # Don't block CSS/JS as we need rendered content
        }
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"ScrapingBee attempt {attempt + 1}/{self.max_retries} for {url}")
                
                response = requests.get(
                    self.base_url,
                    params=params,
                    timeout=30  # 30 second timeout
                )
                
                # Check API response
                if response.status_code == 200:
                    content = response.text
                    if content and len(content) > 1000:  # Ensure we got meaningful content
                        logger.info(f"Successfully scraped {url} via ScrapingBee ({len(content)} chars)")
                        return content
                    else:
                        logger.warning(f"ScrapingBee returned minimal content for {url} ({len(content) if content else 0} chars)")
                        
                elif response.status_code == 422:
                    logger.error(f"ScrapingBee validation error for {url}: {response.text}")
                    return None  # Don't retry validation errors
                    
                elif response.status_code == 429:
                    logger.warning(f"ScrapingBee rate limit reached, waiting before retry...")
                    time.sleep(self.retry_delay * 2)  # Longer wait for rate limits
                    
                else:
                    logger.warning(f"ScrapingBee HTTP {response.status_code} for {url}: {response.text}")
                
            except requests.exceptions.Timeout:
                logger.warning(f"ScrapingBee timeout for {url} on attempt {attempt + 1}")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"ScrapingBee request error for {url}: {e}")
                
            except Exception as e:
                logger.error(f"Unexpected ScrapingBee error for {url}: {e}")
            
            # Wait before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        
        logger.error(f"ScrapingBee failed after {self.max_retries} attempts for {url}")
        return None
    
    def check_api_status(self) -> Dict[str, Any]:
        """
        Check ScrapingBee API status and remaining credits.
        
        Returns:
            Dict with status information
        """
        if not self.api_key:
            return {"error": "API key not configured"}
        
        try:
            # Make a minimal request to check status
            params = {
                'api_key': self.api_key,
                'url': 'https://httpbin.org/status/200',  # Simple test URL
                'render_js': 'false'
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            
            status_info = {
                'status_code': response.status_code,
                'api_credits_remaining': response.headers.get('Spb-Remaining-Requests', 'Unknown'),
                'api_credits_used': response.headers.get('Spb-Used-Requests', 'Unknown'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                logger.info(f"ScrapingBee API working. Credits remaining: {status_info['api_credits_remaining']}")
            else:
                logger.warning(f"ScrapingBee API issue: HTTP {response.status_code}")
            
            return status_info
            
        except Exception as e:
            logger.error(f"Error checking ScrapingBee API status: {e}")
            return {"error": str(e)}

# Configuration for domains that should use ScrapingBee
API_SCRAPER_DOMAINS = [
    "motortrend.com",
    "caranddriver.com", 
    "roadandtrack.com",
    "jalopnik.com",
    "thedrive.com"
]

def should_use_scraping_bee(url: str) -> bool:
    """
    Check if a URL should be scraped using ScrapingBee based on domain.
    
    Args:
        url: URL to check
        
    Returns:
        True if should use ScrapingBee, False otherwise
    """
    if not url:
        return False
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Strip www. prefix for comparison
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain in API_SCRAPER_DOMAINS
        
    except Exception as e:
        logger.error(f"Error parsing URL {url}: {e}")
        return False

# Convenience function for easy importing
def scrape_with_bee(url: str, render_js: bool = True) -> Optional[str]:
    """
    Convenience function to scrape a URL with ScrapingBee.
    
    Args:
        url: URL to scrape
        render_js: Whether to render JavaScript
        
    Returns:
        HTML content or None
    """
    client = ScrapingBeeClient()
    return client.scrape_url(url, render_js=render_js) 