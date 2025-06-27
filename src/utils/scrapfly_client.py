#!/usr/bin/env python3
"""
ScrapFly client for web scraping with anti-bot protection.
ScrapFly provides rotating proxies, browser rendering, and anti-detection features.
"""

import os
import time
from typing import Optional, Tuple
from scrapfly import ScrapflyClient, ScrapeConfig
from src.utils.logger import logger


class ScrapFlyWebCrawler:
    """ScrapFly-powered web crawler with anti-bot protection"""
    
    def __init__(self):
        """Initialize ScrapFly client"""
        self.api_key = os.environ.get('SCRAPFLY_API_KEY')
        
        if not self.api_key:
            logger.warning("SCRAPFLY_API_KEY not found in environment variables")
            self.client = None
        else:
            self.client = ScrapflyClient(key=self.api_key)
            logger.info("✅ ScrapFly client initialized successfully")
    
    def crawl(self, url: str, render_js: bool = False, use_stealth: bool = True, country: str = "US") -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Crawl a URL using ScrapFly with anti-bot protection
        
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
                
                return content, title, None
            else:
                error_msg = f"ScrapFly failed: {result.error_message}"
                logger.error(f"❌ {error_msg}")
                return None, None, error_msg
                
        except Exception as e:
            error_msg = f"ScrapFly exception: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return None, None, error_msg
    
    def crawl_with_fallback(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Crawl with progressive fallback strategy:
        1. Basic scrape (fast, cheap)
        2. With JavaScript rendering (slower, more expensive)
        3. With full stealth + JS (slowest, most expensive)
        """
        logger.info(f"🕷️ ScrapFly progressive crawl starting for: {url}")
        
        # Attempt 1: Basic scrape (no JS, basic stealth)
        logger.info("🔄 Attempt 1: Basic scrape")
        content, title, error = self.crawl(url, render_js=False, use_stealth=True)
        if content and len(content) > 1000:
            logger.info("✅ Basic scrape successful")
            return content, title, error
        
        # Attempt 2: With JavaScript rendering
        logger.info("🔄 Attempt 2: With JavaScript rendering")
        time.sleep(1)  # Brief pause between attempts
        content, title, error = self.crawl(url, render_js=True, use_stealth=True)
        if content and len(content) > 1000:
            logger.info("✅ JavaScript rendering successful")
            return content, title, error
        
        # Attempt 3: Full stealth mode with JS (most expensive)
        logger.info("🔄 Attempt 3: Full stealth + JavaScript")
        time.sleep(2)  # Longer pause for final attempt
        content, title, error = self.crawl(url, render_js=True, use_stealth=True, country="US")
        
        if content and len(content) > 1000:
            logger.info("✅ Full stealth mode successful")
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