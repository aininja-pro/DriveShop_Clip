"""
Enhanced Crawler Manager with 5-Tier Escalation System

Tier 1: Google Search API (find specific articles from index pages)
Tier 2: ScrapingBee API (JS-heavy domains) 
Tier 3: Basic/Enhanced HTTP (scrapy/requests)
Tier 4: RSS Feed (if available)
Tier 5: Playwright Headless (last resort)
"""

import logging
from typing import Dict, Any, Optional, Tuple
import re
from urllib.parse import urlparse

from .config import API_SCRAPER_DOMAINS, GENERIC_INDEX_PATTERNS
from .google_search import GoogleSearchClient
from .scraping_bee import ScrapingBeeClient
from .cache_manager import CacheManager
from .crawler_manager import CrawlerManager  # Original crawler for tiers 3-5

logger = logging.getLogger(__name__)

class EnhancedCrawlerManager:
    """Enhanced crawler with 5-tier escalation including Google Search and ScrapingBee"""
    
    def __init__(self):
        self.google_search = GoogleSearchClient()
        self.scraping_bee = ScrapingBeeClient()
        self.cache_manager = CacheManager()
        self.original_crawler = CrawlerManager()  # For tiers 3-5
        
    def should_use_google_search(self, url: str, make: str, model: str) -> bool:
        """Determine if we should try Google Search first"""
        domain = urlparse(url).netloc.lower()
        
        # Always try Google Search for index/generic pages
        for pattern in GENERIC_INDEX_PATTERNS:
            if pattern in url.lower():
                logger.info(f"URL matches generic pattern '{pattern}' - will try Google Search first")
                return True
                
        # Try Google Search for domains known to have hard-to-crawl content
        if domain in API_SCRAPER_DOMAINS:
            logger.info(f"Domain {domain} in API scraper list - will try Google Search first")
            return True
            
        return False
        
    def should_use_scraping_bee(self, url: str) -> bool:
        """Determine if we should use ScrapingBee API"""
        if not url:
            return False
            
        try:
            original_domain = urlparse(url).netloc.lower()
            domain = original_domain
            
            # Strip www. prefix for comparison (this was the bug!)
            if domain.startswith('www.'):
                domain = domain[4:]
                
            should_use = domain in API_SCRAPER_DOMAINS
            logger.debug(f"ScrapingBee check: {original_domain} -> {domain} -> use_bee={should_use}")
            
            return should_use
            
        except Exception as e:
            logger.error(f"Error parsing URL {url}: {e}")
            return False
        
    def crawl_url(self, url: str, make: str, model: str, person_name: str = "") -> Dict[str, Any]:
        """
        Enhanced crawling with 5-tier escalation
        
        Returns: {
            'success': bool,
            'content': str,
            'title': str,
            'url': str,  # may be different if Google Search found specific article
            'tier_used': str,
            'cached': bool,
            'error': str (if success=False)
        }
        """
        
        # Check cache first
        domain = urlparse(url).netloc.lower()
        
        cached_result = self.cache_manager.get_cached_result(
            person_id=person_name or "unknown",
            domain=domain,
            make=make,
            model=model
        )
        
        if cached_result:
            logger.info(f"Cache hit for {person_name}/{domain}/{make}/{model}")
            return {
                'success': True,
                'content': cached_result['content'],
                'title': 'Cached Result',
                'url': cached_result['url'],
                'tier_used': 'Cache Hit',
                'cached': True
            }
            
        # Tier 1: Google Search (for index pages or hard-to-crawl domains)
        if self.should_use_google_search(url, make, model):
            logger.info(f"Tier 1: Trying Google Search to find specific article for {make} {model}")
            
            # Extract domain from URL
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower().replace('www.', '')
            
            # Try to find a specific article using Google Search
            specific_url = self.google_search.search_for_article(
                domain=domain,
                make=make,
                model=model,
                year=None,  # Don't hardcode year - let it use the model data
                author=person_name  # Pass the author name from the "To" field!
            )
            
            if specific_url and specific_url != url:
                logger.info(f"Tier 1 Success: Google Search found specific article: {specific_url}")
                
                # Now crawl the specific article we found
                article_result = self._crawl_specific_url(specific_url, make, model)
                
                if article_result['success']:
                    result = article_result.copy()
                    result.update({
                        'tier_used': 'Tier 1: Google Search',
                        'cached': False
                    })
                    # Cache the result
                    self.cache_manager.store_result(
                        person_id=person_name or "unknown",
                        domain=domain,
                        make=make,
                        model=model,
                        url=specific_url,
                        content=article_result['content']
                    )
                    return result
                    
        # Tier 2: ScrapingBee API
        if self.should_use_scraping_bee(url):
            logger.info(f"Tier 2: Trying ScrapingBee for {url}")
            
            bee_content = self.scraping_bee.scrape_url(url)
            if bee_content:
                logger.info(f"Tier 2 Success: ScrapingBee crawled {url}")
                result = {
                    'success': True,
                    'content': bee_content,
                    'title': 'ScrapingBee Result',  # ScrapingBee doesn't extract titles
                    'url': url,
                    'tier_used': 'Tier 2: ScrapingBee',
                    'cached': False
                }
                # Cache the result
                self.cache_manager.store_result(
                    person_id=person_name or "unknown",
                    domain=domain,
                    make=make,
                    model=model,
                    url=url,
                    content=bee_content
                )
                return result
                
        # Tiers 3-5: Fall back to original crawler (HTTP + RSS + Playwright)
        logger.info(f"Tiers 3-5: Using original crawler for {url}")
        
        # Original crawler returns (content, title, error, actual_url)
        content, title, error, actual_url = self.original_crawler.crawl(
            url=url,
            allow_escalation=True,
            wait_time=15,
            vehicle_make=make,
            vehicle_model=model
        )
        
        if content and not error:
            result = {
                'success': True,
                'content': content,
                'title': title or 'Unknown Title',
                'url': actual_url or url,
                'tier_used': f"Tier 3-5: Original Crawler",
                'cached': False
            }
            # Cache the result
            self.cache_manager.store_result(
                person_id=person_name or "unknown",
                domain=domain,
                make=make,
                model=model,
                url=actual_url or url,
                content=content
            )
            return result
            
        # All tiers failed
        return {
            'success': False,
            'content': '',
            'title': '',
            'url': url,
            'tier_used': 'All Tiers Failed',
            'cached': False,
            'error': 'All escalation tiers failed'
        }
        
    def _crawl_specific_url(self, url: str, make: str, model: str) -> Dict[str, Any]:
        """Crawl a specific URL using ScrapingBee or original crawler"""
        
        # Try ScrapingBee first for API domains
        if self.should_use_scraping_bee(url):
            logger.info(f"Using ScrapingBee to crawl specific URL: {url}")
            bee_content = self.scraping_bee.scrape_url(url)
            if bee_content:
                logger.info(f"ScrapingBee success for specific URL: {url}")
                return {
                    'success': True,
                    'content': bee_content,
                    'title': 'ScrapingBee Result',
                    'url': url
                }
            else:
                logger.warning(f"ScrapingBee failed for specific URL: {url}, falling back to original crawler")
            
        # Otherwise use original crawler - it returns (content, title, error, actual_url)
        logger.info(f"Using original crawler for specific URL: {url}")
        content, title, error, actual_url = self.original_crawler.crawl(
            url, 
            allow_escalation=True, 
            wait_time=10,
            vehicle_make=make,
            vehicle_model=model
        )
        
        if content and not error:
            return {
                'success': True,
                'content': content,
                'title': title or 'Unknown Title',
                'url': actual_url or url
            }
        else:
            return {
                'success': False,
                'content': '',
                'title': '',
                'url': url,
                'error': error or 'Failed to crawl specific URL'
            }
        
    def close(self):
        """Clean up resources"""
        try:
            # Close the original crawler (handles Playwright browsers)
            if hasattr(self.original_crawler, 'close'):
                self.original_crawler.close()
                logger.info("Closed original crawler resources")
        except Exception as e:
            logger.warning(f"Error closing crawler resources: {e}")
            
        # Note: CacheManager uses SQLite context managers, no explicit close needed
        # Note: ScrapingBee and Google Search are HTTP-based APIs, no cleanup needed
        logger.info("Enhanced crawler manager cleanup completed") 