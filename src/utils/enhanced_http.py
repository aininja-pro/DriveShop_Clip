"""
Enhanced HTTP Client with Browser-like Headers

This module provides HTTP requests that masquerade as real browser traffic,
bypassing basic bot detection while being fast and free.
"""

import requests
import logging
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class EnhancedHTTPClient:
    """HTTP client with enhanced headers to bypass bot detection"""
    
    def __init__(self):
        self.session = requests.Session()
        self.max_retries = 2
        self.retry_delay = 1  # seconds
        
        # Browser-like headers that worked in our test
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        
        # Update session headers
        self.session.headers.update(self.default_headers)
    
    def fetch_url(self, url: str, timeout: int = 10) -> Optional[str]:
        """
        Fetch URL content using enhanced headers.
        
        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            
        Returns:
            HTML content as string or None if failed
        """
        if not url:
            logger.error("No URL provided to fetch")
            return None
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Enhanced HTTP attempt {attempt + 1}/{self.max_retries} for {url}")
                
                start_time = time.time()
                response = self.session.get(url, timeout=timeout)
                fetch_time = time.time() - start_time
                
                # Check response status
                if response.status_code == 200:
                    content = response.text
                    if content and len(content) > 1000:  # Ensure we got meaningful content
                        logger.info(f"Enhanced HTTP success for {url} ({len(content):,} chars in {fetch_time:.2f}s)")
                        return content
                    else:
                        logger.warning(f"Enhanced HTTP returned minimal content for {url} ({len(content) if content else 0} chars)")
                        
                elif response.status_code == 403:
                    logger.warning(f"Enhanced HTTP 403 Forbidden for {url} - headers not sufficient")
                    return None  # Don't retry 403s - escalate to ScrapingBee
                    
                elif response.status_code in [429, 503, 504]:
                    logger.warning(f"Enhanced HTTP {response.status_code} for {url} - rate limited/server issues")
                    # These might be temporary - allow retry
                    
                else:
                    logger.warning(f"Enhanced HTTP {response.status_code} for {url}")
                
            except requests.exceptions.Timeout:
                logger.warning(f"Enhanced HTTP timeout for {url} on attempt {attempt + 1}")
                
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Enhanced HTTP connection error for {url}: {e}")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Enhanced HTTP request error for {url}: {e}")
                
            except Exception as e:
                logger.error(f"Unexpected Enhanced HTTP error for {url}: {e}")
            
            # Wait before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        
        logger.error(f"Enhanced HTTP failed after {self.max_retries} attempts for {url}")
        return None
    
    def is_content_relevant(self, content: str, make: str, model: str) -> bool:
        """
        Quick check if content mentions the vehicle.
        
        Args:
            content: HTML content
            make: Vehicle make (e.g., "Audi")
            model: Vehicle model (e.g., "Q6 e-tron")
            
        Returns:
            True if content appears relevant
        """
        if not content or not make or not model:
            return False
            
        content_lower = content.lower()
        make_lower = make.lower()
        model_lower = model.lower()
        
        # Basic relevance check
        has_make = make_lower in content_lower
        has_model = any(part.lower() in content_lower for part in model.split())
        
        return has_make and has_model
    
    def close(self):
        """Clean up session"""
        try:
            self.session.close()
            logger.debug("Enhanced HTTP session closed")
        except Exception as e:
            logger.warning(f"Error closing Enhanced HTTP session: {e}")

# Convenience function for easy importing
def fetch_with_enhanced_http(url: str, timeout: int = 10) -> Optional[str]:
    """
    Convenience function to fetch a URL with enhanced headers.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        HTML content or None
    """
    client = EnhancedHTTPClient()
    try:
        return client.fetch_url(url, timeout)
    finally:
        client.close() 