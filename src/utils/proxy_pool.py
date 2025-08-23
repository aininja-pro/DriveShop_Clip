# src/utils/proxy_pool.py
import time
import random
import re

class SessionPool:
    """
    Sticky proxy session pool with 15-minute TTL.
    
    - acquire(): Returns same session for 15 minutes (sticky behavior)
    - rotate(): Creates new session, only call on 429/403/empty responses
    """
    
    def __init__(self, base_url, size=6, ttl_s=900):
        self.base = base_url or ""
        self.ttl_s = ttl_s
        self.items = []  # [(session_url, session_id, expires_at)]
    
    def _new(self):
        """Generate new session URL with unique session ID"""
        if not self.base:
            return None, "none"
            
        sid = str(random.randint(10000, 99999))
        
        # Handle different URL formats for IPRoyal sticky sessions
        if "?" in self.base:
            session_url = f"{self.base}&session={sid}"
        else:
            session_url = f"{self.base}?session={sid}"
            
        return session_url, sid
    
    def acquire(self):
        """Get current sticky session (same session for TTL period)"""
        now = time.monotonic()
        
        # Clean expired sessions
        self.items = [(url, sid, exp) for (url, sid, exp) in self.items if exp > now]
        
        # Create new session if none available
        if not self.items:
            url, sid = self._new()
            if url:
                self.items.append((url, sid, now + self.ttl_s))
            else:
                # No proxy configured
                return None, "none"
        
        # Return head (sticky session)
        url, sid, _ = self.items[0]
        return sid, url
    
    def rotate(self):
        """Create new session and make it sticky (only call on failures)"""
        now = time.monotonic()
        url, sid = self._new()
        
        if url:
            # Insert new session at head (becomes sticky)
            self.items.insert(0, (url, sid, now + self.ttl_s))
            return sid, url
        else:
            return "none", None
            
    def rotate_session(self, current_session_id):
        """Rotate away from a problematic session (backward compatibility)"""
        return self.rotate()

# Global session pool instance
_session_pool = None

def get_session_pool(proxy_base_url=None):
    """Get or create global session pool instance"""
    global _session_pool
    if _session_pool is None:
        _session_pool = SessionPool(proxy_base_url)
    return _session_pool