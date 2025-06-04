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
                        
                        # Verify author in content if specified
                        if author and not google_client._verify_author_in_content(url, author):
                            logger.warning(f"🔍 Bing: Article doesn't contain author {author}, reducing score: {url}")
                            score = max(10, score - 30)
                        
                        if score > best_score:
                            best_score = score
                            best_url = url
                        
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
    
    def _generate_model_variations(self, model: str) -> List[str]:
        """Generate model name variations for search optimization"""
        variations = [model]  # Always include original
        
        # Handle hyphenated models more specifically (like CX-5 vs CX-90)
        if '-' in model:
            # For CX-5: try "CX-5", "CX 5", "CX5"
            base_part = model.split('-')[0]  # "CX"
            number_part = model.split('-')[1]  # "5"
            
            variations.extend([
                f"{base_part} {number_part}",      # "CX 5"
                f"{base_part}{number_part}",       # "CX5"
                f'"{model}"',                      # "CX-5" with quotes for exact match
                f"{model} review",                 # "CX-5 review"
                f"{model} test",                   # "CX-5 test"
            ])
        
        # Handle models with spaces
        if ' ' in model:
            variations.append(model.replace(' ', '-'))  # "Q6 e-tron" -> "Q6 e-tron"
            variations.append(model.replace(' ', ''))   # "Q6 e-tron" -> "Q6etron"
        
        # Add common automotive terms
        base_variations = [
            f"{model} review",
            f"{model} test drive", 
            f"{model} first drive",
            f"2025 {model}",
            f"2024 {model}",
        ]
        variations.extend(base_variations)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for v in variations:
            if v not in seen:
                seen.add(v)
                unique_variations.append(v)
        
        return unique_variations[:10]  # Limit to top 10 to avoid too many API calls

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
        if not self.api_key or not self.search_engine_id:
            logger.error("Google Search API not configured properly")
            return None
        
        # Generate hierarchical model variations (from most specific to most general)
        model_variations = self._generate_model_variations(model)
        logger.info(f"Generated {len(model_variations)} model variations: {model_variations}")
        
        # Try each model variation in hierarchical order
        for i, current_model in enumerate(model_variations):
            logger.info(f"Hierarchical search attempt {i+1}/{len(model_variations)}: trying model '{current_model}'")
            
            # Generate search queries for this specific model variation
            queries = self._generate_search_queries(domain, make, current_model, year, author)
            
            best_url = None
            best_score = 0
            
            for j, query in enumerate(queries, 1):
                logger.info(f"Google search attempt {j}/{len(queries)}: {query}")
                
                try:
                    url = self._execute_search(query)
                    if url:
                        # Score the result quality
                        score = self._score_url_relevance(url, make, current_model, author)
                        logger.info(f"Found article URL: {url} (quality score: {score})")
                        
                        # Verify author in content if specified
                        if author and not self._verify_author_in_content(url, author):
                            logger.warning(f"Article doesn't contain author {author}, reducing score: {url}")
                            score = max(10, score - 30)  # Reduce score instead of completely blocking
                        
                        if score > best_score:
                            best_score = score
                            best_url = url
                        
                        # If we found a high-quality result, use it immediately
                        if score >= 80:  # High confidence threshold
                            logger.info(f"✅ Found high-quality article with model variation '{current_model}': {url}")
                            return url
                            
                    else:
                        logger.info(f"No results for query: {query}")
                        
                except Exception as e:
                    logger.error(f"Error in search attempt {j}: {e}")
                    continue
                    
                # Rate limit: wait between queries
                time.sleep(0.5)
            
            # If Google Search found something decent for this model variation, use it
            if best_url and best_score >= 50:
                logger.info(f"✅ Found good article with model variation '{current_model}': {best_url} (score: {best_score})")
                return best_url
            
            logger.info(f"No good results for model variation '{current_model}', trying next variation...")
        
        logger.warning(f"❌ No articles found for any model variation of {make} {model} by {author or 'any author'} on {domain}")
        return None
    
    def _generate_search_queries(self, domain: str, make: str, model: str, year: Optional[str] = None, author: Optional[str] = None) -> List[str]:
        """Generate graduated search queries from specific to broad"""
        queries = []
        
        # Clean up model name for search
        clean_model = model.replace(" Prestige", "").replace(" Premium", "").strip()
        
        # Clean up author name if provided
        clean_author = author.strip() if author else None
        
        # For inurl parameter, use full model for hyphenated models, otherwise first word
        if '-' in clean_model:
            inurl_term = clean_model.lower().replace(' ', '-')  # "CX-5" -> "cx-5"
        else:
            inurl_term = clean_model.split()[0].lower()  # "Jetta GLI" -> "jetta"
        
        # Tier 1: Author + vehicle + site (HIGHEST PRIORITY - author-specific reviews)
        if clean_author:
            queries.append(f'site:{domain} "{make} {clean_model}" "{clean_author}" inurl:{inurl_term}')
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

    def _generate_model_variations(self, model: str) -> List[str]:
        """Generate model name variations for search optimization"""
        variations = [model]  # Always include original
        
        # Handle hyphenated models more specifically (like CX-5 vs CX-90)
        if '-' in model:
            # For CX-5: try "CX-5", "CX 5", "CX5"
            base_part = model.split('-')[0]  # "CX"
            number_part = model.split('-')[1]  # "5"
            
            variations.extend([
                f"{base_part} {number_part}",      # "CX 5"
                f"{base_part}{number_part}",       # "CX5"
                f'"{model}"',                      # "CX-5" with quotes for exact match
                f"{model} review",                 # "CX-5 review"
                f"{model} test",                   # "CX-5 test"
            ])
        
        # Handle models with spaces
        if ' ' in model:
            variations.append(model.replace(' ', '-'))  # "Q6 e-tron" -> "Q6 e-tron"
            variations.append(model.replace(' ', ''))   # "Q6 e-tron" -> "Q6etron"
        
        # Add common automotive terms
        base_variations = [
            f"{model} review",
            f"{model} test drive", 
            f"{model} first drive",
            f"2025 {model}",
            f"2024 {model}",
        ]
        variations.extend(base_variations)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for v in variations:
            if v not in seen:
                seen.add(v)
                unique_variations.append(v)
        
        return unique_variations[:10]  # Limit to top 10 to avoid too many API calls

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
    Now includes Bing Search as backup if Google Search fails.
    
    Args:
        domain: Target domain (e.g., "motortrend.com")
        make: Vehicle make (e.g., "Audi")
        model: Vehicle model (e.g., "Q6 e-tron")
        year: Vehicle year (optional)
        author: Author/journalist name (optional)
        
    Returns:
        Article URL or None
    """
    # Try Google Search first
    logger.info(f"🔍 Starting search for {make} {model} by {author or 'any author'} on {domain}")
    google_client = GoogleSearchClient()
    result = google_client.search_for_article(domain, make, model, year, author)
    
    if result:
        logger.info(f"✅ Google Search found article: {result}")
        return result
    
    # If Google failed, try Bing as backup
    logger.info(f"🔍 Google Search failed, trying Bing Search as backup...")
    bing_client = BingSearchClient()
    bing_result = bing_client.search_for_article(domain, make, model, year, author)
    
    if bing_result:
        logger.info(f"✅ Bing Search backup found article: {bing_result}")
        return bing_result
    
    logger.warning(f"❌ Both Google and Bing searches failed for {make} {model} by {author or 'any author'} on {domain}")
    return None 