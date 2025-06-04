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

        # NEW: Tier 1.5: Index Page Discovery (When Google Search fails)
        logger.info(f"Tier 1.5: Google Search failed, trying Index Page Discovery for {make} {model}")
        index_discovery_result = self._try_index_page_discovery(url, make, model, person_name, domain)
        if index_discovery_result and index_discovery_result['success']:
            logger.info(f"Tier 1.5 Success: Index Page Discovery found specific article")
            result = index_discovery_result.copy()
            result.update({
                'tier_used': 'Tier 1.5: Index Discovery + ' + index_discovery_result.get('tier_used', 'Unknown'),
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
            logger.info(f"🎯 Trying article: {article_title} (score: {score}) - {article_url}")
            
            article_result = self._crawl_specific_url(article_url, make, model)
            if article_result['success']:
                logger.info(f"✅ Successfully crawled specific article: {article_url}")
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
                logger.warning(f"❌ Failed to crawl article: {article_url}")
                
        logger.warning(f"❌ All relevant articles failed to crawl")
        return None

    def _scrape_index_page(self, index_url: str) -> Optional[str]:
        """Scrape the index page content using our available methods"""
        
        # Try Enhanced HTTP first (fast and free)
        logger.info(f"Trying Enhanced HTTP for index page: {index_url}")
        content = self.enhanced_http.fetch_url(index_url)
        if content and len(content) > 1000:  # Reasonable content size
            logger.info(f"✅ Enhanced HTTP got index page ({len(content)} chars)")
            return content
            
        # Try ScrapingBee if Enhanced HTTP fails
        logger.info(f"Enhanced HTTP failed, trying ScrapingBee for index page: {index_url}")
        content = self.scraping_bee.scrape_url(index_url)
        if content and len(content) > 1000:
            logger.info(f"✅ ScrapingBee got index page ({len(content)} chars)")
            return content
            
        logger.warning(f"❌ Both Enhanced HTTP and ScrapingBee failed for index page")
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
                '.title a[href]'
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
                
            return links[:50]  # Limit to top 50 links to avoid overwhelming
            
        except Exception as e:
            logger.error(f"❌ Error extracting article links: {e}")
            return []

    def _find_relevant_articles(self, article_links: List[str], make: str, model: str, person_name: str) -> List[tuple]:
        """Find articles relevant to the vehicle make/model (like searching YouTube transcripts)"""
        relevant_articles = []
        
        # Use hierarchical model search (like our Google Search)
        model_variations = self._generate_model_variations(model)
        logger.info(f"🔍 Searching with model variations: {model_variations}")
        logger.info(f"🔍 DEBUG: Looking for articles about {make} {model} from {len(article_links)} total links")
        
        for i, article_url in enumerate(article_links):
            try:
                logger.info(f"🔍 DEBUG: Processing article {i+1}/{len(article_links)}: {article_url}")
                
                # Score the URL and title for relevance
                score = self._score_article_relevance(article_url, make, model_variations, person_name)
                
                if score > 0:  # Only include potentially relevant articles
                    # Extract title from URL for display
                    title = self._extract_title_from_url(article_url)
                    relevant_articles.append((score, article_url, title))
                    logger.info(f"📰 Relevant: {title} (score: {score})")
                else:
                    logger.info(f"❌ DEBUG: Article scored {score}, not relevant: {article_url}")
                    
            except Exception as e:
                logger.warning(f"❌ Error scoring article {article_url}: {e}")
                
        # Sort by relevance score (highest first)
        relevant_articles.sort(key=lambda x: x[0], reverse=True)
        
        logger.info(f"🔍 DEBUG: Final relevant articles for {make} {model}:")
        for i, (score, url, title) in enumerate(relevant_articles[:5]):
            logger.info(f"  {i+1}. Score: {score}, Title: {title}, URL: {url}")
            
        return relevant_articles[:10]  # Return top 10 most relevant

    def _generate_model_variations(self, model: str) -> List[str]:
        """Generate model variations for searching (reuse hierarchical logic)"""
        if not model or not model.strip():
            return [""]
        
        model = model.strip()
        variations = [model]  # Start with full model
        
        # Split by common separators and create variations
        words = model.replace('-', ' ').replace('_', ' ').split()
        
        # Add progressively shorter variations
        for i in range(len(words) - 1, 0, -1):
            variation = ' '.join(words[:i])
            if variation not in variations and len(variation) >= 2:
                variations.append(variation)
                
        return variations

    def _score_article_relevance(self, url: str, make: str, model_variations: List[str], person_name: str) -> int:
        """Score how relevant an article URL is to our search (like scoring YouTube videos)"""
        import re
        
        score = 0
        url_lower = url.lower()
        
        # DEBUG: Log what we're trying to match
        logger.info(f"🔍 Scoring URL for model variations {model_variations}: {url}")
        
        # HIGH SCORE: Make mentioned in URL
        if make.lower() in url_lower:
            score += 100
            logger.info(f"✅ Make '{make}' found in URL, +100 score")
            
        # HIGH SCORE: Exact model variation match in URL
        model_matched = False
        for model_var in model_variations:
            if not model_var or len(model_var.strip()) < 2:
                continue
                
            model_lower = model_var.lower().strip()
            logger.info(f"🔍 Trying to match model variation: '{model_var}' against URL: {url}")
            
            # For hyphenated models like "cx-5", "cx-90", we need exact matching
            # Create pattern that matches the exact model with word boundaries
            if '-' in model_lower:
                # For hyphenated models, ensure exact match with boundaries
                pattern = r'\b' + re.escape(model_lower) + r'\b'
                logger.info(f"🔍 Using hyphenated pattern: {pattern}")
                if re.search(pattern, url_lower):
                    score += 200
                    model_matched = True
                    logger.info(f"✅ Exact hyphenated model match: '{model_var}' found in {url}, +200 score")
                    break
                else:
                    logger.info(f"❌ Hyphenated pattern '{pattern}' did NOT match in '{url_lower}'")
            else:
                # For non-hyphenated models, use flexible word boundary matching
                pattern = r'\b' + re.escape(model_lower.replace(' ', r'[-\s_]*')) + r'\b'
                logger.info(f"🔍 Using flexible pattern: {pattern}")
                if re.search(pattern, url_lower):
                    score += 200
                    model_matched = True
                    logger.info(f"✅ Model match: '{model_var}' found in {url}, +200 score")
                    break
                else:
                    logger.info(f"❌ Flexible pattern '{pattern}' did NOT match in '{url_lower}'")
                        
        if not model_matched:
            logger.info(f"❌ No model match for {model_variations} in {url}")
                
        # MEDIUM SCORE: Review/test keywords in URL
        review_keywords = ['review', 'test', 'drive', 'first', 'road', 'preview']
        for keyword in review_keywords:
            if keyword in url_lower:
                score += 50
                logger.info(f"✅ Review keyword '{keyword}' found, +50 score")
                break
                
        # BONUS: Author/person name in URL
        if person_name and person_name.lower().replace(' ', '-') in url_lower:
            score += 75
            logger.info(f"✅ Author '{person_name}' found, +75 score")
            
        # BONUS: Year indicators
        for year in ['2024', '2025', '2026']:
            if year in url_lower:
                score += 25
                logger.info(f"✅ Year '{year}' found, +25 score")
                break
                
        # PENALTY: Category/tag pages
        penalty_patterns = ['/category/', '/tag/', '/author/', '/search', '/archive', '/page/']
        for pattern in penalty_patterns:
            if pattern in url_lower:
                score -= 150
                logger.info(f"❌ Penalty pattern '{pattern}' found, -150 score")
                
        logger.info(f"🎯 Final score for {url}: {score}")
        return score

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