import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta

# Get logger
from src.utils.logger import setup_logger
logger = setup_logger(__name__)

class RateLimiter:
    """
    A rate limiter for controlling request rates to external APIs.
    
    This class implements a token bucket algorithm to manage request rates.
    Each domain has its own bucket of tokens that refill over time.
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
            'youtube.com': {'rate': 10, 'per': 60},  # 10 requests per minute
            'default': {'rate': 1, 'per': 2}  # 1 request per 2 seconds for unknown domains
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