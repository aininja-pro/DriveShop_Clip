"""
Enhanced Crawler Manager with 6-Tier Escalation System

Tier 1: Basic HTTP (simplest, fastest)
Tier 2: Enhanced HTTP (browser-like headers) + CONTENT QUALITY CHECK
Tier 3: RSS Feed (if available - FREE & FAST & STRUCTURED)
Tier 4: ScrapFly API (premium with residential proxies)
Tier 5: ScrapingBee API (backup premium service) - Currently disabled
Tier 6: Original Crawler (Playwright browser as last resort)

Plus: Index Page Discovery and Google Search for finding specific articles
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
        
        # Check if this is a homepage/index URL
        parsed_url = urlparse(url)
        if not parsed_url.path or parsed_url.path == '/' or parsed_url.path == '':
            logger.info(f"🏠 Homepage URL detected ({url}) - treating as GENERIC content for escalation")
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
        6-tier escalation system with CONTENT QUALITY DETECTION
        
        Tier 1: Basic HTTP (free & fast)
        Tier 2: Enhanced HTTP (browser-like headers)
        Tier 3: RSS Feed (if available - structured data)
        Tier 4: ScrapFly (premium with residential proxies)
        Tier 5: ScrapingBee (backup service) - Currently disabled
        
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
        
        # BLOCK SOCIAL MEDIA AND NON-CONTENT DOMAINS
        blocked_domains = [
            'instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'tiktok.com',
            'linkedin.com', 'pinterest.com', 'snapchat.com', 'youtube.com/user/',
            'youtube.com/channel/', 'youtube.com/c/', 'youtube.com/@'
        ]
        
        for blocked_domain in blocked_domains:
            if blocked_domain in url.lower():
                logger.warning(f"🚫 BLOCKED: Skipping social media/profile URL: {url}")
                return {
                    'success': False,
                    'content': '',
                    'title': '',
                    'url': url,
                    'tier_used': 'Blocked Domain',
                    'cached': False,
                    'error': f'Social media/profile URLs are not content sources: {blocked_domain}'
                }
        
        # Check cache first - FIX MALFORMED URL PARSING
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # Handle malformed URLs like "https:townvibe.com" (missing //)
            if not domain and url.startswith(('http:', 'https:')):
                logger.warning(f"⚠️ Malformed URL detected: {url}")
                # Try to fix by adding missing //
                if url.startswith('http:') and not url.startswith('http://'):
                    if '://' not in url:
                        fixed_url = url.replace('http:', 'http://', 1)
                    else:
                        fixed_url = url
                elif url.startswith('https:') and not url.startswith('https://'):
                    if '://' not in url:
                        fixed_url = url.replace('https:', 'https://', 1)
                    else:
                        fixed_url = url
                else:
                    fixed_url = url
                
                logger.info(f"🔧 Fixed malformed URL: {url} → {fixed_url}")
                url = fixed_url  # Use fixed URL for all subsequent processing
                parsed_url = urlparse(url)  # Re-parse the fixed URL
                domain = parsed_url.netloc.lower()
                
            if not domain:
                logger.error(f"❌ Unable to extract domain from URL: {url}")
                return {
                    'success': False,
                    'content': '',
                    'title': '',
                    'url': url,
                    'tier_used': 'URL Parsing Failed',
                    'cached': False,
                    'error': f'Invalid URL format: {url}'
                }
        except Exception as e:
            logger.error(f"❌ URL parsing error for {url}: {e}")
            return {
                'success': False,
                'content': '',
                'title': '',
                'url': url,
                'tier_used': 'URL Parsing Error',
                'cached': False,
                'error': f'URL parsing failed: {e}'
            }
        
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
                    return self._add_byline_to_result(result, person_name)
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
                    return self._add_byline_to_result(result, person_name)
                else:
                    logger.info(f"Tier 2: Content extraction succeeded but content is GENERIC, escalating to ScrapingBee")
            else:
                extracted_length = len(extracted_content.strip()) if extracted_content else 0
                logger.info(f"Tier 2: Content extraction FAILED ({extracted_length} chars from {len(http_content)} chars), escalating to ScrapingBee")

        # Tier 3: RSS Feed (if available - FREE and FAST)
        rss_url = self.original_crawler._get_rss_url(url)
        if rss_url:
            logger.info(f"Tier 3: Found RSS feed for domain, trying RSS: {rss_url}")
            
            # Use RSS crawling from original crawler
            rss_content, rss_title, rss_error, found_url = self.original_crawler._crawl_level3_rss(
                rss_url, url, make, model
            )
            
            if rss_content and not rss_error:
                # Test content quality
                from src.utils.content_extractor import extract_article_content
                extracted_content = extract_article_content(rss_content, found_url or url)
                
                if extracted_content and not self.is_generic_content(extracted_content, found_url or url, make, model):
                    logger.info(f"✅ Tier 3: RSS feed returned QUALITY content for {make} {model}")
                    result = {
                        'success': True,
                        'content': rss_content,
                        'title': rss_title or 'RSS Result',
                        'url': found_url or url,
                        'tier_used': 'Tier 3: RSS Feed',
                        'cached': False
                    }
                    # Cache the result
                    self.cache_manager.store_result(
                        person_id=person_name or "unknown",
                        domain=domain,
                        make=make,
                        model=model,
                        url=found_url or url,
                        content=rss_content
                    )
                    return self._add_byline_to_result(result, person_name)
                else:
                    logger.info(f"Tier 3: RSS content is generic or extraction failed, escalating")
            else:
                logger.info(f"Tier 3: RSS feed failed: {rss_error}, escalating")
        else:
            logger.info(f"Tier 3: No RSS feed configured for this domain, skipping to Tier 4")
        
        # Tier 4: ScrapFly (premium service with residential proxies - best success rate)
        logger.info(f"Tier 4: Trying ScrapFly for {url}")
        try:
            from src.utils.scrapfly_client import scrapfly_crawl_with_fallback
            scrapfly_content, scrapfly_title, scrapfly_error = scrapfly_crawl_with_fallback(url)
            if scrapfly_content and not scrapfly_error:
                # EXTRACT CONTENT FIRST to test quality
                from src.utils.content_extractor import extract_article_content
                expected_topic = f"{make} {model}"
                extracted_content = extract_article_content(scrapfly_content, url, expected_topic)
                
                # Check if extraction was successful
                min_content_length = 200
                extraction_successful = extracted_content and len(extracted_content.strip()) >= min_content_length
                
                if extraction_successful and not self.is_generic_content(extracted_content, url, make, model):
                    logger.info(f"Tier 3 Success: ScrapFly + successful extraction found SPECIFIC content for {url}")
                    result = {
                        'success': True,
                        'content': scrapfly_content,
                        'title': scrapfly_title or 'ScrapFly Result',
                        'url': url,
                        'tier_used': 'Tier 4: ScrapFly',
                        'cached': False
                    }
                    # Cache the result
                    self.cache_manager.store_result(
                        person_id=person_name or "unknown",
                        domain=domain,
                        make=make,
                        model=model,
                        url=url,
                        content=scrapfly_content
                    )
                    return self._add_byline_to_result(result, person_name)
                else:
                    logger.info(f"Tier 4: ScrapFly content extraction failed or generic, escalating to ScrapingBee")
            else:
                logger.warning(f"Tier 4: ScrapFly failed for {url}: {scrapfly_error}")
        except Exception as e:
            logger.warning(f"Tier 4: ScrapFly error for {url}: {e}")

        # Tier 5: ScrapingBee (backup service) - DISABLED FOR TESTING
        logger.info(f"Tier 5: ScrapingBee DISABLED for testing - skipping to Index Discovery")
        
        # bee_content = self.scraping_bee.scrape_url(url)
        bee_content = None  # Force skip ScrapingBee
        if False:  # bee_content:
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
                    logger.info(f"Tier 4 Success: ScrapingBee + successful extraction found SPECIFIC content for {url}")
                    result = {
                        'success': True,
                        'content': bee_content,  # Return original HTML for further processing
                        'title': 'ScrapingBee Backup Result',
                        'url': url,
                        'tier_used': 'Tier 5: ScrapingBee Backup',
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
                    return self._add_byline_to_result(result, person_name)
                else:
                    logger.info(f"Tier 5: ScrapingBee content extraction succeeded but content is GENERIC, escalating to Google Search")
            else:
                extracted_length = len(extracted_content.strip()) if extracted_content else 0
                logger.info(f"Tier 5: ScrapingBee content extraction FAILED ({extracted_length} chars from {len(bee_content)} chars), escalating to Index Page Discovery")
        
        # Tier 5.5: Index Page Discovery (when all direct scraping fails but we have a category page)
        logger.info(f"Tier 5.5: All direct scraping failed, trying Index Page Discovery for {make} {model}")
        index_discovery_result = self._try_index_page_discovery(url, make, model, person_name, domain)
        if index_discovery_result and index_discovery_result['success']:
            logger.info(f"Tier 5.5 Success: Index Page Discovery found specific article")
            result = index_discovery_result.copy()
            result.update({
                'tier_used': 'Tier 5.5: Index Discovery + ' + index_discovery_result.get('tier_used', 'Unknown'),
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
            return self._add_byline_to_result(result, person_name)
        
        # Tier 6: Google Search (FALLBACK ONLY - when all direct scraping fails)
        logger.info(f"Tier 6: All direct scraping and Index Discovery failed, trying Google Search as FALLBACK for {make} {model}")
        
        # Extract domain from URL
        parsed_url = urlparse(url)
        domain_clean = parsed_url.netloc.lower().replace('www.', '')
        
        # Try to find a specific article using Google Search (synchronous version)
        search_result = self.google_search.search_for_article_sync(
            domain=domain_clean,
            make=make,
            model=model,
            year=None,
            author=person_name
        )
        
        specific_url = None
        attribution_info = {}
        
        if search_result:
            if isinstance(search_result, dict):
                specific_url = search_result.get('url')
                attribution_info = {
                    'attribution_strength': search_result.get('attribution_strength', 'unknown'),
                    'actual_byline': search_result.get('actual_byline')
                }
            else:
                # Backward compatibility for string returns
                specific_url = search_result
                attribution_info = {
                    'attribution_strength': 'unknown',
                    'actual_byline': None
                }
        
        if specific_url and specific_url != url:
            logger.info(f"Tier 4 Success: Google Search found specific article: {specific_url}")
            
            # Now crawl the specific article we found
            article_result = self._crawl_specific_url(specific_url, make, model)
            
            if article_result['success']:
                result = article_result.copy()
                result.update({
                    'tier_used': 'Tier 6: Google Search + ' + article_result.get('tier_used', 'Unknown'),
                    'cached': False,
                    # Add attribution information for UI display
                    'attribution_strength': attribution_info.get('attribution_strength', 'unknown'),
                    'actual_byline': attribution_info.get('actual_byline')
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
                return self._add_byline_to_result(result, person_name)
                
        # Tier 7: Original crawler (Playwright as last resort)
        logger.info(f"Tier 7: All direct scraping and Google Search failed, using original crawler for {url}")
        
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
                'tier_used': f"Tier 7: Original Crawler",
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
            return self._add_byline_to_result(result, person_name)
            
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
            
        # Tier 2: Try ScrapFly FIRST (premium service with residential proxies - best success rate)
        logger.info(f"Tier 2: Trying ScrapFly for specific URL: {url}")
        try:
            from src.utils.scrapfly_client import scrapfly_crawl_with_fallback
            content, title, error = scrapfly_crawl_with_fallback(url)
            if content and not error and len(content) > 1000:
                logger.info(f"✅ ScrapFly successfully extracted specific article content")
                return {
                    'success': True,
                    'content': content,
                    'title': title or 'ScrapFly Result',
                    'url': url,
                    'tier_used': 'ScrapFly'
                }
            else:
                logger.warning(f"❌ ScrapFly failed for specific URL: {error}")
        except Exception as e:
            logger.warning(f"❌ ScrapFly error: {e}")
            
        # Tier 3: Try ScrapingBee as backup (fallback service) - DISABLED FOR TESTING
        logger.info(f"Tier 3: ScrapingBee DISABLED for testing - skipping to Tier 4")
        # bee_content = self.scraping_bee.scrape_url(url)
        # if bee_content:
        #     logger.info(f"ScrapingBee backup success for specific URL: {url}")
        #     return {
        #         'success': True,
        #         'content': bee_content,
        #         'title': 'ScrapingBee Backup Result',
        #         'url': url,
        #         'tier_used': 'ScrapingBee Backup'
        #     }
        # else:
        #     logger.warning(f"ScrapingBee backup failed for specific URL: {url}")
        
        # Tier 4: Use headless browser directly (skip RSS for specific URLs)
        logger.info(f"Tier 4: Using headless browser directly for specific URL: {url}")
        from src.utils.browser_crawler import BrowserCrawler
        
        browser_crawler = BrowserCrawler(headless=True)
        try:
            content, title, error = browser_crawler.crawl(url, wait_time=10, scroll=True)
            if content and not error:
                logger.info(f"✅ Headless browser successfully extracted specific article content")
                return {
                    'success': True,
                    'content': content,
                    'title': title or 'Headless Browser Result',
                    'url': url,
                    'tier_used': 'Headless Browser Direct'
                }
            else:
                logger.warning(f"❌ Headless browser failed for specific URL: {error}")
        finally:
            browser_crawler.close()
            
        # Final fallback: Use original crawler with RSS disabled for specific URLs
        logger.info(f"Final fallback: original crawler for specific URL: {url}")
        content, title, error, actual_url = self.original_crawler.crawl(
            url, 
            allow_escalation=False,  # DISABLE escalation to prevent RSS override
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
                
                # EXTRACT AUTHOR INFORMATION for attribution transparency
                attribution_strength = 'unknown'
                actual_byline = None
                
                if person_name:
                    logger.info(f"🔍 INDEX DISCOVERY: Extracting author information for {person_name}")
                    try:
                        # Extract actual byline from the article content
                        actual_byline = self._extract_byline_from_content(article_result['content'], article_url)
                        if actual_byline:
                            logger.info(f"📝 INDEX DISCOVERY: Found byline author: {actual_byline}")
                            # Check if expected author matches actual byline
                            if person_name.lower() in actual_byline.lower():
                                attribution_strength = 'strong'
                                logger.info(f"✅ INDEX DISCOVERY: Strong attribution - {person_name} found in byline")
                            else:
                                attribution_strength = 'delegated'
                                logger.info(f"⚠️ INDEX DISCOVERY: Delegated content - {person_name} not in byline, actual: {actual_byline}")
                        else:
                            attribution_strength = 'unknown'
                            logger.info(f"❓ INDEX DISCOVERY: Could not extract byline from article")
                    except Exception as e:
                        logger.warning(f"❌ INDEX DISCOVERY: Error extracting author info: {e}")
                        attribution_strength = 'unknown'
                        actual_byline = None
                
                return {
                    'success': True,
                    'content': article_result['content'],
                    'title': article_title,
                    'url': article_url,
                    'tier_used': f"Index Discovery -> {article_result.get('tier_used', 'Unknown')}",
                    # ADD ATTRIBUTION INFORMATION
                    'attribution_strength': attribution_strength,
                    'actual_byline': actual_byline,
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
                # Try ScrapingBee if Enhanced HTTP fails - DISABLED FOR TESTING
                logger.info(f"Enhanced HTTP failed for page {page_count}, ScrapingBee DISABLED - skipping")
                # page_content = self.scraping_bee.scrape_url(current_url)
                
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
                    
            # Fallback: Look for numbered pagination (page/2, page/3, ?page=2, etc.)
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            base_url = current_url.rstrip('/')
            
            # First check if URL already has page parameter (?page=X)
            parsed_url = urlparse(current_url)
            query_params = parse_qs(parsed_url.query)
            
            if 'page' in query_params:
                # URL uses query parameter pagination like ?page=2
                try:
                    current_page = int(query_params['page'][0])
                    query_params['page'] = [str(current_page + 1)]
                    new_query = urlencode(query_params, doseq=True)
                    next_page_url = urlunparse((
                        parsed_url.scheme,
                        parsed_url.netloc,
                        parsed_url.path,
                        parsed_url.params,
                        new_query,
                        parsed_url.fragment
                    ))
                    logger.info(f"🔗 PAGINATION: Generated next page URL (query param): {next_page_url}")
                    return next_page_url
                except (ValueError, IndexError):
                    pass
            elif '/page/' in current_url:
                # URL uses path-based pagination like /page/2/
                parts = current_url.split('/page/')
                if len(parts) == 2:
                    try:
                        current_page = int(parts[1].split('/')[0])
                        next_page_url = f"{parts[0]}/page/{current_page + 1}/"
                        logger.info(f"🔗 PAGINATION: Generated next page URL (path-based): {next_page_url}")
                        return next_page_url
                    except ValueError:
                        pass
            else:
                # No pagination found - try both formats
                # For Hagerty specifically, use query parameter format
                if 'hagerty.com' in current_url:
                    query_params['page'] = ['2']
                    new_query = urlencode(query_params, doseq=True)
                    next_page_url = urlunparse((
                        parsed_url.scheme,
                        parsed_url.netloc,
                        parsed_url.path,
                        parsed_url.params,
                        new_query,
                        parsed_url.fragment
                    ))
                    logger.info(f"🔗 PAGINATION: Trying Hagerty-style page 2 URL: {next_page_url}")
                    return next_page_url
                else:
                    # Try WordPress-style /page/2/
                    next_page_url = f"{base_url}/page/2/"
                    logger.info(f"🔗 PAGINATION: Trying WordPress-style page 2 URL: {next_page_url}")
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
                        
                        # Only include links from the same domain (with proper subdomain handling)
                        # Fix: Ensure we're checking actual subdomains, not just string endings
                        link_domain = parsed.netloc.lower()
                        if link_domain == base_domain or (link_domain.endswith(f".{base_domain}") and 
                                                          link_domain[-(len(base_domain)+1)] == '.'):
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
        
        # Smart model parsing for compound models like "GR Corolla Premium"
        model_parts = model_lower.split()
        
        # Handle Toyota GR models specially (GR is a sub-brand, not the base model)
        if len(model_parts) >= 2 and model_parts[0] == "gr":
            base_model = f"{model_parts[0]} {model_parts[1]}"  # "gr corolla" from "gr corolla premium"
            variant = " ".join(model_parts[2:]) if len(model_parts) > 2 else ""  # "premium"
        else:
            # Standard parsing for regular models like "Camry Hybrid"
            base_model = model_parts[0] if model_parts else model_lower  # "camry" from "camry hybrid"
            variant = model_parts[1] if len(model_parts) > 1 else ""      # "hybrid" from "camry hybrid"
        
        # Use the enhanced model variations generator that handles trim levels
        from src.utils.model_variations import generate_model_variations
        model_variations = generate_model_variations(make, model)
        
        # Add year variants to the generated variations
        current_year = 2025
        year_variations = []
        for year in [current_year, current_year-1, current_year-2]:  # 2025, 2024, 2023
            for variation in model_variations[:5]:  # Add years to the first few variations
                year_variations.extend([
                    f"{year} {variation}",       # "2025 crown signia"
                    f"{variation} {year}",       # "crown signia 2025"
                ])
        
        # Combine all variations and remove duplicates
        model_variations.extend(year_variations)
        model_variations = list(set([v.lower() for v in model_variations if v.strip()]))
        
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
    
    def _add_byline_to_result(self, result: Dict[str, Any], person_name: str = "") -> Dict[str, Any]:
        """
        Add byline extraction to a successful result.
        Modifies the result dictionary to include attribution_strength and actual_byline.
        """
        if result.get('success') and result.get('content'):
            try:
                # Extract actual byline from the content
                actual_byline = self._extract_byline_from_content(result['content'], result.get('url', ''))
                
                if actual_byline:
                    logger.info(f"📝 Found byline author: {actual_byline}")
                    result['actual_byline'] = actual_byline
                    
                    # Determine attribution strength if person_name provided
                    if person_name:
                        if person_name.lower() in actual_byline.lower():
                            result['attribution_strength'] = 'strong'
                            logger.info(f"✅ Strong attribution - {person_name} found in byline")
                        else:
                            result['attribution_strength'] = 'delegated'
                            logger.info(f"⚠️ Delegated content - {person_name} not in byline, actual: {actual_byline}")
                    else:
                        result['attribution_strength'] = 'unknown'
                else:
                    result['actual_byline'] = None
                    result['attribution_strength'] = 'unknown'
                    logger.info(f"❓ Could not extract byline from article")
            except Exception as e:
                logger.warning(f"Error extracting byline: {e}")
                result['actual_byline'] = None
                result['attribution_strength'] = 'unknown'
        
        return result
    
    def _extract_byline_from_content(self, html_content: str, url: str) -> Optional[str]:
        """Extract author byline from article HTML content"""
        from bs4 import BeautifulSoup
        import re
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Common byline selectors used across automotive sites
            byline_selectors = [
                '.author',
                '.byline',
                '.post-author',
                '.article-author',
                '.entry-author',
                '[class*="author"]',
                '[class*="byline"]',
                '.writer',
                '.journalist',
                'span[itemprop="author"]',
                'div[itemprop="author"]',
                'meta[name="author"]'
            ]
            
            # Try each selector
            for selector in byline_selectors:
                try:
                    if selector.startswith('meta'):
                        # Handle meta tags differently
                        element = soup.select_one(selector)
                        if element:
                            author = element.get('content', '').strip()
                            if author and len(author) > 2:
                                logger.info(f"🔍 BYLINE: Found author via {selector}: {author}")
                                return author
                    else:
                        # Handle regular elements
                        elements = soup.select(selector)
                        for element in elements:
                            text = element.get_text(strip=True)
                            if text and len(text) > 2 and len(text) < 100:  # Reasonable author name length
                                # Clean up common prefixes
                                text = re.sub(r'^(by|author|written by|story by):\s*', '', text, flags=re.IGNORECASE)
                                text = text.strip()
                                
                                # Handle "Posted:date - timeAuthor:name" format
                                if 'Posted:' in text and 'Author:' in text:
                                    # Extract just the author name after "Author:"
                                    author_match = re.search(r'Author:\s*([^,\|\n\r]+)', text)
                                    if author_match:
                                        text = author_match.group(1).strip()
                                        logger.info(f"🔍 BYLINE: Extracted author from Posted/Author format: {text}")
                                    else:
                                        # If regex fails, try to manually split on "Author:"
                                        author_parts = text.split('Author:')
                                        if len(author_parts) > 1:
                                            text = author_parts[1].strip()
                                            logger.info(f"🔍 BYLINE: Extracted author via manual split: {text}")
                                        else:
                                            # If extraction fails, skip this text to avoid saving the full string
                                            logger.warning(f"🔍 BYLINE: Could not extract author from Posted/Author format: {text}")
                                            continue
                                
                                # Only proceed if we have reasonable author text (not the full Posted string)
                                if text and not ('Posted:' in text and len(text) > 50):
                                    logger.info(f"🔍 BYLINE: Found author via {selector}: {text}")
                                    return text
                except Exception as e:
                    logger.debug(f"Error with byline selector {selector}: {e}")
                    continue
            
            # Fallback: Look for "By [Name]" patterns in text
            text_content = soup.get_text()
            by_patterns = [
                r'By\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'Written by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'Story by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'Author:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                # Add patterns to handle "Posted:date - timeAuthor:name" format
                r'PMAuthor:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'AMAuthor:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                # More flexible pattern for various author formats
                r'Author:\s*([A-Za-z]+(?:\s+[A-Za-z]+)*)'
            ]
            
            for pattern in by_patterns:
                matches = re.findall(pattern, text_content)
                if matches:
                    author = matches[0].strip()
                    if len(author) > 2:
                        logger.info(f"🔍 BYLINE: Found author via pattern {pattern}: {author}")
                        return author
            
            logger.info(f"❓ BYLINE: Could not extract author from {url}")
            return None
            
        except Exception as e:
            logger.warning(f"❌ BYLINE: Error extracting byline from {url}: {e}")
            return None 