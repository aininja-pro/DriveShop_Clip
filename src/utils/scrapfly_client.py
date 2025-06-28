#!/usr/bin/env python3
"""
ScrapFly client for web scraping with anti-bot protection.
ScrapFly provides rotating proxies, browser rendering, and anti-detection features.
"""

import os
import time
import requests
from typing import Optional, Tuple
from scrapfly import ScrapflyClient, ScrapeConfig
from src.utils.logger import logger


class ScrapFlyWebCrawler:
    """ScrapFly-powered web crawler with anti-bot protection and proper rate limiting"""
    
    def __init__(self):
        """Initialize ScrapFly client with rate limiting"""
        self.api_key = os.environ.get('SCRAPFLY_API_KEY')
        
        # Rate limiting and circuit breaker state
        self.last_request_time = 0
        self.min_delay_between_requests = 2.0  # Minimum 2 seconds between requests
        self.circuit_breaker_until = 0  # Timestamp when circuit breaker expires
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5  # Circuit breaker threshold
        
        if not self.api_key:
            logger.warning("SCRAPFLY_API_KEY not found in environment variables")
            self.client = None
        else:
            self.client = ScrapflyClient(key=self.api_key)
            logger.info("✅ ScrapFly client initialized successfully with rate limiting")
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is currently open (blocking requests)"""
        if self.circuit_breaker_until > time.time():
            remaining = int(self.circuit_breaker_until - time.time())
            logger.warning(f"🚫 ScrapFly circuit breaker OPEN - {remaining}s remaining")
            return True
        return False
    
    def _enforce_rate_limit(self):
        """Enforce minimum delay between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay_between_requests:
            sleep_time = self.min_delay_between_requests - time_since_last
            logger.info(f"⏱️ Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _handle_rate_limit_response(self, error_message: str) -> Optional[int]:
        """
        Parse rate limit error and extract retry-after time
        Returns: retry_after_seconds (None if not a rate limit error)
        """
        if "429" in error_message and "throttled" in error_message.lower():
            # Try to extract retry-after from error message
            # Example: "Retry After". Make sure to fix your application, this can be seen as DDOS
            
            # Look for common patterns in ScrapFly throttle messages
            retry_after = 60  # Default to 60 seconds if we can't parse
            
            # Try to extract number from error message
            import re
            numbers = re.findall(r'(\d+)', error_message)
            if numbers:
                # Take the largest number as it's likely the retry-after
                retry_after = max(int(num) for num in numbers)
                retry_after = min(retry_after, 300)  # Cap at 5 minutes
            
            logger.warning(f"⚠️ ScrapFly rate limited - will retry after {retry_after}s")
            return retry_after
        
        return None
    
    def _open_circuit_breaker(self, retry_after_seconds: int = 300):
        """Open circuit breaker to prevent further requests"""
        self.circuit_breaker_until = time.time() + retry_after_seconds
        self.consecutive_failures += 1
        
        logger.error(f"🚫 Opening ScrapFly circuit breaker for {retry_after_seconds}s (failure #{self.consecutive_failures})")
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker after successful request"""
        if self.consecutive_failures > 0:
            logger.info("✅ ScrapFly circuit breaker RESET - successful request")
            self.consecutive_failures = 0
            self.circuit_breaker_until = 0

    def crawl(self, url: str, render_js: bool = False, use_stealth: bool = True, country: str = "US") -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Crawl a URL using ScrapFly with anti-bot protection and rate limiting
        
        Args:
            url: URL to crawl
            render_js: Whether to render JavaScript (costs more credits)
            use_stealth: Whether to use anti-detection features
            country: Country for proxy location
            
        Returns:
            Tuple of (content, title, error)
        """
        if not self.client:
            logger.error("ScrapFly client not initialized - missing API key")
            return None, None, "ScrapFly API key not configured"
        
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            return None, None, "ScrapFly circuit breaker is open - too many failures"
        
        # Enforce rate limiting
        self._enforce_rate_limit()
        
        try:
            logger.info(f"🕷️ ScrapFly crawling: {url}")
            logger.info(f"   - JavaScript rendering: {'ON' if render_js else 'OFF'}")
            logger.info(f"   - Stealth mode: {'ON' if use_stealth else 'OFF'}")
            logger.info(f"   - Proxy country: {country}")
            
            # Configure ScrapFly request (minimal configuration)
            config_options = ScrapeConfig(
                url=url,
                # Basic settings
                country=country,
                render_js=render_js,
                # Anti-scraping protection
                asp=use_stealth,
                # ScrapFly handles timeouts automatically when retry is enabled
                # Custom timeout not allowed with retry enabled
            )
            
            # Execute the scrape
            result = self.client.scrape(config_options)
            
            if result.success:
                content = result.content
                
                # Extract title from HTML
                title = self._extract_title(content)
                
                logger.info(f"✅ ScrapFly successfully crawled {url}")
                logger.info(f"   - Content length: {len(content)} chars")
                logger.info(f"   - Title: {title[:50] + '...' if title and len(title) > 50 else title}")
                logger.info(f"   - Credits used: {result.cost}")
                
                # Reset circuit breaker on success
                self._reset_circuit_breaker()
                
                return content, title, None
            else:
                error_msg = f"ScrapFly failed: {result.error_message}"
                logger.error(f"❌ {error_msg}")
                
                # Check if this is a rate limit error
                retry_after = self._handle_rate_limit_response(result.error_message)
                if retry_after:
                    self._open_circuit_breaker(retry_after)
                
                return None, None, error_msg
                
        except Exception as e:
            error_msg = f"ScrapFly exception: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            # Check if this is a rate limit error
            retry_after = self._handle_rate_limit_response(str(e))
            if retry_after:
                self._open_circuit_breaker(retry_after)
            elif self.consecutive_failures >= self.max_consecutive_failures:
                # Too many consecutive failures - open circuit breaker
                self._open_circuit_breaker(180)  # 3 minutes
            
            return None, None, error_msg
    
    def crawl_with_fallback(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Crawl with progressive fallback strategy BUT with proper rate limiting:
        1. Basic scrape (fast, cheap)
        2. With JavaScript rendering (slower, more expensive) - ONLY if first fails
        
        Removed the third attempt to reduce API calls and prevent rate limiting
        """
        logger.info(f"🕷️ ScrapFly progressive crawl starting for: {url}")
        
        # Check circuit breaker before starting
        if self._is_circuit_breaker_open():
            return None, None, "ScrapFly circuit breaker is open - too many failures"
        
        # Attempt 1: Basic scrape (no JS, basic stealth)
        logger.info("🔄 Attempt 1: Basic scrape")
        content, title, error = self.crawl(url, render_js=False, use_stealth=True)
        if content and len(content) > 1000:
            logger.info("✅ Basic scrape successful")
            return content, title, error
        
        # Check circuit breaker again before second attempt
        if self._is_circuit_breaker_open():
            return None, None, "ScrapFly circuit breaker opened during crawl"
        
        # Attempt 2: With JavaScript rendering (ONLY if basic failed)
        logger.info("🔄 Attempt 2: With JavaScript rendering")
        time.sleep(3)  # Longer pause between attempts to respect rate limits
        content, title, error = self.crawl(url, render_js=True, use_stealth=True)
        
        if content and len(content) > 1000:
            logger.info("✅ JavaScript rendering successful")
        else:
            logger.warning("❌ All ScrapFly attempts failed")
        
        return content, title, error
    
    def _extract_title(self, html_content: str) -> Optional[str]:
        """Extract title from HTML content"""
        try:
            import re
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                # Clean up title (remove extra whitespace, decode HTML entities)
                title = ' '.join(title.split())
                return title
        except Exception as e:
            logger.warning(f"Error extracting title: {e}")
        
        return None
    
    def get_account_info(self) -> dict:
        """Get ScrapFly account information (credits, usage, etc.)"""
        if not self.client:
            return {"error": "ScrapFly client not initialized"}
        
        try:
            # This would require the ScrapFly SDK to support account info
            # For now, return basic info
            return {
                "status": "connected",
                "api_key_configured": bool(self.api_key),
                "client_initialized": bool(self.client)
            }
        except Exception as e:
            return {"error": str(e)}


# Convenience function for easy use
def scrapfly_crawl(url: str, render_js: bool = False) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Convenience function to crawl a single URL with ScrapFly
    
    Args:
        url: URL to crawl
        render_js: Whether to render JavaScript
        
    Returns:
        Tuple of (content, title, error)
    """
    crawler = ScrapFlyWebCrawler()
    return crawler.crawl(url, render_js=render_js)


# Convenience function with progressive fallback
def scrapfly_crawl_with_fallback(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Convenience function to crawl with progressive fallback
    
    Args:
        url: URL to crawl
        
    Returns:
        Tuple of (content, title, error)
    """
    crawler = ScrapFlyWebCrawler()
    return crawler.crawl_with_fallback(url) 