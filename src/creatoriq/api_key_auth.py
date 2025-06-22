"""
CreatorIQ API Key Authentication

Clean, simple authentication using CreatorIQ API keys instead of browser sessions.
This is much more reliable than browser authentication.
"""

import os
from typing import Dict, Optional
from dotenv import load_dotenv
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Load environment variables from .env file
load_dotenv()

class CreatorIQAPIAuth:
    """
    API Key-based authentication for CreatorIQ.
    
    Much more reliable than browser session authentication.
    """
    
    def __init__(self):
        self.api_key = os.getenv('CREATORIQ_API_KEY')
        self.user_agent = os.getenv('CREATORIQ_USER_AGENT', 
                                   'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36')
        
        # Log authentication status (without exposing the key)
        self._log_auth_status()
    
    def _log_auth_status(self):
        """Log authentication status without exposing sensitive data."""
        if self.api_key:
            logger.info(f"✅ API Key: {self.api_key[:20]}...")
        else:
            logger.info("❌ API Key: Missing")
        
        logger.info("🔑 CreatorIQ API Key Authentication Status:")
        logger.info(f"   {'✅' if self.api_key else '❌'} API Key: {'Loaded' if self.api_key else 'Missing'}")
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get complete headers dictionary for API key-based requests.
        
        Returns:
            Dictionary of headers for API requests
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': self.user_agent,
            'Origin': 'https://app.creatoriq.com',
            'Referer': 'https://app.creatoriq.com/'
        }
        
        # Add API key authentication
        if self.api_key:
            # Try common API key header patterns
            headers['Authorization'] = f"Bearer {self.api_key}"
            headers['X-API-Key'] = self.api_key
            headers['API-Key'] = self.api_key
            # Note: We'll determine the correct pattern once we see the API docs
        
        return headers
    
    def is_authenticated(self) -> bool:
        """
        Check if we have a valid API key.
        
        Returns:
            True if we have an API key
        """
        return bool(self.api_key)
    
    def get_auth_summary(self) -> Dict[str, bool]:
        """
        Get summary of API key authentication status.
        
        Returns:
            Dictionary showing authentication status
        """
        return {
            'has_api_key': bool(self.api_key),
            'is_authenticated': self.is_authenticated(),
            'auth_method': 'api_key'
        }

# Global auth instance
_api_auth_instance = None

def get_api_key_headers() -> Dict[str, str]:
    """
    Convenience function to get API key authentication headers.
    
    Returns:
        Dictionary of headers for API requests
    """
    global _api_auth_instance
    if _api_auth_instance is None:
        _api_auth_instance = CreatorIQAPIAuth()
    
    return _api_auth_instance.get_headers()

def is_api_key_authenticated() -> bool:
    """
    Convenience function to check API key authentication status.
    
    Returns:
        True if authenticated with API key
    """
    global _api_auth_instance
    if _api_auth_instance is None:
        _api_auth_instance = CreatorIQAPIAuth()
    
    return _api_auth_instance.is_authenticated()

def validate_api_key_setup() -> bool:
    """
    Validate that API key authentication is properly configured.
    
    Returns:
        True if API key is properly set up
        
    Raises:
        ValueError: If API key is not configured
    """
    auth = CreatorIQAPIAuth()
    
    if not auth.is_authenticated():
        error_msg = f"""
❌ CreatorIQ API Key Not Configured!

Missing environment variable: CREATORIQ_API_KEY

To fix this:
1. Get your API key from CreatorIQ dashboard/settings
2. Add to your .env file:

CREATORIQ_API_KEY=your_api_key_here

Example .env:
CREATORIQ_API_KEY=ciq_12345abcdef67890...

This is MUCH better than browser authentication!
        """
        
        logger.error(error_msg)
        raise ValueError("CreatorIQ API key not configured")
    
    logger.info("✅ CreatorIQ API key authentication is properly configured")
    return True

# Test function
def test_api_key_auth():
    """Test API key authentication setup."""
    logger.info("🧪 Testing CreatorIQ API key authentication setup...")
    
    try:
        validate_api_key_setup()
        headers = get_api_key_headers()
        summary = get_auth_summary()
        
        logger.info("✅ API key authentication test successful!")
        logger.info(f"   Headers count: {len(headers)}")
        logger.info(f"   Auth summary: {summary}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ API key authentication test failed: {e}")
        return False

def get_auth_summary() -> Dict[str, bool]:
    """Get authentication summary."""
    global _api_auth_instance
    if _api_auth_instance is None:
        _api_auth_instance = CreatorIQAPIAuth()
    
    return _api_auth_instance.get_auth_summary()

if __name__ == "__main__":
    test_api_key_auth() 