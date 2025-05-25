import os
import requests
import logging
from typing import Optional, List
from urllib.parse import urlparse
import time

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class GoogleSearchClient:
    """Google Custom Search API client with graduated fallback queries"""
    
    def __init__(self):
        self.api_key = os.environ.get('GOOGLE_SEARCH_API_KEY')
        self.search_engine_id = os.environ.get('GOOGLE_SEARCH_ENGINE_ID')
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        
        if not self.api_key:
            logger.warning("GOOGLE_SEARCH_API_KEY not found in environment variables")
        if not self.search_engine_id:
            logger.warning("GOOGLE_SEARCH_ENGINE_ID not found in environment variables")
    
    def search_for_article(self, domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> Optional[str]:
        """
        Search for a specific vehicle review article using graduated fallback queries.
        
        Args:
            domain: Target domain (e.g., "motortrend.com")
            make: Vehicle make (e.g., "Audi")
            model: Vehicle model (e.g., "Q6 e-tron Prestige") 
            year: Vehicle year (e.g., "2024"), optional
            author: Author/journalist name (e.g., "Alexander Stoklosa"), optional
            
        Returns:
            Best matching article URL or None if not found
        """
        if not self.api_key or not self.search_engine_id:
            logger.error("Google Search API not configured properly")
            return None
        
        # Generate search queries in order of specificity
        queries = self._generate_search_queries(domain, make, model, year, author)
        
        for i, query in enumerate(queries, 1):
            logger.info(f"Google search attempt {i}/{len(queries)}: {query}")
            
            try:
                url = self._execute_search(query)
                if url:
                    logger.info(f"Found article URL: {url}")
                    return url
                else:
                    logger.info(f"No results for query: {query}")
                    
            except Exception as e:
                logger.error(f"Error in search attempt {i}: {e}")
                continue
                
            # Rate limit: wait between queries
            time.sleep(0.5)
        
        logger.warning(f"No articles found for {make} {model} by {author or 'any author'} on {domain}")
        return None
    
    def _generate_search_queries(self, domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> List[str]:
        """Generate graduated search queries from specific to broad"""
        queries = []
        
        # Clean up model name for search
        clean_model = model.replace(" Prestige", "").replace(" Premium", "").strip()
        
        # Clean up author name if provided
        clean_author = author.strip() if author else None
        
        # Tier 1: Hyper-specific with author, year, and site restriction
        if clean_author and year:
            queries.append(f'site:{domain} "{year} {make} {clean_model}" "{clean_author}" review')
            queries.append(f'site:{domain} "{year} {make} {clean_model}" "{clean_author}" "first drive"')
        
        # Tier 2: Author + vehicle + site (without year)
        if clean_author:
            queries.append(f'site:{domain} "{make} {clean_model}" "{clean_author}" review')
            queries.append(f'site:{domain} "{make} {clean_model}" "{clean_author}" "first drive"')
            queries.append(f'site:{domain} "{make} {clean_model}" "{clean_author}" "test drive"')
        
        # Tier 3: Site-specific without author (fallback)
        if year:
            queries.append(f'site:{domain} "{year} {make} {clean_model}" review')
            queries.append(f'site:{domain} "{year} {make} {clean_model}" "first drive"')
            
        queries.append(f'site:{domain} "{make} {clean_model}" review')
        queries.append(f'site:{domain} "{make} {clean_model}" "first drive"')
        queries.append(f'site:{domain} "{make} {clean_model}" "test drive"')
        
        # Tier 4: Drop site restriction - search entire web with author
        if clean_author:
            if year:
                queries.append(f'"{year} {make} {clean_model}" "{clean_author}" review')
            queries.append(f'"{make} {clean_model}" "{clean_author}" review')
            queries.append(f'"{make} {clean_model}" "{clean_author}" "first drive"')
        
        # Tier 5: Final fallback without author
        if year:
            queries.append(f'"{year} {make} {clean_model}" review')
        queries.append(f'"{make} {clean_model}" review')
        queries.append(f'"{make} {clean_model}" "first drive"')
        
        return queries
    
    def _execute_search(self, query: str) -> Optional[str]:
        """Execute a single Google search and return the best matching URL"""
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'num': 5  # Get top 5 results
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'items' not in data:
                return None
            
            # Return the first result that looks like an article
            for item in data['items']:
                url = item.get('link', '')
                title = item.get('title', '')
                
                # Validate this looks like an article URL
                if self._is_article_url(url, title):
                    return url
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error in Google search: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Google search: {e}")
            return None
    
    def _is_article_url(self, url: str, title: str) -> bool:
        """Check if a URL and title look like a legitimate article"""
        if not url:
            return False
            
        # Parse URL
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
        except:
            return False
        
        # Skip obvious non-article pages
        skip_patterns = [
            '/search', '/category', '/tag', '/author',
            '/page/', '/index', '/sitemap', '/feed',
            '.pdf', '.jpg', '.png', '.gif'
        ]
        
        for pattern in skip_patterns:
            if pattern in path:
                return False
        
        # Look for article indicators in path or title
        article_indicators = [
            'review', 'first-drive', 'test-drive', 'road-test',
            'drive', 'test', 'preview', 'comparison'
        ]
        
        content_text = (path + ' ' + title.lower())
        
        for indicator in article_indicators:
            if indicator in content_text:
                return True
        
        # If no clear indicators but it's not in skip list, consider it valid
        return True

# Convenience function for easy importing
def google_search_for_article(domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> Optional[str]:
    """
    Convenience function to search for a vehicle article.
    
    Args:
        domain: Target domain (e.g., "motortrend.com")
        make: Vehicle make (e.g., "Audi")
        model: Vehicle model (e.g., "Q6 e-tron")
        year: Vehicle year (optional)
        author: Author/journalist name (optional)
        
    Returns:
        Article URL or None
    """
    client = GoogleSearchClient()
    return client.search_for_article(domain, make, model, year, author) 