import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from time import monotonic
from random import uniform

# Get logger
from src.utils.logger import setup_logger
logger = setup_logger(__name__)

# NEW: Session-scoped post-response backoff system
# { (domain, proxy_session): unblock_at_epoch }
_COOLDOWNS = {}
_COOLDOWN_LOCK = threading.Lock()

def should_wait(domain: str, proxy_session: str | None = None):
    """Check if we need to wait before making a request (post-response backoff only)"""
    key = (domain, proxy_session or "none")
    now = monotonic()
    
    with _COOLDOWN_LOCK:
        until = _COOLDOWNS.get(key, 0)
        return max(0, until - now)

def register_backoff(domain: str, proxy_session: str | None = None, retry_after_s: float | None = None, status_code: int = None):
    """Register a backoff period after receiving 429/403/empty response"""
    key = (domain, proxy_session or "none")
    
    # Use Retry-After header if available, otherwise jittered backoff
    if retry_after_s is not None and retry_after_s > 0:
        base = min(retry_after_s, 15.0)  # Cap at 15s max
    else:
        base = uniform(6.0, 12.0)  # Short & jittered default
    
    with _COOLDOWN_LOCK:
        _COOLDOWNS[key] = monotonic() + base
    
    logger.info(f"Registered backoff for {domain} (session: {(proxy_session or 'none')[:8]}): {base:.1f}s (status: {status_code})")

def clear_backoff(domain: str, proxy_session: str | None = None):
    """Clear any backoff for successful requests"""
    key = (domain, proxy_session or "none")
    
    with _COOLDOWN_LOCK:
        if key in _COOLDOWNS:
            del _COOLDOWNS[key]

# LEGACY: Keep original RateLimiter for non-YouTube domains
class RateLimiter:
    """
    A rate limiter for controlling request rates to external APIs.
    
    This class implements a token bucket algorithm to manage request rates.
    Each domain has its own bucket of tokens that refill over time.
    
    NOTE: YouTube transcript extraction now uses post-response backoff (should_wait/register_backoff)
    """
    
    def __init__(self):
        # Maps domain -> {token_count, last_refill, lock}
        self.buckets = defaultdict(lambda: {
            'token_count': 0,
            'last_refill': datetime.now(),
            'lock': threading.Lock()
        })
        
        # Default limits for common services
        # OpenAI Tier 1: gpt-4-turbo = 500 RPM, gpt-3.5-turbo = 3500 RPM
        # Set to 80% of limit to be safe
        self.default_rates = {
            'openai.com': {'rate': 400, 'per': 60},  # 400 requests per minute (80% of 500 RPM for gpt-4-turbo)
            'youtube.com': {'rate': 10, 'per': 60},  # Relaxed: 10 per minute (legacy API only, yt-dlp uses post-response)
            'default': {'rate': 1, 'per': 5}         # 1 request per 5 seconds for unknown domains
        }
    
    def wait_if_needed(self, domain, custom_rate=None, custom_per=None):
        """
        Wait if necessary to respect rate limits for a domain.
        
        Args:
            domain (str): The domain to check rate limits for
            custom_rate (int, optional): Custom rate limit to override defaults
            custom_per (int, optional): Custom period in seconds to override defaults
        """
        # Normalize domain
        domain = self._normalize_domain(domain)
        
        # SURGICAL FIX: Skip all pre-flight waits for YouTube - use post-response backoff instead
        if domain == 'youtube.com':
            logger.debug(f"🚀 Skipping pre-flight wait for {domain} - using post-response backoff")
            return
        
        # Get rate limits for this domain
        if custom_rate is not None and custom_per is not None:
            rate = custom_rate
            per = custom_per
        elif domain in self.default_rates:
            rate = self.default_rates[domain]['rate']
            per = self.default_rates[domain]['per']
        else:
            rate = self.default_rates['default']['rate']
            per = self.default_rates['default']['per']
        
        # Attempt to get a token
        with self.buckets[domain]['lock']:
            bucket = self.buckets[domain]
            
            # Refill tokens based on time elapsed
            now = datetime.now()
            elapsed = (now - bucket['last_refill']).total_seconds()
            new_tokens = int(elapsed * rate / per)
            
            if new_tokens > 0:
                bucket['token_count'] = min(rate, bucket['token_count'] + new_tokens)
                bucket['last_refill'] = now
            
            # If no tokens, calculate wait time
            if bucket['token_count'] <= 0:
                # Calculate time until next token
                wait_time = per / rate - elapsed
                logger.info(f"Rate limit reached for {domain}. Waiting {wait_time:.2f} seconds.")
                time.sleep(max(0, wait_time))
                bucket['token_count'] = 1
                bucket['last_refill'] = datetime.now()
            
            # Consume a token
            bucket['token_count'] -= 1
    
    def _normalize_domain(self, url):
        """Extract and normalize domain from URL"""
        # Simple domain extraction - could be improved with urlparse
        domain = url.lower()
        for prefix in ['https://', 'http://', 'www.']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        
        domain = domain.split('/')[0]
        
        # Map to top-level domain
        for known_domain in self.default_rates.keys():
            if known_domain in domain:
                return known_domain
        
        return domain

# Singleton instance
rate_limiter = RateLimiter() 