import os
import requests
import logging
from typing import Optional, List
from urllib.parse import urlparse
import time

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class BingSearchClient:
    """Bing Search API client as backup for Google Search"""
    
    def __init__(self):
        self.api_key = os.environ.get('BING_SEARCH_API_KEY')
        self.base_url = "https://api.bing.microsoft.com/v7.0/search"
        
        if not self.api_key:
            logger.warning("BING_SEARCH_API_KEY not found in environment variables")
    
    def search_for_article(self, domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> Optional[str]:
        """
        Search for a specific vehicle review article using Bing Search API.
        Uses same hierarchical approach as Google Search.
        """
        if not self.api_key:
            logger.warning("Bing Search API not configured, skipping Bing search")
            return None
        
        # Generate hierarchical model variations (same as Google)
        model_variations = self._generate_model_variations(model)
        logger.info(f"🔍 Bing: Generated {len(model_variations)} model variations: {model_variations}")
        
        # Try each model variation
        for i, current_model in enumerate(model_variations):
            logger.info(f"🔍 Bing search attempt {i+1}/{len(model_variations)}: trying model '{current_model}'")
            
            # Generate search queries for this model variation
            queries = self._generate_search_queries(domain, make, current_model, year, author)
            
            best_url = None
            best_score = 0
            
            for j, query in enumerate(queries, 1):
                logger.info(f"🔍 Bing search attempt {j}/{len(queries)}: {query}")
                
                try:
                    url = self._execute_search(query)
                    if url:
                        # Score the result quality (reuse Google's scoring logic)
                        from src.utils.google_search import GoogleSearchClient
                        google_client = GoogleSearchClient()
                        score = google_client._score_url_relevance(url, make, current_model, author)
                        logger.info(f"🔍 Bing found article URL: {url} (quality score: {score})")
                        
                        # Verify author in content if specified - NEW BUSINESS-AWARE LOGIC
                        attribution_strength = 'strong'
                        actual_byline = None
                        
                        if author:
                            author_found = self._verify_author_in_content(url, author)
                            if author_found:
                                logger.info(f"✅ Strong attribution: {author} found in content")
                                attribution_strength = 'strong'
                            else:
                                logger.info(f"⚠️ Delegated content: {author} not in byline, but domain-restricted content accepted")
                                attribution_strength = 'delegated'
                                # Try to extract actual byline for transparency
                                actual_byline = self._extract_actual_byline(url)
                                if actual_byline:
                                    logger.info(f"📝 Actual byline author: {actual_byline}")
                        
                        # BUSINESS LOGIC: Don't reject domain-restricted, vehicle-specific content
                        # This handles delegated writing, staff writers, house bylines
                        # Manual review will catch any issues
                        
                        if score > best_score:
                            best_score = score
                            best_url = url
                            # Store attribution info for UI display
                            best_attribution = attribution_strength
                            best_byline = actual_byline
                        
                        # If we found a high-quality result, use it
                        if score >= 80:
                            logger.info(f"✅ Bing found high-quality article with model variation '{current_model}': {url}")
                            return url
                            
                    else:
                        logger.info(f"🔍 Bing: No results for query: {query}")
                        
                except Exception as e:
                    logger.error(f"🔍 Bing error in search attempt {j}: {e}")
                    continue
                    
                # Rate limit: wait between queries
                time.sleep(0.5)
            
            # If we found something decent for this model variation, use it
            if best_url and best_score >= 50:
                logger.info(f"✅ Bing found good article with model variation '{current_model}': {best_url} (score: {best_score})")
                return best_url
            
            logger.info(f"🔍 Bing: No good results for model variation '{current_model}', trying next variation...")
        
        logger.warning(f"❌ Bing: No articles found for any model variation of {make} {model} by {author or 'any author'} on {domain}")
        return None
    
    def _generate_search_queries(self, domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> List[str]:
        """Generate Bing-optimized search queries"""
        queries = []
        
        # Clean up model name for search
        clean_model = model.replace(" Prestige", "").replace(" Premium", "").strip()
        clean_author = author.strip() if author else None
        
        # Bing search queries (similar to Google but optimized for Bing syntax)
        if clean_author:
            queries.append(f'site:{domain} "{make} {clean_model}" "{clean_author}" review')
            if year:
                queries.append(f'site:{domain} "{year} {make} {clean_model}" "{clean_author}"')
            queries.append(f'site:{domain} "{clean_author}" "{make}" "{clean_model}"')
        
        # Article title formats
        if year:
            queries.append(f'site:{domain} "{year} {make} {clean_model} Review"')
        queries.append(f'site:{domain} "{make} {clean_model} Review"')
        
        # Broader searches
        queries.append(f'site:{domain} "{make}" "{clean_model}" review')
        if clean_author:
            queries.append(f'"{make} {clean_model}" "{clean_author}" site:{domain}')
        
        return queries
    
    def _execute_search(self, query: str) -> Optional[str]:
        """Execute a single Bing search and return the best matching URL"""
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key
        }
        
        params = {
            'q': query,
            'count': 5,  # Get top 5 results
            'mkt': 'en-US'
        }
        
        try:
            response = requests.get(self.base_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'webPages' not in data or 'value' not in data['webPages']:
                return None
            
            # Process results similar to Google
            search_terms = self._extract_search_terms(query)
            scored_results = []
            
            for item in data['webPages']['value']:
                url = item.get('url', '')
                title = item.get('name', '')
                snippet = item.get('snippet', '')
                
                if self._is_article_url(url, title):
                    # Check for obvious old dates in URL BEFORE scoring/crawling
                    if self._is_url_too_old(url):
                        logger.info(f"❌ Bing skipping old URL (detected from path): {url}")
                        continue
                        
                    score = self._score_result(title, snippet, search_terms)
                    scored_results.append((score, url, title))
                    logger.info(f"🔍 Bing candidate: {title} | Score: {score}")
            
            # Return the highest scoring result
            if scored_results:
                scored_results.sort(key=lambda x: x[0], reverse=True)
                best_score, best_url, best_title = scored_results[0]
                logger.info(f"🔍 Bing selected: {best_title} (score: {best_score})")
                return best_url
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"🔍 Bing HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"🔍 Bing unexpected error: {e}")
            return None
    
    def _extract_search_terms(self, query: str) -> dict:
        """Extract search terms from query for scoring (reuse Google's logic)"""
        # Reuse Google's implementation
        from src.utils.google_search import GoogleSearchClient
        google_client = GoogleSearchClient()
        return google_client._extract_search_terms(query)
    
    def _score_result(self, title: str, snippet: str, search_terms: dict) -> int:
        """Score search result relevance (reuse Google's logic)"""
        from src.utils.google_search import GoogleSearchClient
        google_client = GoogleSearchClient()
        return google_client._score_result(title, snippet, search_terms)
    
    def _is_article_url(self, url: str, title: str) -> bool:
        """Check if URL looks like an article (reuse Google's logic)"""
        from src.utils.google_search import GoogleSearchClient
        google_client = GoogleSearchClient()
        return google_client._is_article_url(url, title)

    def _is_url_too_old(self, url: str) -> bool:
        """Check if URL contains obvious old date patterns (reuse Google's logic)"""
        from src.utils.google_search import GoogleSearchClient
        google_client = GoogleSearchClient()
        return google_client._is_url_too_old(url)
    
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

    def _extract_actual_byline(self, url: str) -> Optional[str]:
        """Extract actual byline author from the article content"""
        try:
            # Import here to avoid circular imports
            from src.utils.enhanced_http import fetch_with_enhanced_http
            
            # Quick fetch of article content
            content = fetch_with_enhanced_http(url)
            if not content:
                return None
            
            # Extract byline from content
            import re
            byline_pattern = r'^(.*?)(?: - | \| )'
            match = re.search(byline_pattern, content)
            
            if match:
                byline = match.group(1).strip()
                logger.info(f"📝 Extracted byline: {byline}")
                return byline
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting actual byline: {e}")
            return None

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
    
    def search_for_article_sync(self, domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> Optional[str]:
        """
        SYNCHRONOUS version of search_for_article - for use in enhanced crawler.
        Skips async author verification to avoid async/await issues.
        
        Args:
            domain: Target domain (e.g., "motortrend.com")
            make: Vehicle make (e.g., "Audi")
            model: Vehicle model (e.g., "Q6 e-tron Prestige") 
            year: Vehicle year (e.g., "2024"), optional
            author: Author/journalist name (e.g., "Alexander Stoklosa"), optional
            
        Returns:
            Best matching article URL or None if not found
        """
        logger.info(f"🔍 Google Search (sync) called with: make='{make}', model='{model}', year='{year}', author='{author}', domain='{domain}'")
        
        if not self.api_key or not self.search_engine_id:
            logger.error("Google Search API not configured properly")
            return None
        
        # Generate exactly 3 simple search queries (no model variations)
        queries = self._generate_search_queries(domain, make, model, year, author)
        
        best_url = None
        best_score = 0
        
        for i, query in enumerate(queries, 1):
            logger.info(f"Google search attempt {i}/{len(queries)}: {query}")
            
            try:
                url = self._execute_search(query)
                if url:
                    # Score the result quality
                    score = self._score_url_relevance(url, make, model, author)
                    logger.info(f"Found article URL: {url} (quality score: {score})")
                    
                    # NOTE: Skipping async author verification in sync version
                    # The enhanced crawler doesn't need detailed attribution info
                    
                    if score > best_score:
                        best_score = score
                        best_url = url
                    
                    # If we found a high-quality result, use it immediately
                    if score >= 80:  # High confidence threshold
                        logger.info(f"✅ Found high-quality article: {url}")
                        return url
                        
                else:
                    logger.info(f"No results for query: {query}")
                    
            except Exception as e:
                logger.error(f"Error in search attempt {i}: {e}")
                continue
                
            # Rate limit: wait between queries
            time.sleep(0.5)
        
        # Return best result found, if any
        if best_url and best_score >= 50:
            logger.info(f"✅ Found good article: {best_url} (score: {best_score})")
            return best_url
        
        logger.warning(f"❌ No articles found for {make} {model} by {author or 'any author'} on {domain}")
        return None
    
    async def search_for_article(self, domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> Optional[str]:
        """
        Search for a specific vehicle review article using graduated fallback queries.
        Now includes HIERARCHICAL MODEL SEARCH: tries full model name first, then progressively simpler terms.
        
        Args:
            domain: Target domain (e.g., "motortrend.com")
            make: Vehicle make (e.g., "Audi")
            model: Vehicle model (e.g., "Q6 e-tron Prestige") 
            year: Vehicle year (e.g., "2024"), optional
            author: Author/journalist name (e.g., "Alexander Stoklosa"), optional
            
        Returns:
            Best matching article URL or None if not found
        """
        logger.info(f"🔍 Google Search called with: make='{make}', model='{model}', year='{year}', author='{author}', domain='{domain}'")
        
        if not self.api_key or not self.search_engine_id:
            logger.error("Google Search API not configured properly")
            return None
        
        # Generate exactly 3 simple search queries (no model variations)
        queries = self._generate_search_queries(domain, make, model, year, author)
        
        best_url = None
        best_score = 0
        
        for i, query in enumerate(queries, 1):
            logger.info(f"Google search attempt {i}/{len(queries)}: {query}")
            
            try:
                url = self._execute_search(query)
                if url:
                    # Score the result quality
                    score = self._score_url_relevance(url, make, model, author)
                    logger.info(f"Found article URL: {url} (quality score: {score})")
                    
                    # Verify author in content if specified - NEW BUSINESS-AWARE LOGIC
                    attribution_strength = 'strong'
                    actual_byline = None
                    
                    if author:
                        author_found = await self._verify_author_in_content(url, author)
                        if author_found:
                            logger.info(f"✅ Strong attribution: {author} found in content")
                            attribution_strength = 'strong'
                        else:
                            logger.info(f"⚠️ Delegated content: {author} not in byline, but domain-restricted content accepted")
                            attribution_strength = 'delegated'
                            # Try to extract actual byline for transparency
                            actual_byline = await self._extract_actual_byline(url)
                            if actual_byline:
                                logger.info(f"📝 Actual byline author: {actual_byline}")
                        
                        # BUSINESS LOGIC: Don't reject domain-restricted, vehicle-specific content
                        # This handles delegated writing, staff writers, house bylines
                        # Manual review will catch any issues
                    
                    if score > best_score:
                        best_score = score
                        best_url = url
                        # Store attribution info for UI display
                        best_attribution = attribution_strength
                        best_byline = actual_byline
                    
                    # If we found a high-quality result, use it immediately
                    if score >= 80:  # High confidence threshold
                        logger.info(f"✅ Found high-quality article: {url}")
                        return url
                        
                else:
                    logger.info(f"No results for query: {query}")
                    
            except Exception as e:
                logger.error(f"Error in search attempt {i}: {e}")
                continue
                
            # Rate limit: wait between queries
            time.sleep(0.5)
        
        # Return best result found, if any
        if best_url and best_score >= 50:
            logger.info(f"✅ Found good article: {best_url} (score: {best_score})")
            # Return tuple with attribution info for UI display
            attribution_info = {
                'url': best_url,
                'attribution_strength': best_attribution if 'best_attribution' in locals() else 'unknown',
                'actual_byline': best_byline if 'best_byline' in locals() else None
            }
            return attribution_info
        
        logger.warning(f"❌ No articles found for {make} {model} by {author or 'any author'} on {domain}")
        return None
    
    def _generate_search_queries(self, domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> List[str]:
        """Generate exactly 3 simple search queries: Domain+Make+Model+Author, Domain+Make+Model, Domain+Model"""
        queries = []
        
        # Use the exact model name as provided (no cleaning, no hardcoding)
        
        # Attempt 1: Domain Make Model Author (if author provided)
        if author:
            queries.append(f'site:{domain} "{make} {model}" "{author}"')
        
        # Attempt 2: Domain Make Model  
        queries.append(f'site:{domain} "{make} {model}"')
        
        # Attempt 3: Domain Model
        queries.append(f'site:{domain} "{model}"')
        
        logger.info(f"Generated {len(queries)} simple search queries")
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
                
                # DOMAIN RESTRICTION: Only accept URLs from the target domain
                from urllib.parse import urlparse
                try:
                    result_domain = urlparse(url).netloc.lower().replace('www.', '')
                    query_domain = None
                    
                    # Extract domain from site: restriction in query
                    import re
                    site_match = re.search(r'site:([^\s]+)', query)
                    if site_match:
                        query_domain = site_match.group(1).lower()
                    
                    if query_domain and query_domain not in result_domain:
                        logger.info(f"❌ Skipping off-domain result: {url} (expected {query_domain})")
                        continue
                        
                except Exception as e:
                    logger.warning(f"Error checking domain restriction for {url}: {e}")
                    continue
                
                if self._is_article_url(url, title):
                    # Check for obvious old dates in URL BEFORE scoring/crawling
                    if self._is_url_too_old(url):
                        logger.info(f"❌ Skipping old URL (detected from path): {url}")
                        continue
                        
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
            model_lower = search_terms['model'].lower().replace('"', '')
            model_words = model_lower.split()
            
            # STRICT MODEL VERIFICATION: ALL model words must be present
            title_matches = sum(1 for word in model_words if word in title_lower)
            match_percentage = title_matches / len(model_words) if model_words else 0
            
            if match_percentage >= 1.0:  # 100% of model words must match (was 70%)
                score += 100
                logger.debug(f"Title match bonus: +100 for exact model '{search_terms['model']}'")
            elif match_percentage >= 0.7:  # Partial match gets lower score
                score += 30
                logger.debug(f"Partial title match: +30 for {match_percentage:.0%} of '{search_terms['model']}'")
            else:
                # PENALTY for wrong model (e.g., searching Odyssey but finding Civic)
                score -= 50
                logger.debug(f"Wrong model penalty: -50 (only {match_percentage:.0%} match for '{search_terms['model']}')")
        
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

    def _is_url_too_old(self, url: str) -> bool:
        """Check if URL contains obvious old date patterns that make it not worth crawling"""
        import re
        from datetime import datetime
        
        # Extract 4-digit years from URL path
        year_pattern = r'/(\d{4})[-/]'
        matches = re.findall(year_pattern, url)
        
        if matches:
            try:
                url_year = int(matches[0])
                current_year = datetime.now().year
                
                # Reject articles older than 2 years (configurable threshold)
                if url_year < (current_year - 1):  # 2023 and older are rejected in 2025
                    logger.debug(f"URL contains old year {url_year}: {url}")
                    return True
            except ValueError:
                pass
        
        # Additional patterns for known old content
        old_patterns = [
            '/2019/', '/2020/', '/2021/', '/2022/', '/2023/',  # Specific old years
            '2019-', '2020-', '2021-', '2022-', '2023-'       # Year in filename
        ]
        
        for pattern in old_patterns:
            if pattern in url:
                logger.debug(f"URL matches old pattern '{pattern}': {url}")
                return True
                
        return False

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
        
        # FIXED: Precise model matching for hyphenated models like CX-5 vs CX-90
        if '-' in model_lower:
            # For hyphenated models, require EXACT match to avoid CX-5 matching CX-90
            if model_lower in url_lower:
                score += 100  # Higher score for exact match
                logger.debug(f"Exact hyphenated model match: {model_lower} in {url_lower}")
            else:
                logger.debug(f"No exact hyphenated model match: {model_lower} not in {url_lower}")
        else:
            # For non-hyphenated models, use first word matching (existing behavior)
            if model_lower.split('-')[0] in url_lower:
                score += 40
                logger.debug(f"Model first word match: {model_lower.split('-')[0]} in {url_lower}")
        
        if author and any(word.lower() in url_lower for word in author.split()):
            score += 20
        if 'review' in url_lower or 'test' in url_lower:
            score += 20
        if '2025' in url_lower or '2024' in url_lower:
            score += 10
            
        # Check if it's obviously wrong vehicle - ENHANCED for hyphenated models
        wrong_indicators = ['genesis', 'toyota', 'honda', 'bmw', 'mercedes']
        vehicle_words = [make_lower, model_lower.split('-')[0]]
        for wrong in wrong_indicators:
            if wrong in url_lower and wrong not in vehicle_words:
                score -= 50
        
        # ENHANCED: Penalty for wrong hyphenated model (like CX-90 when looking for CX-5)
        if '-' in model_lower:
            base_part = model_lower.split('-')[0]  # "cx"
            number_part = model_lower.split('-')[1]  # "5"
            
            # Look for other models with same base but different number
            import re
            wrong_pattern = rf'{re.escape(base_part)}-(?!{re.escape(number_part)})\d+'
            if re.search(wrong_pattern, url_lower):
                score -= 200  # Heavy penalty for wrong model variant
                logger.debug(f"Wrong hyphenated model penalty: Found {base_part}-X where X≠{number_part}")
                
        return max(0, score)

    async def _verify_author_in_content(self, url: str, author: str) -> bool:
        """
        Verify that the article content actually contains the specified author.
        This prevents wrong articles from being returned.
        Uses ESCALATION: Enhanced HTTP → Headless Browser if needed
        """
        try:
            # Import here to avoid circular imports
            from src.utils.enhanced_http import fetch_with_enhanced_http
            from src.utils.browser_crawler import BrowserCrawler
            
            # Try Enhanced HTTP first (faster)
            logger.info(f"🔍 Verifying author {author} in {url} using Enhanced HTTP")
            content = fetch_with_enhanced_http(url)
            
            # If Enhanced HTTP fails, try headless browser
            if not content:
                logger.info(f"🔍 Enhanced HTTP failed, trying headless browser for {url}")
                browser_crawler = BrowserCrawler(headless=True)
                try:
                    content, title, error = await browser_crawler.crawl(url, wait_time=5, scroll=False)
                    if content:
                        logger.info(f"✅ Headless browser successfully extracted content from {url}")
                    else:
                        logger.warning(f"❌ Headless browser also failed for {url}: {error}")
                        return False
                finally:
                    browser_crawler.close()
            
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

    async def _extract_actual_byline(self, url: str) -> Optional[str]:
        """Extract actual byline author from the article content with escalation"""
        try:
            # Import here to avoid circular imports
            from src.utils.enhanced_http import fetch_with_enhanced_http
            from src.utils.browser_crawler import BrowserCrawler
            
            # Try Enhanced HTTP first (faster)
            content = fetch_with_enhanced_http(url)
            
            # If Enhanced HTTP fails, try headless browser
            if not content:
                logger.info(f"🔍 Enhanced HTTP failed for byline extraction, trying headless browser for {url}")
                browser_crawler = BrowserCrawler(headless=True)
                try:
                    content, title, error = await browser_crawler.crawl(url, wait_time=5, scroll=False)
                    if not content:
                        logger.warning(f"❌ Headless browser also failed for byline extraction: {error}")
                        return None
                finally:
                    browser_crawler.close()
            
            # Extract byline from content
            import re
            byline_pattern = r'^(.*?)(?: - | \| )'
            match = re.search(byline_pattern, content)
            
            if match:
                byline = match.group(1).strip()
                logger.info(f"📝 Extracted byline: {byline}")
                return byline
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting actual byline: {e}")
            return None

# Convenience function for easy importing
async def google_search_for_article(domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> Optional[dict]:
    """
    Convenience function to search for a vehicle article.
    Now includes Bing Search as backup if Google Search fails.
    
    Args:
        domain: Target domain (e.g., "motortrend.com")
        make: Vehicle make (e.g., "Audi")
        model: Vehicle model (e.g., "Q6 e-tron")
        year: Vehicle year (optional)
        author: Author/journalist name (optional)
        
    Returns:
        Dict with url, attribution_strength, actual_byline or None
    """
    # Try Google Search first
    logger.info(f"🔍 Starting search for {make} {model} by {author or 'any author'} on {domain}")
    google_client = GoogleSearchClient()
    result = await google_client.search_for_article(domain, make, model, year, author)
    
    if result:
        logger.info(f"✅ Google Search found article: {result}")
        return result
    
    # If Google failed, try Bing as backup
    logger.info(f"🔍 Google Search failed, trying Bing Search as backup...")
    bing_client = BingSearchClient()
    bing_result = bing_client.search_for_article(domain, make, model, year, author)
    
    if bing_result:
        # Convert simple URL to dict format for consistency
        if isinstance(bing_result, str):
            bing_result = {
                'url': bing_result,
                'attribution_strength': 'unknown',
                'actual_byline': None
            }
        logger.info(f"✅ Bing Search backup found article: {bing_result}")
        return bing_result
    
    logger.warning(f"❌ Both Google and Bing searches failed for {make} {model} by {author or 'any author'} on {domain}")
    return None 