"""
Enhanced Crawler Manager with CLEAN 4-Tier Escalation System

Tier 1: Google Search API (find specific articles from index pages)
Tier 2: Enhanced HTTP (browser-like headers - FREE & FAST) + CONTENT QUALITY CHECK
Tier 3: ScrapingBee API (when Enhanced HTTP fails OR returns generic content)
Tier 4: Original Crawler (RSS + Playwright as last resort)

CLEAN AND SIMPLE: try each tier until one succeeds with QUALITY content.
"""

import logging
from typing import Dict, Any, Optional, Tuple
import re
from urllib.parse import urlparse

from .config import API_SCRAPER_DOMAINS, GENERIC_INDEX_PATTERNS
from .google_search import GoogleSearchClient
from .enhanced_http import EnhancedHTTPClient
from .scraping_bee import ScrapingBeeClient
from .cache_manager import CacheManager
from .crawler_manager import CrawlerManager  # Original crawler for tiers 4-5

logger = logging.getLogger(__name__)

class EnhancedCrawlerManager:
    """Enhanced crawler with clean 4-tier escalation including Google Search, Enhanced HTTP, and ScrapingBee"""
    
    def __init__(self):
        self.google_search = GoogleSearchClient()
        self.enhanced_http = EnhancedHTTPClient()
        self.scraping_bee = ScrapingBeeClient()
        self.cache_manager = CacheManager()
        self.original_crawler = CrawlerManager()  # For tiers 4-5
        
    def should_use_google_search(self, url: str, make: str, model: str) -> bool:
        """Determine if we should try Google Search first"""
        domain = urlparse(url).netloc.lower()
        parsed_url = urlparse(url)
        
        # Always try Google Search for homepage URLs (most generic)
        if not parsed_url.path or parsed_url.path == '/' or parsed_url.path == '':
            logger.info(f"URL is homepage ({url}) - will try Google Search first")
            return True
        
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
        """Determine if we should use ScrapingBee API (now Tier 3)"""
        if not url:
            return False
            
        try:
            original_domain = urlparse(url).netloc.lower()
            domain = original_domain
            
            # Strip www. prefix for comparison
            if domain.startswith('www.'):
                domain = domain[4:]
                
            should_use = domain in API_SCRAPER_DOMAINS
            logger.debug(f"ScrapingBee check: {original_domain} -> {domain} -> use_bee={should_use}")
            
            return should_use
            
        except Exception as e:
            logger.error(f"Error parsing URL {url}: {e}")
            return False
        
    def is_generic_content(self, content: str, url: str, make: str, model: str) -> bool:
        """Detect if content is a generic index page vs specific article - FIXED VERSION"""
        if not content:
            return True
            
        content_lower = content.lower()
        make_lower = make.lower() if make else ""
        model_lower = model.lower() if model else ""
        
        # STRICT CHECK: Both make AND model must be present for specific content
        # Handle empty make/model values properly - empty strings should be treated as "not found"
        make_found = bool(make_lower) and (make_lower in content_lower)
        model_found = bool(model_lower) and (model_lower in content_lower)
        
        # If NEITHER make nor model is found (or both are empty), it's definitely generic/wrong content
        if not make_found and not model_found:
            make_status = f"'{make}' found" if make_found else f"'{make}' NOT found"
            model_status = f"'{model}' found" if model_found else f"'{model}' NOT found"
            logger.info(f"WRONG CONTENT detected: {make_status}, {model_status} - ESCALATING")
            return True
            
        # If only ONE of make/model is found, we need to be extra careful
        # Check for strong indicators that this is actually about our specific vehicle
        if make_found != model_found:  # Only one of them found
            found_term = make if make_found else model
            missing_term = model if make_found else make
            
            # Look for the combined make+model phrase to be sure
            combined_phrases = []
            if make_lower and model_lower:
                combined_phrases = [
                    f'{make_lower} {model_lower}',
                    f'{model_lower} {make_lower}',
                    f'{make_lower}-{model_lower}',
                    f'{model_lower}-{make_lower}'
                ]
            
            combined_found = any(phrase in content_lower for phrase in combined_phrases) if combined_phrases else False
            
            if not combined_found:
                logger.info(f"SUSPICIOUS CONTENT: Only '{found_term}' found, '{missing_term}' missing, no combined phrase - ESCALATING")
                return True
        
        # If we get here, both make and model were found, or we found a combined phrase
        # Check for obvious generic page indicators that override specific content
        generic_indicators = [
            'car reviews</title>',
            'vehicle reviews</title>',
            'latest reviews',
            'recent reviews', 
            'all reviews',
            'review archive',
            'browse reviews'
        ]
        
        title_indicators_found = sum(1 for indicator in generic_indicators if indicator in content_lower)
        
        # If we have multiple generic indicators, it's probably still an index page
        if title_indicators_found >= 2:
            logger.info(f"GENERIC PAGE detected: {title_indicators_found} generic indicators found - ESCALATING")
            return True
            
        # Check URL patterns for obvious generic pages
        url_lower = url.lower()
        generic_url_patterns = [
            '/reviews/',
            '/car-reviews/', 
            '/vehicle-reviews/',
            '/review-archive/',
            '/latest-reviews/'
        ]
        
        is_generic_url = any(pattern in url_lower for pattern in generic_url_patterns)
        
        # If URL is clearly generic AND we don't have strong content indicators, escalate
        if is_generic_url:
            # Look for very specific indicators that this is actually a specific review
            specific_review_indicators = []
            if make_lower and model_lower:
                specific_review_indicators = [
                    f'{make_lower} {model_lower} review',
                    f'{model_lower} review',
                    f'test drive',
                    f'first drive', 
                    f'road test',
                    f'we drove',
                    f'our test'
                ]
            
            specific_indicators_found = sum(1 for indicator in specific_review_indicators if indicator in content_lower)
            
            if specific_indicators_found < 2:
                logger.info(f"GENERIC URL with weak content: only {specific_indicators_found} specific indicators - ESCALATING")
                return True
        
        # If we get here, content appears to be specifically about our make/model
        logger.info(f"SPECIFIC CONTENT confirmed: {make} {model} found with sufficient confidence")
        return False

    def crawl_url(self, url: str, make: str, model: str, person_name: str = "") -> Dict[str, Any]:
        """
        CLEAN 4-tier escalation system with CONTENT QUALITY DETECTION
        
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
            
        # Tier 1: Try Google Search first (ALWAYS)
        if True:  # Always try Google Search first - removed pattern matching for scalability
            logger.info(f"Tier 1: Trying Google Search to find specific article for {make} {model}")
            
            # Extract domain from URL
            parsed_url = urlparse(url)
            domain_clean = parsed_url.netloc.lower().replace('www.', '')
            
            # Try to find a specific article using Google Search
            specific_url = self.google_search.search_for_article(
                domain=domain_clean,
                make=make,
                model=model,
                year=None,
                author=person_name
            )
            
            if specific_url and specific_url != url:
                logger.info(f"Tier 1 Success: Google Search found specific article: {specific_url}")
                
                # Now crawl the specific article we found
                article_result = self._crawl_specific_url(specific_url, make, model)
                
                if article_result['success']:
                    result = article_result.copy()
                    result.update({
                        'tier_used': 'Tier 1: Google Search + ' + article_result.get('tier_used', 'Unknown'),
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
                    
        # Tier 2: Enhanced HTTP (fast and free) + QUALITY CHECK
        logger.info(f"Tier 2: Trying Enhanced HTTP for {url}")
        
        http_content = self.enhanced_http.fetch_url(url)
        if http_content:
            # Check if the content is actually useful or just generic
            if not self.is_generic_content(http_content, url, make, model):
                logger.info(f"Tier 2 Success: Enhanced HTTP found SPECIFIC content for {url}")
                result = {
                    'success': True,
                    'content': http_content,
                    'title': 'Enhanced HTTP Result',
                    'url': url,
                    'tier_used': 'Tier 2: Enhanced HTTP',
                    'cached': False
                }
                # Cache the result
                self.cache_manager.store_result(
                    person_id=person_name or "unknown",
                    domain=domain,
                    make=make,
                    model=model,
                    url=url,
                    content=http_content
                )
                return result
            else:
                logger.info(f"Tier 2: Enhanced HTTP got GENERIC content, escalating to ScrapingBee")
                
        # Tier 3: ScrapingBee (when Enhanced HTTP fails OR returns generic content)
        logger.info(f"Tier 3: Trying ScrapingBee for {url}")
        
        bee_content = self.scraping_bee.scrape_url(url)
        if bee_content:
            logger.info(f"Tier 3 Success: ScrapingBee crawled {url}")
            result = {
                'success': True,
                'content': bee_content,
                'title': 'ScrapingBee Result',
                'url': url,
                'tier_used': 'Tier 3: ScrapingBee',
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
                
        # Tier 4: Original crawler (RSS + Playwright as last resort)
        logger.info(f"Tier 4: Enhanced HTTP and ScrapingBee failed, using original crawler for {url}")
        
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
                'tier_used': f"Tier 4: Original Crawler",
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
        """Crawl a specific URL using OPTIMIZED tier order with CONTENT QUALITY CHECK"""
        
        # Tier 2: Try Enhanced HTTP first (FREE and FAST) + QUALITY CHECK
        logger.info(f"Trying Enhanced HTTP for specific URL: {url}")
        http_content = self.enhanced_http.fetch_url(url)
        if http_content:
            # Check if the content is actually useful or just generic
            if not self.is_generic_content(http_content, url, make, model):
                logger.info(f"Enhanced HTTP found SPECIFIC content for: {url}")
                return {
                    'success': True,
                    'content': http_content,
                    'title': 'Enhanced HTTP Result',
                    'url': url,
                    'tier_used': 'Enhanced HTTP'
                }
            else:
                logger.info(f"Enhanced HTTP got GENERIC content for {url}, escalating to ScrapingBee")
            
        # Tier 3: Try ScrapingBee for ALL URLs when Enhanced HTTP fails OR returns generic content
        logger.info(f"Trying ScrapingBee for specific URL: {url}")
        bee_content = self.scraping_bee.scrape_url(url)
        if bee_content:
            logger.info(f"ScrapingBee success for specific URL: {url}")
            return {
                'success': True,
                'content': bee_content,
                'title': 'ScrapingBee Result',
                'url': url,
                'tier_used': 'ScrapingBee'
            }
        else:
            logger.warning(f"ScrapingBee failed for specific URL: {url}, falling back to original crawler")
            
        # Tiers 4-5: Use original crawler as last resort
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
                'url': actual_url or url,
                'tier_used': 'Original Crawler'
            }
        else:
            return {
                'success': False,
                'content': '',
                'title': '',
                'url': url,
                'error': error or 'Failed to crawl specific URL',
                'tier_used': 'All Failed'
            }
        
    def close(self):
        """Clean up resources"""
        try:
            # Close Enhanced HTTP client
            if hasattr(self.enhanced_http, 'close'):
                self.enhanced_http.close()
                logger.info("Closed Enhanced HTTP client")
                
            # Close the original crawler (handles Playwright browsers)
            if hasattr(self.original_crawler, 'close'):
                self.original_crawler.close()
                logger.info("Closed original crawler resources")
        except Exception as e:
            logger.warning(f"Error closing crawler resources: {e}")
            
        # Note: CacheManager uses SQLite context managers, no explicit close needed
        # Note: ScrapingBee and Google Search are HTTP-based APIs, no cleanup needed
        logger.info("Enhanced crawler manager cleanup completed") 