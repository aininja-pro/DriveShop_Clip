import sqlite3
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class CacheManager:
    """SQLite-based cache manager for storing scraping results with 24-hour TTL"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize cache manager with SQLite database.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Default to data directory in project root
            project_root = Path(__file__).parent.parent.parent
            data_dir = os.path.join(project_root, 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'scraping_cache.db')
        
        self.db_path = db_path
        self.ttl_hours = 24
        
        # Initialize database
        self._init_database()
        
        logger.info(f"Cache manager initialized with database: {self.db_path}")
    
    def _init_database(self):
        """Create the cache table if it doesn't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create cache table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS scraping_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        person_id TEXT NOT NULL,
                        domain TEXT NOT NULL,
                        make TEXT NOT NULL,
                        model TEXT NOT NULL,
                        url TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata TEXT,  -- JSON string for GPT analysis results
                        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        UNIQUE(person_id, domain, make, model) ON CONFLICT REPLACE
                    )
                ''')
                
                # Create index for faster lookups
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_cache_lookup 
                    ON scraping_cache(person_id, domain, make, model, expires_at)
                ''')
                
                # Create index for cleanup
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_cache_expiry 
                    ON scraping_cache(expires_at)
                ''')
                
                conn.commit()
                logger.info("Cache database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing cache database: {e}")
            raise
    
    def get_cached_result(self, person_id: str, domain: str, make: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Get cached scraping result if it exists and hasn't expired.
        
        CACHE DISABLED: Always returns None to force fresh searches for reliable results.
        
        Args:
            person_id: Unique identifier for the media contact
            domain: Domain name (e.g., "motortrend.com")
            make: Vehicle make (e.g., "Audi")
            model: Vehicle model (e.g., "Q6 e-tron")
            
        Returns:
            Always None - cache disabled for reliability
        """
        # CACHE DISABLED: Always return None to force fresh searches
        # This ensures consistent, reliable results without cache-related bugs
        logger.info(f"Cache DISABLED - forcing fresh search for {person_id}/{domain}/{make}/{model}")
        return None
    
    def store_result(self, person_id: str, domain: str, make: str, model: str, 
                    url: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Store scraping result in cache with 24-hour expiry.
        
        Args:
            person_id: Unique identifier for the media contact
            domain: Domain name
            make: Vehicle make
            model: Vehicle model  
            url: The actual URL where content was found
            content: Scraped HTML content
            metadata: Optional GPT analysis results
        """
        try:
            # Calculate expiry time (24 hours from now)
            expires_at = datetime.now() + timedelta(hours=self.ttl_hours)
            
            # Convert metadata to JSON
            metadata_json = json.dumps(metadata) if metadata else None
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO scraping_cache 
                    (person_id, domain, make, model, url, content, metadata, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (person_id, domain, make, model, url, content, metadata_json, expires_at))
                
                conn.commit()
                
                logger.info(f"Cached result for {person_id}/{domain}/{make}/{model} (expires: {expires_at})")
                
        except Exception as e:
            logger.error(f"Error storing cache result: {e}")
    
    def _cleanup_expired_entries(self, cursor):
        """Remove expired entries from cache"""
        try:
            cursor.execute('DELETE FROM scraping_cache WHERE expires_at <= CURRENT_TIMESTAMP')
            deleted_count = cursor.rowcount
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired cache entries")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired entries: {e}")
    
    def cleanup_cache(self) -> int:
        """
        Manually clean up expired cache entries.
        
        Returns:
            Number of entries removed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('DELETE FROM scraping_cache WHERE expires_at <= CURRENT_TIMESTAMP')
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Manual cleanup removed {deleted_count} expired cache entries")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error during manual cache cleanup: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.
        
        Returns:
            Dict with cache statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total entries
                cursor.execute('SELECT COUNT(*) FROM scraping_cache')
                total_entries = cursor.fetchone()[0]
                
                # Valid (non-expired) entries
                cursor.execute('SELECT COUNT(*) FROM scraping_cache WHERE expires_at > CURRENT_TIMESTAMP')
                valid_entries = cursor.fetchone()[0]
                
                # Expired entries
                expired_entries = total_entries - valid_entries
                
                # Entries by domain
                cursor.execute('''
                    SELECT domain, COUNT(*) 
                    FROM scraping_cache 
                    WHERE expires_at > CURRENT_TIMESTAMP
                    GROUP BY domain 
                    ORDER BY COUNT(*) DESC
                ''')
                domain_stats = dict(cursor.fetchall())
                
                return {
                    'total_entries': total_entries,
                    'valid_entries': valid_entries,
                    'expired_entries': expired_entries,
                    'domain_breakdown': domain_stats,
                    'cache_file': self.db_path
                }
                
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'error': str(e)}
    
    def clear_cache(self):
        """Clear all cache entries (use with caution)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM scraping_cache')
                conn.commit()
                
                logger.warning("All cache entries cleared")
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

# Global cache instance
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

# Convenience functions
def get_cached_result(person_id: str, domain: str, make: str, model: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get cached result"""
    cache = get_cache_manager()
    return cache.get_cached_result(person_id, domain, make, model)

def store_result(person_id: str, domain: str, make: str, model: str, 
                url: str, content: str, metadata: Optional[Dict[str, Any]] = None):
    """Convenience function to store result"""
    cache = get_cache_manager()
    cache.store_result(person_id, domain, make, model, url, content, metadata) 