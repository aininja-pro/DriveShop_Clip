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
        
        # Tier 1: Author + vehicle + site (HIGHEST PRIORITY - author-specific reviews)
        if clean_author:
            queries.append(f'site:{domain} "{make} {clean_model}" "{clean_author}" inurl:{clean_model.split()[0].lower()}')
            if year:
                queries.append(f'site:{domain} "{year} {make} {clean_model}" "{clean_author}" review')
                queries.append(f'site:{domain} "{year} {make} {clean_model}" "{clean_author}" "first test"')
            queries.append(f'site:{domain} "{make} {clean_model}" "{clean_author}" review')
            queries.append(f'site:{domain} "{make} {clean_model}" "{clean_author}" "first test"')
        
        # Tier 2: Try exact article title format (without author)
        if year:
            queries.append(f'site:{domain} "{year} {make} {clean_model} Review"')
            queries.append(f'site:{domain} "{year} {make} {clean_model}" "Review:"')
        queries.append(f'site:{domain} "{make} {clean_model} Review:"')
        queries.append(f'site:{domain} "{make} {clean_model} Review"')
        
        # Tier 3: Exclude template content explicitly  
        if year:
            queries.append(f'site:{domain} "{year} {make} {clean_model}" -"Related Posts" -"Recent Posts"')
        queries.append(f'site:{domain} "{make} {clean_model}" -"Related Posts" -"Recent Posts" review')
        
        # Tier 4: Site-specific without author (fallback)
        if year:
            queries.append(f'site:{domain} "{year} {make} {clean_model}" review')
            queries.append(f'site:{domain} "{year} {make} {clean_model}" "first drive"')
            
        queries.append(f'site:{domain} "{make} {clean_model}" review')
        queries.append(f'site:{domain} "{make} {clean_model}" "first drive"')
        queries.append(f'site:{domain} "{make} {clean_model}" "test drive"')
        
        # Tier 5: Drop site restriction - search entire web with author
        if clean_author:
            if year:
                queries.append(f'"{year} {make} {clean_model}" "{clean_author}" review')
            queries.append(f'"{make} {clean_model}" "{clean_author}" review')
            queries.append(f'"{make} {clean_model}" "{clean_author}" "first drive"')
        
        # Tier 6: Final fallback without author
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
            
            # Extract search terms for better matching
            search_terms = self._extract_search_terms(query)
            
            # Score and rank results
            scored_results = []
            for item in data['items']:
                url = item.get('link', '')
                title = item.get('title', '')
                snippet = item.get('snippet', '')
                
                if self._is_article_url(url, title):
                    score = self._score_result(title, snippet, search_terms)
                    scored_results.append((score, url, title))
                    logger.info(f"Candidate: {title} | Score: {score} | URL: {url}")
            
            # Return the highest scoring result
            if scored_results:
                scored_results.sort(key=lambda x: x[0], reverse=True)
                best_score, best_url, best_title = scored_results[0]
                logger.info(f"Selected best result: {best_title} (score: {best_score})")
                return best_url
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error in Google search: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Google search: {e}")
            return None
    
    def _extract_search_terms(self, query: str) -> dict:
        """Extract key search terms from the query"""
        import re
        
        # Extract quoted terms
        quoted_terms = re.findall(r'"([^"]*)"', query)
        
        # Extract vehicle info
        make = model = author = None
        for term in quoted_terms:
            term_lower = term.lower()
            if any(make_word in term_lower for make_word in ['audi', 'vw', 'volkswagen', 'bmw', 'mercedes', 'toyota', 'honda', 'ford']):
                if 'jetta' in term_lower or 'q6' in term_lower or 'civic' in term_lower:
                    model = term
                else:
                    make = term
            elif 'review' not in term_lower and 'drive' not in term_lower and len(term.split()) >= 2:
                author = term
                
        return {
            'make': make,
            'model': model, 
            'author': author,
            'all_quoted': quoted_terms
        }
    
    def _score_result(self, title: str, snippet: str, search_terms: dict) -> int:
        """Score a search result based on how well it matches our criteria"""
        score = 0
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        
        # HIGHEST PRIORITY: Actual review URLs (strongly prefer these)
        if '/review' in snippet_lower or '/first-test' in snippet_lower or '/road-test' in snippet_lower:
            score += 200
            logger.debug(f"Review URL bonus: +200")
        
        # HIGH PRIORITY: Vehicle mentioned in title (not just sidebar)
        if search_terms.get('model'):
            model_lower = search_terms['model'].lower()
            model_words = model_lower.replace('"', '').split()
            title_matches = sum(1 for word in model_words if word in title_lower)
            if title_matches >= len(model_words) * 0.7:  # 70% of model words in title
                score += 100
                logger.debug(f"Title match bonus: +100 for {search_terms['model']}")
        
        # MEDIUM PRIORITY: Author in title, snippet, or URL path
        if search_terms.get('author'):
            author_lower = search_terms['author'].lower().replace('"', '')
            author_words = author_lower.split()
            
            # Check for author in title
            if any(word in title_lower for word in author_words):
                score += 75
                logger.debug(f"Author in title bonus: +75")
            # Check for author in snippet
            elif any(word in snippet_lower for word in author_words):
                score += 50
                logger.debug(f"Author in snippet bonus: +50")
        
        # BONUS: Article type indicators in title
        article_indicators = ['review', 'first test', 'first drive', 'test drive', 'road test']
        for indicator in article_indicators:
            if indicator in title_lower:
                score += 50  # Increased from 20
                logger.debug(f"Article type bonus: +50 for '{indicator}'")
        
        # PENALTY: Specs/comparison pages (not actual reviews)
        specs_indicators = [
            'expert insights, pricing, and trims',
            'pricing and trims',
            'msrp',
            'specifications',
            'compare',
            'top competitors'
        ]
        for indicator in specs_indicators:
            if indicator in title_lower or indicator in snippet_lower:
                score -= 150  # Heavy penalty for specs pages
                logger.debug(f"Specs page penalty: -150 for '{indicator}'")
        
        # PENALTY: Signs this is sidebar/template content
        template_indicators = [
            'related posts', 'recent posts', 'you may also like',
            'more stories', 'other articles', 'similar content'
        ]
        for indicator in template_indicators:
            if indicator in snippet_lower:
                score -= 50
                logger.debug(f"Template content penalty: -50 for '{indicator}'")
        
        # PENALTY: Wrong vehicle in title (false positive)
        wrong_vehicles = ['dodge', 'charger', 'camaro', 'mustang', 'bmw', 'lexus']
        if search_terms.get('model') and 'jetta' in search_terms['model'].lower():
            for wrong in wrong_vehicles:
                if wrong in title_lower:
                    score -= 200  # Heavy penalty
                    logger.debug(f"Wrong vehicle penalty: -200 for '{wrong}'")
        
        # BONUS: Recent publication (if available)
        if 'days ago' in snippet_lower or '2025' in title_lower:
            score += 10
            logger.debug(f"Recent article bonus: +10")
        
        # BONUS: Long content snippets (indicate substantial articles)
        if len(snippet_lower) > 200:
            score += 15
            logger.debug(f"Long snippet bonus: +15")
            
        return score
    
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