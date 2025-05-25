from typing import Dict, List, Optional
import re
import os
import csv
from pathlib import Path

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class CrawlingStrategy:
    """Class to determine which crawling level to use for a URL."""
    
    def __init__(self):
        """Initialize the crawling strategy with default settings."""
        # Define domains that are known to require JavaScript rendering
        # But we'll still start with level 1 and escalate as needed
        self.js_likely_domains = set([
            'motortrend.com',
            'caranddriver.com',
            'roadandtrack.com',
            'jalopnik.com',
            'thedrive.com'
        ])
        
        # Only these domains will start directly at level 3 (headless)
        self.force_js_domains = set([
            # Empty for now - we want to try level 1 first for all domains
        ])
        
        self.js_required_patterns = [
            r'reviews?',
            r'test-drive',
            r'first-look'
        ]
        
        # Try to load from media_sources.csv if it exists
        self._load_domain_config()
    
    def _load_domain_config(self) -> None:
        """Load domain configuration from media_sources.csv if available."""
        try:
            project_root = Path(__file__).parent.parent.parent
            config_file = os.path.join(project_root, 'data', 'media_sources.csv')
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        domain = row.get('domain', '').strip()
                        js_mode = row.get('js_mode', '').lower()
                        force_js = row.get('force_js', '').lower() == 'true'
                        rss_url = row.get('rss_url', '')
                        
                        if domain:
                            if js_mode == 'true':
                                self.js_likely_domains.add(domain)
                                logger.info(f"Added {domain} to JS-likely domains")
                                
                                if force_js:
                                    self.force_js_domains.add(domain)
                                    logger.info(f"Added {domain} to force-JS domains (will start at level 3)")
                            
                            if rss_url:
                                logger.info(f"Configured RSS feed for {domain}: {rss_url}")
        
        except Exception as e:
            logger.warning(f"Error loading media sources configuration: {e}")
    
    def get_crawl_level(self, url: str) -> int:
        """
        Determine the starting crawling level for a URL.
        
        Args:
            url: The URL to crawl
            
        Returns:
            int: 1 for basic crawling, 2 for enhanced headers, 3 for headless browser
        """
        if not url:
            return 1
            
        # Extract domain from URL
        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if not domain_match:
            return 1
            
        domain = domain_match.group(1)
        
        # Check if domain is in force_js_domains (should start at level 3)
        for js_domain in self.force_js_domains:
            if js_domain in domain:
                logger.info(f"Domain {domain} is in force-JS list - starting at level 3")
                return 3
        
        # Otherwise, always start at level 1 (basic crawling)
        return 1
    
    def is_js_likely(self, url: str) -> bool:
        """
        Determine if a URL is likely to need JavaScript rendering.
        This is used for logging and debugging, not to determine the actual crawling level.
        
        Args:
            url: The URL to check
            
        Returns:
            bool: True if JavaScript rendering is likely needed
        """
        if not url:
            return False
            
        # Extract domain from URL
        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if not domain_match:
            return False
            
        domain = domain_match.group(1)
        
        # Check domain
        for js_domain in self.js_likely_domains:
            if js_domain in domain:
                return True
                
        # Check URL path for JS patterns
        for pattern in self.js_required_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
                
        return False
    
    def should_use_headless(self, url: str) -> bool:
        """
        Determine if headless browser should be used for a URL.
        
        Args:
            url: The URL to crawl
            
        Returns:
            bool: True if headless browser should be used
        """
        return self.get_crawl_level(url) == 3

# Create a singleton instance
crawling_strategy = CrawlingStrategy() 