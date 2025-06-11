"""
Enhanced Crawler Manager with CLEAN 4-Tier Escalation System

Tier 1: Google Search API (find specific articles from index pages)
Tier 2: Enhanced HTTP (browser-like headers - FREE & FAST) + CONTENT QUALITY CHECK
Tier 3: ScrapingBee API (when Enhanced HTTP fails OR returns generic content)
Tier 4: Original Crawler (RSS + Playwright as last resort)

CLEAN AND SIMPLE: try each tier until one succeeds with QUALITY content.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
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
            
        # Tier 1: Basic HTTP (FREE - simplest approach first)
        logger.info(f"Tier 1: Trying Basic HTTP (free) for {url}")
        
        basic_content = self._fetch_basic_http(url)
        if basic_content:
            # EXTRACT CONTENT FIRST to test quality
            from src.utils.content_extractor import extract_article_content
            expected_topic = f"{make} {model}"
            extracted_content = extract_article_content(basic_content, url, expected_topic)
            
            # Check if extraction was successful (not just 30 chars from 469KB)
            min_content_length = 200  # Reasonable minimum for an article
            extraction_successful = extracted_content and len(extracted_content.strip()) >= min_content_length
            
            if extraction_successful:
                # Content extraction succeeded, now check if it's generic
                if not self.is_generic_content(extracted_content, url, make, model):
                    logger.info(f"Tier 1 Success: Basic HTTP + successful extraction found SPECIFIC content for {url}")
                    result = {
                        'success': True,
                        'content': basic_content,  # Return original HTML for further processing
                        'title': 'Basic HTTP Result',
                        'url': url,
                        'tier_used': 'Tier 1: Basic HTTP',
                        'cached': False
                    }
                    # Cache the result
                    self.cache_manager.store_result(
                        person_id=person_name or "unknown",
                        domain=domain,
                        make=make,
                        model=model,
                        url=url,
                        content=basic_content
                    )
                    return result
                else:
                    logger.info(f"Tier 1: Content extraction succeeded but content is GENERIC, escalating to Enhanced HTTP")
            else:
                extracted_length = len(extracted_content.strip()) if extracted_content else 0
                logger.info(f"Tier 1: Content extraction FAILED ({extracted_length} chars from {len(basic_content)} chars), escalating to Enhanced HTTP")

        # Tier 2: Enhanced HTTP + Content Extraction Test (auto-escalation based on quality)
        logger.info(f"Tier 2: Trying Enhanced HTTP (browser-like headers) for {url}")
        
        http_content = self.enhanced_http.fetch_url(url)
        if http_content:
            # EXTRACT CONTENT FIRST to test quality
            from src.utils.content_extractor import extract_article_content
            expected_topic = f"{make} {model}"
            extracted_content = extract_article_content(http_content, url, expected_topic)
            
            # Check if extraction was successful (not just 30 chars from 469KB)
            min_content_length = 200  # Reasonable minimum for an article
            extraction_successful = extracted_content and len(extracted_content.strip()) >= min_content_length
            
            if extraction_successful:
                # Content extraction succeeded, now check if it's generic
                if not self.is_generic_content(extracted_content, url, make, model):
                    logger.info(f"Tier 2 Success: Enhanced HTTP + successful extraction found SPECIFIC content for {url}")
                    result = {
                        'success': True,
                        'content': http_content,  # Return original HTML for further processing
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
                    logger.info(f"Tier 2: Content extraction succeeded but content is GENERIC, escalating to ScrapingBee")
            else:
                extracted_length = len(extracted_content.strip()) if extracted_content else 0
                logger.info(f"Tier 2: Content extraction FAILED ({extracted_length} chars from {len(http_content)} chars), escalating to ScrapingBee")

        # Tier 3: ScrapingBee (when Enhanced HTTP fails OR returns generic content)
        logger.info(f"Tier 3: Trying ScrapingBee for {url}")
        
        bee_content = self.scraping_bee.scrape_url(url)
        if bee_content:
            # EXTRACT CONTENT FIRST to test quality (same as Enhanced HTTP)
            from src.utils.content_extractor import extract_article_content
            expected_topic = f"{make} {model}"
            extracted_content = extract_article_content(bee_content, url, expected_topic)
            
            # Check if extraction was successful (not just 30 chars from 638KB)
            min_content_length = 200  # Reasonable minimum for an article
            extraction_successful = extracted_content and len(extracted_content.strip()) >= min_content_length
            
            if extraction_successful:
                # Content extraction succeeded, now check if it's generic
                if not self.is_generic_content(extracted_content, url, make, model):
                    logger.info(f"Tier 3 Success: ScrapingBee + successful extraction found SPECIFIC content for {url}")
                    result = {
                        'success': True,
                        'content': bee_content,  # Return original HTML for further processing
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
                else:
                    logger.info(f"Tier 3: ScrapingBee content extraction succeeded but content is GENERIC, escalating to Google Search")
            else:
                extracted_length = len(extracted_content.strip()) if extracted_content else 0
                logger.info(f"Tier 3: ScrapingBee content extraction FAILED ({extracted_length} chars from {len(bee_content)} chars), escalating to Index Page Discovery")
        
        # Tier 3.5: Index Page Discovery (when all direct scraping fails but we have a category page)
        logger.info(f"Tier 3.5: All direct scraping failed, trying Index Page Discovery for {make} {model}")
        index_discovery_result = self._try_index_page_discovery(url, make, model, person_name, domain)
        if index_discovery_result and index_discovery_result['success']:
            logger.info(f"Tier 3.5 Success: Index Page Discovery found specific article")
            result = index_discovery_result.copy()
            result.update({
                'tier_used': 'Tier 3.5: Index Discovery + ' + index_discovery_result.get('tier_used', 'Unknown'),
                'cached': False
            })
            # Cache the result
            self.cache_manager.store_result(
                person_id=person_name or "unknown",
                domain=domain,
                make=make,
                model=model,
                url=index_discovery_result['url'],
                content=index_discovery_result['content']
            )
            return result
        
        # Tier 4: Google Search (FALLBACK ONLY - when all direct scraping fails)
        logger.info(f"Tier 4: All direct scraping and Index Discovery failed, trying Google Search as FALLBACK for {make} {model}")
        
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
            logger.info(f"Tier 4 Success: Google Search found specific article: {specific_url}")
            
            # Now crawl the specific article we found
            article_result = self._crawl_specific_url(specific_url, make, model)
            
            if article_result['success']:
                result = article_result.copy()
                result.update({
                    'tier_used': 'Tier 4: Google Search + ' + article_result.get('tier_used', 'Unknown'),
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
                
        # Tier 5: Original crawler (RSS + Playwright as last resort)
        logger.info(f"Tier 5: All direct scraping and Google Search failed, using original crawler for {url}")
        
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
                'tier_used': f"Tier 5: Original Crawler",
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
        
        # Tier 1: Enhanced HTTP + Content Extraction Test (auto-escalation based on quality)
        logger.info(f"Trying Enhanced HTTP for specific URL: {url}")
        http_content = self.enhanced_http.fetch_url(url)
        if http_content:
            # EXTRACT CONTENT FIRST to test quality
            from src.utils.content_extractor import extract_article_content
            expected_topic = f"{make} {model}"
            extracted_content = extract_article_content(http_content, url, expected_topic)
            
            # Check if extraction was successful (not just 30 chars from 469KB)
            min_content_length = 200  # Reasonable minimum for an article
            extraction_successful = extracted_content and len(extracted_content.strip()) >= min_content_length
            
            if extraction_successful:
                # Content extraction succeeded, now check if it's generic
                if not self.is_generic_content(extracted_content, url, make, model):
                    logger.info(f"Enhanced HTTP + successful extraction found SPECIFIC content for: {url}")
                    return {
                        'success': True,
                        'content': http_content,
                        'title': 'Enhanced HTTP Result',
                        'url': url,
                        'tier_used': 'Enhanced HTTP'
                    }
                else:
                    logger.info(f"Enhanced HTTP: content extraction succeeded but content is GENERIC for {url}, escalating to ScrapingBee")
            else:
                extracted_length = len(extracted_content.strip()) if extracted_content else 0
                logger.info(f"Enhanced HTTP: content extraction FAILED ({extracted_length} chars from {len(http_content)} chars) for {url}, escalating to ScrapingBee")
            
        # Tier 2: Try ScrapingBee when Enhanced HTTP fails OR returns generic content
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
            
        # Tier 3: Use original crawler as last resort
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
        
    def _fetch_basic_http(self, url: str) -> Optional[str]:
        """Basic HTTP request with minimal headers (Level 1)"""
        try:
            import requests
            
            headers = {
                'User-Agent': 'DriveShopMediaMonitorBot/1.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            logger.info(f"Making basic HTTP request to {url}")
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                logger.info(f"Basic HTTP success for {url} ({len(response.text)} chars)")
                return response.text
            else:
                logger.warning(f"Basic HTTP failed for {url}: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Basic HTTP error for {url}: {e}")
            return None

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

    def _try_index_page_discovery(self, index_url: str, make: str, model: str, person_name: str, domain: str) -> Optional[Dict[str, Any]]:
        """
        INDEX PAGE DISCOVERY: Scrape index page, extract article links, find relevant ones, crawl them.
        This is like YouTube processing but for web articles.
        """
        logger.info(f"🔍 Starting Index Page Discovery for {index_url}")
        
        # Step 1: Scrape the ENTIRE index page (like YouTube RSS feed)
        logger.info(f"Step 1: Scraping index page: {index_url}")
        index_content = self._scrape_index_page(index_url)
        if not index_content:
            logger.warning(f"❌ Failed to scrape index page: {index_url}")
            return None
            
        # Step 2: Extract ALL article links from index page (like YouTube video links)
        logger.info(f"Step 2: Extracting article links from index page")
        article_links = self._extract_article_links_from_index(index_content, index_url)
        if not article_links:
            logger.warning(f"❌ No article links found on index page: {index_url}")
            return None
            
        logger.info(f"📄 Found {len(article_links)} article links on index page")
        
        # Step 3: Search through article links for relevant ones (like YouTube transcript search)
        logger.info(f"Step 3: Searching for relevant articles about {make} {model}")
        relevant_articles = self._find_relevant_articles(article_links, make, model, person_name)
        if not relevant_articles:
            logger.warning(f"❌ No relevant articles found for {make} {model}")
            return None
            
        logger.info(f"✅ Found {len(relevant_articles)} relevant article candidates")
        
        # Step 4: Crawl the BEST relevant article (like YouTube specific video)
        logger.info(f"Step 4: Crawling best relevant article")
        for score, article_url, article_title in relevant_articles:
            logger.info(f"🎯 INDEX DISCOVERY TRYING: {article_title} (score: {score}) - {article_url}")
            logger.info(f"🔍 IMPORTANT: This is the article that will be crawled and checked for dates!")
            
            article_result = self._crawl_specific_url(article_url, make, model)
            if article_result['success']:
                logger.info(f"✅ INDEX DISCOVERY SUCCESS: Successfully crawled specific article: {article_url}")
                return {
                    'success': True,
                    'content': article_result['content'],
                    'title': article_title,
                    'url': article_url,
                    'tier_used': f"Index Discovery -> {article_result.get('tier_used', 'Unknown')}",
                    'discovery_details': {
                        'index_url': index_url,
                        'total_links': len(article_links),
                        'relevant_links': len(relevant_articles),
                        'selected_score': score,
                        'selected_title': article_title
                    }
                }
            else:
                logger.warning(f"❌ INDEX DISCOVERY FAILED to crawl article: {article_url}")
                logger.warning(f"❌ Reason: {article_result.get('error', 'Unknown error')}")
                
        logger.warning(f"❌ All relevant articles failed to crawl")
        return None

    def _scrape_index_page(self, index_url: str) -> Optional[str]:
        """Scrape MULTIPLE PAGES of the index with PAGINATION SUPPORT"""
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, urlparse
        
        logger.info(f"🔍 PAGINATION: Starting multi-page scraping for {index_url}")
        
        all_content = ""
        page_count = 0
        max_pages = 5  # Reasonable limit to avoid infinite loops
        current_url = index_url
        visited_urls = set()
        
        while current_url and page_count < max_pages and current_url not in visited_urls:
            page_count += 1
            visited_urls.add(current_url)
            
            logger.info(f"📄 PAGINATION: Scraping page {page_count}: {current_url}")
            
            # Try Enhanced HTTP first (fast and free)
            page_content = self.enhanced_http.fetch_url(current_url)
            if not page_content or len(page_content) < 1000:
                # Try ScrapingBee if Enhanced HTTP fails
                logger.info(f"Enhanced HTTP failed for page {page_count}, trying ScrapingBee")
                page_content = self.scraping_bee.scrape_url(current_url)
                
            if page_content and len(page_content) > 1000:
                logger.info(f"✅ PAGINATION: Got page {page_count} content ({len(page_content)} chars)")
                all_content += page_content + "\n<!-- PAGE_BREAK -->\n"
                
                # Look for "Next Page" link for pagination
                next_url = self._find_next_page_url(page_content, current_url)
                if next_url and next_url != current_url:
                    logger.info(f"🔗 PAGINATION: Found next page URL: {next_url}")
                    current_url = next_url
                else:
                    logger.info(f"🛑 PAGINATION: No more pages found after page {page_count}")
                    break
            else:
                logger.warning(f"❌ PAGINATION: Failed to get content for page {page_count}")
                break
                
        if all_content:
            logger.info(f"✅ PAGINATION: Successfully scraped {page_count} pages ({len(all_content)} total chars)")
            return all_content
        else:
            logger.warning(f"❌ PAGINATION: Failed to scrape any pages")
            return None
    
    def _find_next_page_url(self, html_content: str, current_url: str) -> Optional[str]:
        """Find the 'Next Page' URL for pagination"""
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Common pagination selectors for WordPress and other CMS
            next_selectors = [
                'a.next',
                'a[rel="next"]',
                '.pagination a[aria-label*="next" i]',
                '.pagination a[title*="next" i]',
                '.nav-links a[aria-label*="next" i]',
                '.page-numbers a.next',
                '.pagination-next a',
                'a:contains("Next")',
                'a:contains("→")',
                'a:contains("›")',
                'a:contains("»")',
                '.wp-pagenavi a.nextpostslink',
                '.navigation a[title*="next" i]'
            ]
            
            for selector in next_selectors:
                try:
                    if ':contains(' in selector:
                        # Handle text-based selectors differently
                        if 'Next' in selector:
                            next_links = soup.find_all('a', string=lambda text: text and 'next' in text.lower())
                        elif '→' in selector:
                            next_links = soup.find_all('a', string=lambda text: text and '→' in str(text))
                        elif '›' in selector:
                            next_links = soup.find_all('a', string=lambda text: text and '›' in str(text))
                        elif '»' in selector:
                            next_links = soup.find_all('a', string=lambda text: text and '»' in str(text))
                        else:
                            continue
                    else:
                        next_links = soup.select(selector)
                    
                    for link in next_links:
                        href = link.get('href', '')
                        if href:
                            next_url = urljoin(current_url, href)
                            logger.info(f"🔗 PAGINATION: Found next page with selector '{selector}': {next_url}")
                            return next_url
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
                    
            # Fallback: Look for numbered pagination (page/2, page/3, etc.)
            base_url = current_url.rstrip('/')
            if '/page/' in current_url:
                # Extract current page number and increment
                parts = current_url.split('/page/')
                if len(parts) == 2:
                    try:
                        current_page = int(parts[1].split('/')[0])
                        next_page_url = f"{parts[0]}/page/{current_page + 1}/"
                        logger.info(f"🔗 PAGINATION: Generated next page URL: {next_page_url}")
                        return next_page_url
                    except ValueError:
                        pass
            else:
                # Try adding /page/2/ to base URL
                next_page_url = f"{base_url}/page/2/"
                logger.info(f"🔗 PAGINATION: Trying page 2 URL: {next_page_url}")
                return next_page_url
                
            logger.info(f"🛑 PAGINATION: No next page found for {current_url}")
            return None
            
        except Exception as e:
            logger.error(f"❌ PAGINATION: Error finding next page: {e}")
            return None

    def _extract_article_links_from_index(self, html_content: str, base_url: str) -> List[str]:
        """Extract article links from index page HTML (like extracting video links from YouTube)"""
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, urlparse
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            base_domain = urlparse(base_url).netloc
            
            # Look for article links using common patterns
            article_link_selectors = [
                'a[href*="/review"]',
                'a[href*="/test"]', 
                'a[href*="/drive"]',
                'a[href*="/first"]',
                'a[href*="/road"]',
                'article a[href]',
                '.post a[href]',
                '.entry a[href]',
                '.article a[href]',
                'h1 a[href]',
                'h2 a[href]', 
                'h3 a[href]',
                '.headline a[href]',
                '.title a[href]',
                'a[href]'  # CATCH-ALL: Get ALL links, filter by domain and relevance later
            ]
            
            logger.info(f"🔍 DEBUG: Extracting article links from {base_url}")
            logger.info(f"🔍 DEBUG: HTML content length: {len(html_content)} characters")
            
            for selector in article_link_selectors:
                found_links = soup.select(selector)
                logger.info(f"🔍 DEBUG: Selector '{selector}' found {len(found_links)} links")
                
                for link in found_links:
                    href = link.get('href', '')
                    if href:
                        # Convert relative URLs to absolute
                        full_url = urljoin(base_url, href)
                        parsed = urlparse(full_url)
                        
                        # Only include links from the same domain
                        if parsed.netloc == base_domain or parsed.netloc.endswith(f".{base_domain}"):
                            # Filter out obvious non-article pages
                            path = parsed.path.lower()
                            if not any(skip in path for skip in ['/category/', '/tag/', '/author/', '/search', '/page/', '.jpg', '.png', '.pdf']):
                                if full_url not in links:
                                    links.append(full_url)
                                    link_text = link.get_text(strip=True)
                                    logger.info(f"📄 DEBUG: Found article link: {full_url} - Text: '{link_text[:100]}'")
                                    
            logger.info(f"📄 Extracted {len(links)} potential article links")
            
            # DEBUG: Log first 10 links to see what we're finding
            logger.info(f"🔍 DEBUG: First 10 article links found:")
            for i, link in enumerate(links[:10]):
                logger.info(f"  {i+1}. {link}")
                
            return links[:100]  # Increased from 50 to 100 to search deeper pagination
            
        except Exception as e:
            logger.error(f"❌ Error extracting article links: {e}")
            return []

    def _find_relevant_articles(self, article_links: List[str], make: str, model: str, person_name: str) -> List[tuple]:
        """Find articles with FLEXIBLE Make + Model matching - BROADER SEARCH for better results"""
        relevant_articles = []
        
        make_lower = make.lower()
        model_lower = model.lower()
        
        # For Camry Hybrid - split into base model and variant for more flexible search
        model_parts = model_lower.split()
        base_model = model_parts[0] if model_parts else model_lower  # "camry" from "camry hybrid"
        variant = model_parts[1] if len(model_parts) > 1 else ""      # "hybrid" from "camry hybrid"
        
        # Create COMPREHENSIVE model variations (handle dashes, spaces, years, etc.)
        model_variations = [
            model_lower,                      # "camry hybrid"
            base_model,                       # "camry" (BROADER SEARCH - key for finding more articles)
            model_lower.replace(' ', ''),     # "camryhybrid"
            model_lower.replace(' ', '-'),    # "camry-hybrid"
            model_lower.replace('-', ''),     # "cx5" (for CX-5)
            model_lower.replace('-', ' '),    # "cx 5"
        ]
        
        # Add year variants for recent years (2023-2025)
        current_year = 2025
        for year in [current_year, current_year-1, current_year-2]:  # 2025, 2024, 2023
            model_variations.extend([
                f"{year} {base_model}",       # "2025 camry"
                f"{base_model} {year}",       # "camry 2025"  
                f"{year} {model_lower}",      # "2025 camry hybrid"
                f"{model_lower} {year}",      # "camry hybrid 2025"
            ])
        
        # Remove duplicates and filter out empty strings
        model_variations = list(set([v for v in model_variations if v.strip()]))
        
        logger.info(f"🔍 FLEXIBLE SEARCH: Looking for articles about '{make}' '{model}'")
        logger.info(f"🔍 Base model: '{base_model}', Variant: '{variant}'")
        logger.info(f"🔍 Model variations ({len(model_variations)}): {model_variations[:15]}...")  # Show first 15
        logger.info(f"🔍 Searching through {len(article_links)} total article links...")
        
        for i, article_url in enumerate(article_links):
            try:
                url_lower = article_url.lower()
                title = self._extract_title_from_url(article_url)
                title_lower = title.lower()
                
                # TIER 1: Check for exact make + model match (perfect)
                has_make_url = make_lower in url_lower
                has_make_title = make_lower in title_lower
                has_make = has_make_url or has_make_title
                
                has_full_model_url = any(variation in url_lower for variation in model_variations)
                has_full_model_title = any(variation in title_lower for variation in model_variations)
                has_full_model = has_full_model_url or has_full_model_title
                matching_variation = next((var for var in model_variations if var in url_lower or var in title_lower), None)
                
                # TIER 2: Check for base model only (broader search)
                has_base_model_url = base_model in url_lower
                has_base_model_title = base_model in title_lower
                has_base_model = has_base_model_url or has_base_model_title
                
                # TIER 3: Check for variant only (like "hybrid")
                has_variant_url = variant and variant in url_lower
                has_variant_title = variant and variant in title_lower
                has_variant = has_variant_url or has_variant_title
                
                if i < 30:  # Debug first 30 URLs to see what we're finding
                    logger.info(f"🔍 {i+1}/{len(article_links)}: {article_url}")
                    logger.info(f"  Title: '{title}'")
                    logger.info(f"  Make '{make}' found: URL={has_make_url}, Title={has_make_title}")
                    logger.info(f"  Full model found: URL={has_full_model_url}, Title={has_full_model_title} (variation: {matching_variation})")
                    logger.info(f"  Base model '{base_model}' found: URL={has_base_model_url}, Title={has_base_model_title}")
                    if variant:
                        logger.info(f"  Variant '{variant}' found: URL={has_variant_url}, Title={has_variant_title}")
                
                score = 0
                match_type = ""
                
                if has_make and has_full_model:
                    # PERFECT MATCH: Make + Full Model
                    score = 1000
                    match_type = f"PERFECT: {make} + {matching_variation}"
                elif has_full_model:
                    # EXCELLENT: Full Model without make
                    score = 800
                    match_type = f"EXCELLENT: {matching_variation} (no make)"
                elif has_make and has_base_model and has_variant:
                    # VERY GOOD: Make + Base Model + Variant (e.g., Toyota + Camry + Hybrid)
                    score = 700
                    match_type = f"VERY GOOD: {make} + {base_model} + {variant}"
                elif has_base_model and has_variant:
                    # GOOD: Base Model + Variant (no make) (e.g., Camry + Hybrid)
                    score = 600
                    match_type = f"GOOD: {base_model} + {variant} (no make)"
                elif has_make and has_base_model:
                    # DECENT: Make + Base Model only (e.g., Toyota + Camry)
                    score = 500
                    match_type = f"DECENT: {make} + {base_model}"
                elif has_base_model:
                    # FAIR: Base Model only (e.g., Camry only)
                    score = 300
                    match_type = f"FAIR: {base_model} only"
                    
                if score > 0:
                    relevant_articles.append((score, article_url, title))
                    logger.info(f"✅ {match_type}: {title} - {article_url}")
                    
            except Exception as e:
                logger.warning(f"❌ Error checking article {article_url}: {e}")
                
        # Sort by relevance score (highest first)
        relevant_articles.sort(key=lambda x: x[0], reverse=True)
        
        logger.info(f"🎯 FINAL SEARCH RESULTS for {make} {model}:")
        if relevant_articles:
            logger.info(f"📄 Found {len(relevant_articles)} relevant articles (showing top 15):")
            for i, (score, url, title) in enumerate(relevant_articles[:15]):
                logger.info(f"  {i+1}. Score: {score}, Title: {title}")
                logger.info(f"       URL: {url}")
                
            # CRITICAL DEBUG: Show which article will be selected first
            best_score, best_url, best_title = relevant_articles[0]
            logger.info(f"🚨 WILL SELECT FIRST: {best_title} (Score: {best_score})")
            logger.info(f"🚨 WILL SELECT URL: {best_url}")
        else:
            logger.warning(f"❌ NO RELEVANT ARTICLES FOUND for {make} {model}")
            logger.warning(f"❌ Searched {len(article_links)} links")
            logger.warning(f"❌ Base model: '{base_model}', Variant: '{variant}', Make: '{make}'")
            logger.warning(f"❌ Model variations: {model_variations[:10]}...")
            
        return relevant_articles[:10]  # Return top 10 most relevant

    def _extract_title_from_url(self, url: str) -> str:
        """Extract a readable title from URL path"""
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            # Get the last meaningful part of the path
            parts = [p for p in path.split('/') if p]
            if parts:
                title = parts[-1].replace('-', ' ').replace('_', ' ')
                return title.title()
            return "Unknown Article"
        except:
            return "Unknown Article" 