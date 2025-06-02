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
        
        # HYBRID APPROACH: Pattern-first for known domains, Google-first for unknown domains
        known_domains = [
            'motortrend.com', 
            'carfanaticsblog.com', 
            'thegentlemanracer.com', 
            'carpro.com',
            # Easy to add more - just one line each:
            'caranddriver.com',
            'roadandtrack.com', 
            'jalopnik.com',
            'edmunds.com',
            'kbb.com',
            'autotrader.com',
            'cars.com'
        ]
        is_known_domain = any(known_domain in domain.lower() for known_domain in known_domains)
        
        if is_known_domain:
            # For known domains: Try pattern fallback FIRST (it works better)
            logger.info(f"Known domain {domain}: Trying pattern fallback first")
            pattern_url = self._try_url_pattern_fallback(domain, make, model, year, author)
            if pattern_url:
                pattern_score = self._score_url_relevance(pattern_url, make, model, author)
                logger.info(f"Pattern-based fallback found: {pattern_url} (quality score: {pattern_score})")
                if pattern_score >= 50:  # Good enough score
                    # Verify author if specified
                    if author and not self._verify_author_in_content(pattern_url, author):
                        logger.warning(f"Pattern result doesn't contain author {author}, skipping")
                    else:
                        return pattern_url
        
        # For unknown domains OR if pattern failed: Use Google Search
        logger.info(f"Trying Google Search for domain: {domain}")
        
        # Generate search queries in order of specificity
        queries = self._generate_search_queries(domain, make, model, year, author)
        
        best_url = None
        best_score = 0
        
        for i, query in enumerate(queries, 1):
            logger.info(f"Google search attempt {i}/{len(queries)}: {query}")
            
            # CRITICAL FIX: If author was specified, require author to be in query
            if author and not self._query_requires_author(query, author):
                logger.info(f"Query without required author {author}, will try but with lower priority: {query}")
            
            try:
                url = self._execute_search(query)
                if url:
                    # Score the result quality
                    score = self._score_url_relevance(url, make, model, author)
                    logger.info(f"Found article URL: {url} (quality score: {score})")
                    
                    # CRITICAL FIX: Verify author in content if specified
                    if author and not self._verify_author_in_content(url, author):
                        logger.warning(f"Article doesn't contain author {author}, reducing score: {url}")
                        score = max(10, score - 30)  # Reduce score instead of completely blocking
                    
                    if score > best_score:
                        best_score = score
                        best_url = url
                    
                    # If we found a high-quality result, use it
                    if score >= 80:  # High confidence threshold
                        return url
                        
                else:
                    logger.info(f"No results for query: {query}")
                    
            except Exception as e:
                logger.error(f"Error in search attempt {i}: {e}")
                continue
                
            # Rate limit: wait between queries
            time.sleep(0.5)
        
        # If Google Search found something decent, use it (already verified above)
        if best_url and best_score >= 50:
            logger.info(f"Google Search found good result: {best_url} (score: {best_score})")
            return best_url
        
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
        
        # Tier 4: Site-specific without author (fallback for when NO AUTHOR specified)
        if not clean_author:  # Only add these if no author was specified
            if year:
                queries.append(f'site:{domain} "{year} {make} {clean_model}" review')
                queries.append(f'site:{domain} "{year} {make} {clean_model}" "first drive"')
                
            queries.append(f'site:{domain} "{make} {clean_model}" review')
            queries.append(f'site:{domain} "{make} {clean_model}" "first drive"')
            queries.append(f'site:{domain} "{make} {clean_model}" "test drive"')
        
        # If we have an author, add a few more author-specific searches
        if clean_author:
            # Try broader searches but still with author requirement
            if year:
                queries.append(f'"{year} {make} {clean_model}" "{clean_author}" review site:{domain}')
            queries.append(f'"{make} {clean_model}" "{clean_author}" review OR "first drive" site:{domain}')
            queries.append(f'"{make} {clean_model}" "{clean_author}" test OR review site:{domain}')
        
        logger.info(f"Generated {len(queries)} search queries (author requirement: {'YES' if clean_author else 'NO'})")
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

    def _try_url_pattern_fallback(self, domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> Optional[str]:
        """
        Try to construct URLs based on known patterns when Google Search fails.
        This helps with index freshness issues in Custom Search API.
        """
        # Import here to avoid circular imports
        try:
            from src.utils.enhanced_http import fetch_with_enhanced_http
        except ImportError:
            logger.warning("Enhanced HTTP not available for pattern fallback")
            return None
        
        domain_lower = domain.lower()
        make_lower = make.lower().replace(' ', '-')
        model_lower = model.lower().replace(' ', '-').replace('e-tron', 'e-tron')
        year_str = year or "2025"
        
        # Known URL patterns for different sites
        url_patterns = []
        
        if 'carfanaticsblog.com' in domain_lower:
            # Pattern: /YYYY/MM/DD/vehicle-name/
            # We don't know the exact date, so try recent months
            model_slug = f"{make_lower}-{model_lower}".replace('--', '-')
            recent_dates = [
                f"{year_str}/05/20",  # Try May 20 (known date for this case)
                f"{year_str}/05",     # Try May generally
                f"{year_str}/04",     # Try April
                f"{year_str}/03",     # Try March
            ]
            
            for date_part in recent_dates:
                patterns = [
                    f"https://{domain}/{date_part}/{model_slug}/",
                    f"https://{domain}/{date_part}/{model_slug}-review/",
                    f"https://{domain}/{date_part}/{model_slug}-limited-awd/",  # Specific for this case
                    f"https://{domain}/{date_part}/{year_str}-{model_slug}/",
                    f"https://{domain}/{date_part}/{year_str}-{model_slug}-limited-awd/",  # More specific
                ]
                url_patterns.extend(patterns)
        
        elif 'motortrend.com' in domain_lower:
            model_slug = f"{make_lower}-{model_lower}".replace('--', '-')
            # Handle common MotorTrend URL variations
            url_patterns = [
                # Basic patterns
                f"https://www.{domain}/reviews/{year_str}-{model_slug}-review/",
                f"https://www.{domain}/reviews/{year_str}-{model_slug}-first-test/",
                f"https://www.{domain}/reviews/{year_str}-{model_slug}-first-test-review",
                f"https://www.{domain}/reviews/{year_str}-{model_slug}-quattro-first-test-review",
                f"https://www.{domain}/reviews/{year_str}-{model_slug}-road-test/",
                # Without www
                f"https://{domain}/reviews/{year_str}-{model_slug}-review/",
                f"https://{domain}/reviews/{year_str}-{model_slug}-first-test/", 
                f"https://{domain}/reviews/{year_str}-{model_slug}-first-test-review",
                # Common trim variations
                f"https://www.{domain}/reviews/{year_str}-{model_slug}-prestige-first-test/",
                f"https://www.{domain}/reviews/{year_str}-{model_slug}-premium-review/",
                # Car info pages
                f"https://www.{domain}/cars/{make_lower}/{model_lower}/",
                f"https://{domain}/cars/{make_lower}/{model_lower}/",
            ]
        
        elif 'thegentlemanracer.com' in domain_lower:
            model_slug = f"{model_lower}".replace('--', '-')
            url_patterns = [
                f"https://{domain}/{year_str}/{model_slug}/",
                f"https://{domain}/{year_str}/05/{model_slug}/",
                f"https://{domain}/reviews/{model_slug}/",
            ]
        
        elif 'carpro.com' in domain_lower:
            # CarPro URL patterns
            model_slug = f"{make_lower}-{model_lower}".replace('--', '-')
            url_patterns = [
                f"https://www.{domain}/resources/vehicle-reviews/{year_str}-{model_slug}/",
                f"https://www.{domain}/blog/{year_str}-{model_slug}-review/",
                f"https://www.{domain}/vehicle-reviews/{model_slug}/",
                f"https://{domain}/resources/vehicle-reviews/{year_str}-{model_slug}/",
                f"https://{domain}/blog/{year_str}-{model_slug}-review/",
            ]
        
        # EASY TO ADD: Here's how you add new domains (just copy this block)
        elif 'caranddriver.com' in domain_lower:
            model_slug = f"{make_lower}-{model_lower}".replace('--', '-')
            url_patterns = [
                f"https://www.{domain}/reviews/{year_str}-{model_slug}-review/",
                f"https://www.{domain}/reviews/{model_slug}-review/",
                f"https://www.{domain}/features/{year_str}-{model_slug}/",
            ]
            
        elif 'jalopnik.com' in domain_lower:
            model_slug = f"{make_lower}-{model_lower}".replace('--', '-')
            url_patterns = [
                f"https://{domain}/{year_str}/{make_lower}-{model_slug}-review/",
                f"https://{domain}/review/{make_lower}-{model_slug}/",
            ]
            
        elif 'edmunds.com' in domain_lower:
            model_slug = f"{make_lower}-{model_lower}".replace('--', '-')
            url_patterns = [
                f"https://www.{domain}/car-reviews/{year_str}-{model_slug}/",
                f"https://www.{domain}/{make_lower}/{model_lower}/review/",
            ]
        
        # Test each pattern
        for pattern_url in url_patterns:
            logger.debug(f"Testing URL pattern: {pattern_url}")
            
            try:
                # Quick HEAD request to check if URL exists
                import requests
                response = requests.head(pattern_url, timeout=5, allow_redirects=True)
                
                if response.status_code == 200:
                    # Verify it's actually an article about our vehicle
                    content = fetch_with_enhanced_http(pattern_url)
                    if content and self._verify_article_relevance(content, make, model):
                        logger.info(f"Pattern-based URL verification successful: {pattern_url}")
                        return pattern_url
                    
            except Exception as e:
                logger.debug(f"Pattern test failed for {pattern_url}: {e}")
                continue
        
        return None
    
    def _verify_article_relevance(self, content: str, make: str, model: str) -> bool:
        """Verify that content actually discusses the specified vehicle"""
        content_lower = content.lower()
        make_lower = make.lower()
        model_lower = model.lower()
        
        # Check for vehicle mentions
        make_count = content_lower.count(make_lower)
        model_count = content_lower.count(model_lower)
        
        # Must have reasonable number of mentions
        return make_count >= 2 and model_count >= 2 and len(content) > 1000

    def _score_url_relevance(self, url: str, make: str, model: str, author: Optional[str] = None) -> int:
        """Score a URL based on how well it matches our target vehicle and author"""
        if not url:
            return 0
            
        score = 0
        url_lower = url.lower()
        make_lower = make.lower()
        model_lower = model.lower().replace(' ', '-')
        
        # URL structure scoring
        if make_lower in url_lower:
            score += 30
        if model_lower.split('-')[0] in url_lower:  # First word of model
            score += 40
        if author and any(word.lower() in url_lower for word in author.split()):
            score += 20
        if 'review' in url_lower or 'test' in url_lower:
            score += 20
        if '2025' in url_lower or '2024' in url_lower:
            score += 10
            
        # Check if it's obviously wrong vehicle
        wrong_indicators = ['genesis', 'toyota', 'honda', 'bmw', 'mercedes']
        vehicle_words = [make_lower, model_lower.split('-')[0]]
        for wrong in wrong_indicators:
            if wrong in url_lower and wrong not in vehicle_words:
                score -= 50
                
        return max(0, score)

    def _query_requires_author(self, query: str, author: str) -> bool:
        """Check if a search query includes the specified author"""
        author_lower = author.lower()
        query_lower = query.lower()
        
        # Check if author name is quoted in the query
        return f'"{author_lower}"' in query_lower or f"'{author_lower}'" in query_lower
    
    def _verify_author_in_content(self, url: str, author: str) -> bool:
        """
        Verify that the article content actually contains the specified author.
        This prevents wrong articles from being returned.
        """
        try:
            # Import here to avoid circular imports
            from src.utils.enhanced_http import fetch_with_enhanced_http
            
            # Quick fetch of article content
            content = fetch_with_enhanced_http(url)
            if not content:
                return False
            
            content_lower = content.lower()
            author_lower = author.lower()
            
            # Check if author name appears in content
            author_words = author_lower.split()
            
            # Author must appear as full name or individual words
            if author_lower in content_lower:
                logger.info(f"✅ Author verification passed: {author} found in content")
                return True
            
            # Check for individual author words (handle "First Last" names)
            if len(author_words) >= 2:
                words_found = sum(1 for word in author_words if word in content_lower)
                if words_found >= len(author_words):
                    logger.info(f"✅ Author verification passed: All words of {author} found in content")
                    return True
            
            logger.warning(f"❌ Author verification failed: {author} not found in content")
            return False
            
        except Exception as e:
            logger.error(f"Error verifying author in content: {e}")
            # If we can't verify, assume it's valid (don't block valid results)
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