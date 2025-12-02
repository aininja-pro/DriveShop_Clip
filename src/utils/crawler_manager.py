import os
import re
import time
import requests
import logging
import csv
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

# Import local modules
from src.utils.logger import setup_logger
from src.utils.escalation import crawling_strategy
from src.utils.browser_crawler import BrowserCrawler

logger = setup_logger(__name__)

class CrawlerManager:
    """
    Manages the 4-level escalation hierarchy for web crawling:
    
    Level 1: Basic requests with minimal headers
    Level 2: Enhanced headers and cookies
    Level 3: RSS feed (if available)
    Level 4: Headless browser (Playwright)
    """
    
    def __init__(self):
        """Initialize the crawler manager with necessary components."""
        self.browser_crawler = BrowserCrawler(headless=True)
        self.user_agents = {
            'basic': 'DriveShopMediaMonitorBot/1.0',
            'enhanced': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.headers_basic = {
            'User-Agent': self.user_agents['basic'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self.headers_enhanced = {
            'User-Agent': self.user_agents['enhanced'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/'
        }
        self.media_sources = self._load_media_sources()
        
    def _load_media_sources(self) -> Dict[str, Dict[str, Any]]:
        """Load media sources configuration from CSV."""
        media_sources = {}
        try:
            project_root = Path(__file__).parent.parent.parent
            config_file = os.path.join(project_root, 'data', 'media_sources.csv')
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        domain = row.get('domain', '').strip()
                        if domain:
                            media_sources[domain] = row
                            logger.debug(f"Loaded configuration for {domain}")
            return media_sources
        except Exception as e:
            logger.warning(f"Error loading media sources: {e}")
            return {}
    
    def _get_rss_url(self, url: str) -> Optional[str]:
        """Get RSS URL for a domain if available."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Strip 'www.' prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # Check if we have RSS URL for this domain
        for media_domain, config in self.media_sources.items():
            # Exact match or valid subdomain check
            if media_domain == domain or domain == media_domain or \
               (media_domain.endswith('.' + domain) and media_domain[-(len(domain)+1)] == '.') or \
               (domain.endswith('.' + media_domain) and domain[-(len(media_domain)+1)] == '.'):
                rss_url = config.get('rss_url', '')
                if rss_url:
                    logger.info(f"Found RSS URL for {domain}: {rss_url}")
                    return rss_url
        return None
        
    def crawl(self, url: str, allow_escalation: bool = True, wait_time: int = 5, vehicle_make: str = None, vehicle_model: str = None) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Crawl a URL with automatic escalation through different levels.
        
        Args:
            url: URL to crawl
            allow_escalation: Whether to allow escalation through levels
            wait_time: Time to wait for page to load (seconds)
            vehicle_make: Make of the vehicle to look for in links (if provided)
            vehicle_model: Model of the vehicle to look for in links (if provided)
            
        Returns:
            Tuple of (content, title, error, actual_url)
        """
        # First check if this is a known domain that requires a specific level
        start_level = crawling_strategy.get_crawl_level(url)
        
        # If we need to start at a higher level based on the domain, skip earlier levels
        current_level = start_level
        
        # Track the actual URL where content was found (initially the same as input URL)
        actual_url = url
        
        # Try Level 1 (Basic request) if we're starting from level 1
        if current_level == 1:
            logger.info(f"Trying Level 1 (Basic request) for {url}")
            content, title, error = self._crawl_level1(url)
            
            if content and not error:
                logger.info(f"Level 1 crawling successful for {url}")
                
                # If this is a review index page and we have vehicle information, try to find relevant article links
                if vehicle_make and vehicle_model and self._is_review_index_page(url):
                    logger.info(f"This appears to be a review index page. Looking for links about {vehicle_make} {vehicle_model}")
                    relevant_links = self._find_relevant_links(url, content, vehicle_make, vehicle_model)
                    
                    if relevant_links:
                        logger.info(f"Found {len(relevant_links)} potentially relevant links about {vehicle_make} {vehicle_model}")
                        
                        # Try each link until we find content that mentions the vehicle
                        for link_url, link_text in relevant_links:
                            logger.info(f"Crawling potentially relevant article: {link_text} at {link_url}")
                            article_content, article_title, article_error, _ = self.crawl(link_url, allow_escalation=True, wait_time=wait_time)
                            
                            if article_content and not article_error:
                                # Check if the article actually mentions the vehicle
                                if (vehicle_make.lower() in article_content.lower() and 
                                    vehicle_model.lower() in article_content.lower()):
                                    logger.info(f"Found relevant article about {vehicle_make} {vehicle_model}: {article_title}")
                                    return article_content, article_title, None, link_url
                        
                        logger.warning(f"None of the potential links contained relevant content about {vehicle_make} {vehicle_model}")
                
                return content, title, None, actual_url
            
            if not allow_escalation:
                logger.warning(f"Level 1 crawling failed and escalation is disabled: {error}")
                return None, None, error, None
                
            logger.info(f"Level 1 failed, escalating to Level 2: {error}")
            current_level = 2
        
        # Try Level 2 (Enhanced headers)
        if current_level == 2:
            logger.info(f"Trying Level 2 (Enhanced headers) for {url}")
            content, title, error = self._crawl_level2(url)
            
            if content and not error:
                logger.info(f"Level 2 crawling successful for {url}")
                
                # If this is a review index page and we have vehicle information, try to find relevant article links
                if vehicle_make and vehicle_model and self._is_review_index_page(url):
                    logger.info(f"This appears to be a review index page. Looking for links about {vehicle_make} {vehicle_model}")
                    relevant_links = self._find_relevant_links(url, content, vehicle_make, vehicle_model)
                    
                    if relevant_links:
                        logger.info(f"Found {len(relevant_links)} potentially relevant links about {vehicle_make} {vehicle_model}")
                        
                        # Try each link until we find content that mentions the vehicle
                        for link_url, link_text in relevant_links:
                            logger.info(f"Crawling potentially relevant article: {link_text} at {link_url}")
                            article_content, article_title, article_error, _ = self.crawl(link_url, allow_escalation=True, wait_time=wait_time)
                            
                            if article_content and not article_error:
                                # Check if the article actually mentions the vehicle
                                if (vehicle_make.lower() in article_content.lower() and 
                                    vehicle_model.lower() in article_content.lower()):
                                    logger.info(f"Found relevant article about {vehicle_make} {vehicle_model}: {article_title}")
                                    return article_content, article_title, None, link_url
                        
                        logger.warning(f"None of the potential links contained relevant content about {vehicle_make} {vehicle_model}")
                
                return content, title, None, actual_url
                
            if not allow_escalation:
                logger.warning(f"Level 2 crawling failed and escalation is disabled: {error}")
                return None, None, error, None
                
            logger.info(f"Level 2 failed, checking for RSS feed (Level 3): {error}")
            current_level = 3
        
        # Try Level 3 (RSS feed if available)
        if current_level == 3:
            # Check if we have RSS feed URL for this domain
            rss_url = self._get_rss_url(url)
            
            if rss_url:
                logger.info(f"Trying Level 3 (RSS feed) for {url} via {rss_url}")
                rss_content, rss_title, rss_error, found_url = self._crawl_level3_rss(rss_url, url, vehicle_make, vehicle_model)
                
                if rss_content and not rss_error:
                    logger.info(f"Level 3 (RSS) crawling successful for {url}")
                    return rss_content, rss_title, None, found_url
                
                logger.info(f"Level 3 (RSS) failed, escalating to Level 4 (Headless browser): {rss_error}")
            else:
                logger.info(f"No RSS feed configured for {url}, escalating directly to Level 4 (Headless browser)")
            
            current_level = 4
        
        # Try Level 4 (Headless browser)
        if current_level == 4:
            logger.info(f"Trying Level 4 (Headless browser) for {url}")
            content, title, error = self._crawl_level4_headless(url, wait_time=wait_time)
            
            if content and not error:
                logger.info(f"Level 4 (Headless) crawling successful for {url}")
                
                # If this is a review index page and we have vehicle information, try to find relevant article links
                if vehicle_make and vehicle_model and self._is_review_index_page(url):
                    logger.info(f"This appears to be a review index page. Looking for links about {vehicle_make} {vehicle_model}")
                    relevant_links = self._find_relevant_links(url, content, vehicle_make, vehicle_model)
                    
                    if relevant_links:
                        logger.info(f"Found {len(relevant_links)} potentially relevant links about {vehicle_make} {vehicle_model}")
                        
                        # Try each link until we find content that mentions the vehicle
                        for link_url, link_text in relevant_links:
                            logger.info(f"Crawling potentially relevant article: {link_text} at {link_url}")
                            article_content, article_title, article_error, _ = self.crawl(link_url, allow_escalation=True, wait_time=wait_time)
                            
                            if article_content and not article_error:
                                # Check if the article actually mentions the vehicle
                                if (vehicle_make.lower() in article_content.lower() and 
                                    vehicle_model.lower() in article_content.lower()):
                                    logger.info(f"Found relevant article about {vehicle_make} {vehicle_model}: {article_title}")
                                    return article_content, article_title, None, link_url
                        
                        logger.warning(f"None of the potential links contained relevant content about {vehicle_make} {vehicle_model}")
                
                return content, title, None, actual_url
        
        # If we reach here, all levels failed
        logger.error(f"All crawling levels failed for {url}")
        return None, None, "All crawling levels failed", None
    
    def _is_review_index_page(self, url: str) -> bool:
        """
        Check if a URL is likely a review index/listing page rather than a specific article.
        
        Args:
            url: URL to check
            
        Returns:
            True if it appears to be a review index page
        """
        # Common patterns for review index pages
        review_index_patterns = [
            '/reviews', 
            '/car-reviews', 
            '/road-tests', 
            '/first-drives',
            '/car-comparison-tests',
            '/news/reviews',
            '/auto-reviews'
        ]
        
        # Check if the URL contains any of these patterns but doesn't end with specific article indicators
        for pattern in review_index_patterns:
            if pattern in url:
                # Check if this is just an index page, not a specific article (which often has a date, ID, or specific name)
                is_specific_article = re.search(r'/\d{4}/', url) or re.search(r'/\d{4}-\d{2}/', url) or re.search(r'/article/', url)
                if not is_specific_article:
                    return True
                
        return False
    
    def _find_relevant_links(self, base_url: str, html_content: str, vehicle_make: str, vehicle_model: str) -> List[Tuple[str, str]]:
        """
        Extract links from HTML content and filter them for relevance to a specific vehicle.
        
        Args:
            base_url: Base URL for resolving relative links
            html_content: HTML content to parse
            vehicle_make: Vehicle make to look for (e.g., "Cadillac")
            vehicle_model: Vehicle model to look for (e.g., "Vistiq")
            
        Returns:
            List of tuples (url, link_text) for potentially relevant links
        """
        try:
            relevant_links = []
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract all links
            links = soup.find_all('a', href=True)
            
            # Filter for links that might be about the vehicle
            make_lower = vehicle_make.lower()
            model_lower = vehicle_model.lower()
            
            for link in links:
                href = link['href']
                link_text = link.get_text().strip()
                
                # Skip empty links, navigation links, etc.
                if not href or href.startswith('#') or href.startswith('javascript:'):
                    continue
                    
                # Resolve relative URLs
                full_url = urljoin(base_url, href)
                
                # Skip external domains (usually)
                if urlparse(full_url).netloc != urlparse(base_url).netloc:
                    continue
                
                # Look for relevant keywords in the link text or URL
                href_lower = href.lower()
                link_text_lower = link_text.lower()
                
                # Check for exact make/model mentions
                if ((make_lower in link_text_lower and model_lower in link_text_lower) or
                    (make_lower in href_lower and model_lower in href_lower)):
                    logger.info(f"Found highly relevant link: {link_text} -> {full_url}")
                    relevant_links.append((full_url, link_text))
                    continue
                
                # Check for possible vehicle-related keywords
                vehicle_keywords = ['review', 'test', 'drive', 'first look', 'hands-on', 'exclusive']
                
                if (model_lower in link_text_lower or model_lower in href_lower):
                    for keyword in vehicle_keywords:
                        if keyword in link_text_lower or keyword in href_lower:
                            logger.info(f"Found potentially relevant link with model mention: {link_text} -> {full_url}")
                            relevant_links.append((full_url, link_text))
                            break
            
            # Sort by relevance (exact make+model mentions first)
            def relevance_score(link_tuple):
                url, text = link_tuple
                text_lower = text.lower()
                url_lower = url.lower()
                
                score = 0
                if make_lower in text_lower and model_lower in text_lower:
                    score += 10
                elif model_lower in text_lower:
                    score += 5
                elif make_lower in text_lower:
                    score += 3
                
                vehicle_keywords = ['review', 'test', 'drive', 'first look', 'first drive']
                for keyword in vehicle_keywords:
                    if keyword in text_lower:
                        score += 2
                    if keyword in url_lower:
                        score += 1
                
                return score
                
            relevant_links.sort(key=relevance_score, reverse=True)
            
            return relevant_links
            
        except Exception as e:
            logger.error(f"Error finding relevant links: {e}")
            return []
    
    def _crawl_level1(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Level 1: Basic request with minimal headers.
        
        Args:
            url: URL to crawl
            
        Returns:
            Tuple of (content, title, error)
        """
        try:
            logger.info(f"Making Level 1 request to {url}")
            
            # Use requests with a timeout and basic headers
            response = requests.get(
                url, 
                headers=self.headers_basic,
                timeout=10,
                allow_redirects=True
            )
            
            # Check for success
            if response.status_code != 200:
                return None, None, f"HTTP error: {response.status_code}"
                
            # Extract title using regex
            title_match = re.search(r'<title[^>]*>(.*?)</title>', response.text, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else "Unknown Title"
            
            # Check if content seems empty or blocked
            if len(response.text) < 1000 or "access denied" in response.text.lower() or "403" in response.text:
                return None, None, "Content appears to be blocked or too short"
                
            return response.text, title, None
            
        except Exception as e:
            logger.error(f"Error in Level 1 crawling: {e}")
            return None, None, str(e)
    
    def _crawl_level2(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Level 2: Enhanced headers and cookies.
        
        Args:
            url: URL to crawl
            
        Returns:
            Tuple of (content, title, error)
        """
        try:
            logger.info(f"Making Level 2 request to {url}")
            
            # Create a session to maintain cookies
            session = requests.Session()
            
            # First make a request to the domain root to get cookies
            parsed_url = urlparse(url)
            domain_root = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            try:
                # Get domain root first for cookies
                session.get(domain_root, headers=self.headers_enhanced, timeout=10)
            except Exception as e:
                logger.warning(f"Could not fetch domain root for cookies: {e}")
            
            # Now fetch the actual URL with enhanced headers and any cookies received
            response = session.get(
                url, 
                headers=self.headers_enhanced,
                timeout=15,
                allow_redirects=True
            )
            
            # Check for success
            if response.status_code != 200:
                return None, None, f"HTTP error: {response.status_code}"
                
            # Extract title using regex
            title_match = re.search(r'<title[^>]*>(.*?)</title>', response.text, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else "Unknown Title"
            
            # Check if content seems empty or blocked
            if len(response.text) < 1000 or "access denied" in response.text.lower() or "403" in response.text:
                return None, None, "Content appears to be blocked or too short"
                
            return response.text, title, None
            
        except Exception as e:
            logger.error(f"Error in Level 2 crawling: {e}")
            return None, None, str(e)
    
    def _crawl_level3_rss(self, rss_url: str, original_url: str, vehicle_make: str = None, vehicle_model: str = None) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Level 3: Fetch content via RSS feed.
        
        Args:
            rss_url: RSS feed URL
            original_url: Original article URL (for domain matching)
            vehicle_make: Vehicle make to search for (optional)
            vehicle_model: Vehicle model to search for (optional)
            
        Returns:
            Tuple of (content, title, error, found_url)
        """
        try:
            logger.info(f"Fetching RSS feed from {rss_url}")
            
            response = requests.get(
                rss_url,
                headers=self.headers_basic,
                timeout=15,
                allow_redirects=True
            )
            
            if response.status_code != 200:
                return None, None, f"RSS feed HTTP error: {response.status_code}", None
                
            # Check if it's a valid XML
            if not response.content or not response.content.strip():
                return None, None, "Empty RSS feed", None
                
            try:
                # Parse the RSS feed
                soup = BeautifulSoup(response.content, 'xml')
                
                # If vehicle info is provided, try to find matching articles
                if vehicle_make and vehicle_model:
                    logger.info(f"Searching RSS feed for {vehicle_make} {vehicle_model}")
                    
                    # Handle both RSS and Atom formats
                    items = soup.find_all('item') or soup.find_all('entry')
                    
                    for item in items:
                        # Get title and description
                        title = item.find('title')
                        title_text = title.text if title else ""
                        
                        # Get description or content
                        description = item.find('description') or item.find('summary') or item.find('content')
                        description_text = description.text if description else ""
                        
                        # Get link
                        link = item.find('link')
                        link_url = link.get('href') if link and link.get('href') else link.text if link else None
                        
                        # Check if the item mentions our vehicle
                        # MUST contain the model name (more specific than just make)
                        model_in_title = vehicle_model.lower() in title_text.lower()
                        model_in_desc = vehicle_model.lower() in description_text.lower()
                        
                        if model_in_title or model_in_desc:
                            
                            logger.info(f"Found matching RSS item: {title_text}")
                            if link_url:
                                logger.info(f"Article URL: {link_url}")
                            
                            # Combine content into an HTML-like structure
                            html_content = f"<html><head><title>{title_text}</title></head><body>"
                            html_content += f"<h1>{title_text}</h1>"
                            html_content += f"<div>{description_text}</div>"
                            if link_url:
                                html_content += f"<p><a href='{link_url}'>Read Article</a></p>"
                            html_content += "</body></html>"
                            
                            return html_content, title_text, None, link_url
                            
                    logger.warning(f"No matching items found in RSS feed for {vehicle_make} {vehicle_model}")
                    return None, None, "No matching items in RSS feed", None
                    
                else:
                    # Without vehicle info, just return the first item or a summary
                    channel_title = soup.find('title')
                    channel_title_text = channel_title.text if channel_title else "RSS Feed"
                    
                    items = soup.find_all('item') or soup.find_all('entry')
                    first_link_url = None
                    
                    # Build an HTML overview of the RSS feed
                    html_content = f"<html><head><title>{channel_title_text}</title></head><body>"
                    html_content += f"<h1>{channel_title_text}</h1>"
                    
                    for item in items[:10]:  # Limit to first 10 items
                        item_title = item.find('title')
                        item_title_text = item_title.text if item_title else "Untitled"
                        
                        link = item.find('link')
                        link_url = link.get('href') if link and link.get('href') else link.text if link else None
                        
                        if link_url and not first_link_url:
                            first_link_url = link_url
                            
                        html_content += f"<h2>{item_title_text}</h2>"
                        
                        description = item.find('description') or item.find('summary') or item.find('content')
                        if description:
                            html_content += f"<div>{description.text}</div>"
                        
                        if link_url:
                            html_content += f"<p><a href='{link_url}'>Read Article</a></p>"
                    
                    html_content += "</body></html>"
                    
                    return html_content, channel_title_text, None, first_link_url
                    
            except Exception as e:
                logger.error(f"Error parsing RSS feed: {e}")
                return None, None, f"RSS parsing error: {e}", None
                
        except Exception as e:
            logger.error(f"Error fetching RSS feed: {e}")
            return None, None, str(e), None
    
    def _crawl_level4_headless(self, url: str, wait_time: int = 5) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Level 4: Headless browser using Playwright.

        Args:
            url: URL to crawl
            wait_time: Time to wait for page to load (seconds)

        Returns:
            Tuple of (content, title, error)
        """
        import asyncio
        return asyncio.run(self.browser_crawler.crawl(url, wait_time=wait_time, scroll=True))
    
    def close(self):
        """Close any open resources."""
        self.browser_crawler.close() 