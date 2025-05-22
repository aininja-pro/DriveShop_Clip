import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Generator, Optional

import scrapy
from scrapy.http import Response, Request

from crawler.items import LoanItem


class LoanSpider(scrapy.Spider):
    name = 'loan_spider'
    allowed_domains = []  # Will be set dynamically based on URLs
    start_urls = []  # Will be set dynamically based on input data

    def __init__(self, loans_data: List[Dict[str, Any]] = None, *args, **kwargs):
        """
        Initialize the loan spider with loan data.
        
        Args:
            loans_data: List of dictionaries containing loan information
        """
        super(LoanSpider, self).__init__(*args, **kwargs)
        
        # Initialize empty if not provided
        self.loans_data = loans_data or []
        
        # Generate allowed domains from loans data
        if self.loans_data:
            domains = set()
            for loan in self.loans_data:
                for url in loan.get('urls', []):
                    if url:
                        domain = self._extract_domain(url)
                        if domain:
                            domains.add(domain)
            
            self.allowed_domains = list(domains)
    
    def start_requests(self) -> Generator[Request, None, None]:
        """Generate initial requests from loans data"""
        for loan in self.loans_data:
            for url in loan.get('urls', []):
                if url:
                    # Add loan data to request meta for later reference
                    yield Request(
                        url=url,
                        callback=self.parse,
                        meta={
                            'loan_data': loan,
                            'url': url,
                            'crawl_level': 1  # Start with level 1 crawling
                        },
                        errback=self.handle_error
                    )
    
    def parse(self, response: Response) -> Generator[LoanItem, None, None]:
        """
        Parse the response and extract content.
        
        Args:
            response: The response object from Scrapy
        
        Yields:
            LoanItem with extracted content
        """
        # Extract loan data from meta
        loan_data = response.meta.get('loan_data', {})
        url = response.meta.get('url', response.url)
        crawl_level = response.meta.get('crawl_level', 1)
        
        # Get make and model for content extraction
        make = loan_data.get('make', '')
        model = loan_data.get('model', '')
        
        # Extract title
        title = self._extract_title(response)
        
        # Extract main content
        content = self._extract_content(response, make, model)
        
        # Extract publication date if available
        publication_date = self._extract_date(response)
        
        # Create and yield the item
        item = LoanItem(
            work_order=loan_data.get('work_order', ''),
            make=make,
            model=model,
            source=loan_data.get('source', ''),
            url=url,
            content=content,
            title=title,
            publication_date=publication_date,
            content_type='article',
            crawl_date=datetime.now().isoformat(),
            crawl_level=crawl_level
        )
        
        yield item
        
        # If we couldn't find any content relevant to the make/model,
        # and we're on a homepage or general page, try to discover relevant pages
        if not self._content_mentions_vehicle(content, make, model) and crawl_level == 1:
            yield from self._discover_relevant_pages(response, loan_data)
    
    def _discover_relevant_pages(self, response: Response, loan_data: Dict[str, Any]) -> Generator[Request, None, None]:
        """
        Discover and follow links that might contain relevant content.
        
        Args:
            response: The response object from Scrapy
            loan_data: Loan data dictionary
        
        Yields:
            Requests for discovered pages
        """
        make = loan_data.get('make', '')
        model = loan_data.get('model', '')
        
        # Look for links containing make/model names
        make_model_pattern = rf'({re.escape(make)}|{re.escape(model)})'
        
        # Look for typical review section links
        review_patterns = [
            r'review', r'test.drive', r'road.test', 
            r'first.look', r'first.drive', r'comparison'
        ]
        
        # Combine patterns
        patterns = [make_model_pattern] + review_patterns
        
        # Find links matching our patterns
        discovered_links = []
        for pattern in patterns:
            links = response.css('a::attr(href)').re(pattern)
            discovered_links.extend(links)
        
        # Also look for links to common content sections
        section_links = response.css('a[href*="review"], a[href*="blog"], a[href*="news"]::attr(href)').getall()
        discovered_links.extend(section_links)
        
        # Deduplicate and filter out media files
        discovered_links = list(set(discovered_links))
        discovered_links = [link for link in discovered_links if not self._is_media_file(link)]
        
        # Limit to top 5 most promising links
        discovered_links = discovered_links[:5]
        
        # Follow discovered links
        for link in discovered_links:
            full_url = response.urljoin(link)
            yield Request(
                url=full_url,
                callback=self.parse,
                meta={
                    'loan_data': loan_data,
                    'url': full_url,
                    'crawl_level': 2  # These are level 2 (discovered) links
                }
            )
    
    def handle_error(self, failure):
        """Handle request failures"""
        # Extract original request and loan data
        request = failure.request
        loan_data = request.meta.get('loan_data', {})
        
        # Log the error
        self.logger.error(f"Error crawling {request.url}: {failure.value}")
        
        # Create an error item
        item = LoanItem(
            work_order=loan_data.get('work_order', ''),
            make=loan_data.get('make', ''),
            model=loan_data.get('model', ''),
            source=loan_data.get('source', ''),
            url=request.url,
            content='',
            title='',
            content_type='error',
            crawl_date=datetime.now().isoformat(),
            crawl_level=request.meta.get('crawl_level', 1),
            error=str(failure.value)
        )
        
        return item
    
    def _extract_title(self, response: Response) -> str:
        """Extract the title from the response"""
        # Try common title selectors
        title = response.css('title::text').get() or ''
        
        # If that didn't work, try article heading
        if not title:
            title = response.css('h1::text').get() or ''
        
        return title.strip()
    
    def _extract_content(self, response: Response, make: str, model: str) -> str:
        """
        Extract the main content from the response.
        
        Args:
            response: The response object
            make: Vehicle make to look for
            model: Vehicle model to look for
            
        Returns:
            Extracted content as a string
        """
        # Try common content selectors for article bodies
        content = ''
        
        # First try common article content selectors
        selectors = [
            'article', 
            'div.content', 
            'div.article-content',
            'div.post-content',
            'div.entry-content',
            'div.main-content',
            '.story'
        ]
        
        for selector in selectors:
            content_elements = response.css(f'{selector} p::text').getall()
            if content_elements:
                content = ' '.join([p.strip() for p in content_elements])
                break
        
        # If no content found, try a more generic approach
        if not content:
            # Get all paragraphs
            all_paragraphs = response.css('p::text').getall()
            content = ' '.join([p.strip() for p in all_paragraphs if p.strip()])
        
        # If still no content, get all text from the body
        if not content:
            body_text = response.css('body ::text').getall()
            content = ' '.join([t.strip() for t in body_text if t.strip()])
        
        return content
    
    def _extract_date(self, response: Response) -> Optional[str]:
        """Extract the publication date if available"""
        # Try common date meta tags
        date = response.css('meta[property="article:published_time"]::attr(content)').get()
        if not date:
            date = response.css('meta[name="pubdate"]::attr(content)').get()
        
        # Try common date HTML elements
        if not date:
            date_text = response.css('.date::text, .publish-date::text, time::text').get()
            if date_text:
                # Simple parsing could be enhanced with dateutil.parser
                date = date_text.strip()
        
        return date
    
    def _content_mentions_vehicle(self, content: str, make: str, model: str) -> bool:
        """Check if content mentions the vehicle make and model"""
        if not content or not make or not model:
            return False
        
        content_lower = content.lower()
        make_lower = make.lower()
        model_lower = model.lower()
        
        # Check for make and model mentions
        return make_lower in content_lower and model_lower in content_lower
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            return parsed_url.netloc
        except Exception as e:
            self.logger.error(f"Error extracting domain from {url}: {e}")
            return None
    
    def _is_media_file(self, url: str) -> bool:
        """Check if URL points to a media file"""
        media_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.pdf']
        return any(url.lower().endswith(ext) for ext in media_extensions) 