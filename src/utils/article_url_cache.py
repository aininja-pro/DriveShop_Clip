"""
Article URL Cache - Stores discovered article URLs to avoid repeated Index Discovery.
This significantly improves performance for slow sites like Tightwad Garage.
"""

import json
import os
from typing import Optional, Dict
from datetime import datetime
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class ArticleURLCache:
    """Cache for storing discovered article URLs to avoid repeated searches."""
    
    def __init__(self, cache_file: str = None):
        """Initialize the article URL cache."""
        if cache_file is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cache_file = os.path.join(project_root, 'data', 'article_url_cache.json')
        
        self.cache_file = cache_file
        self.cache = self._load_cache()
        logger.info(f"Article URL cache initialized with {len(self.cache)} entries")
    
    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading article URL cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving article URL cache: {e}")
    
    def _get_cache_key(self, domain: str, make: str, model: str) -> str:
        """Generate a cache key for the article."""
        # Normalize inputs
        domain = domain.lower().replace('www.', '')
        make = make.lower()
        model = model.lower()
        return f"{domain}:{make}:{model}"
    
    def get_article_url(self, domain: str, make: str, model: str) -> Optional[str]:
        """
        Get cached article URL if available.
        
        Returns:
            Article URL if found in cache, None otherwise
        """
        cache_key = self._get_cache_key(domain, make, model)
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            url = entry.get('url')
            logger.info(f"✅ Found cached article URL for {make} {model} on {domain}: {url}")
            
            # Update last accessed time
            entry['last_accessed'] = datetime.now().isoformat()
            self._save_cache()
            
            return url
        
        return None
    
    def store_article_url(self, domain: str, make: str, model: str, url: str, title: str = None):
        """
        Store discovered article URL in cache.
        
        Args:
            domain: Website domain
            make: Vehicle make
            model: Vehicle model
            url: Article URL
            title: Article title (optional)
        """
        cache_key = self._get_cache_key(domain, make, model)
        
        self.cache[cache_key] = {
            'url': url,
            'title': title or f"{make} {model} Review",
            'discovered': datetime.now().isoformat(),
            'last_accessed': datetime.now().isoformat(),
            'domain': domain,
            'make': make,
            'model': model
        }
        
        self._save_cache()
        logger.info(f"✅ Cached article URL for {make} {model} on {domain}: {url}")
    
    def clear_old_entries(self, days: int = 30):
        """Remove cache entries older than specified days."""
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        keys_to_remove = []
        for key, entry in self.cache.items():
            try:
                discovered = datetime.fromisoformat(entry.get('discovered', ''))
                if discovered.timestamp() < cutoff_date:
                    keys_to_remove.append(key)
            except:
                pass
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            self._save_cache()
            logger.info(f"Removed {len(keys_to_remove)} old cache entries")

# Global instance for easy access
_article_cache = None

def get_article_cache() -> ArticleURLCache:
    """Get the global article URL cache instance."""
    global _article_cache
    if _article_cache is None:
        _article_cache = ArticleURLCache()
    return _article_cache