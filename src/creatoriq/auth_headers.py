"""
CreatorIQ Authentication Headers

Manages authentication credentials for CreatorIQ GraphQL API requests.
Loads credentials from environment variables for security.
"""

import os
from typing import Dict, Optional
from dotenv import load_dotenv
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Load environment variables from .env file
load_dotenv()

class CreatorIQAuth:
    """
    Authentication manager for CreatorIQ API requests.
    
    Handles loading and managing authentication credentials from environment variables.
    """
    
    def __init__(self):
        self.auth_token = os.getenv('CREATORIQ_AUTH_TOKEN')
        self.cookie = os.getenv('CREATORIQ_COOKIE')
        self.csrf_token = os.getenv('CREATORIQ_CSRF_TOKEN')
        self.user_agent = os.getenv('CREATORIQ_USER_AGENT', 
                                   'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36')
        
        # Log authentication status (without exposing credentials)
        self._log_auth_status()
    
    def _log_auth_status(self):
        """Log authentication status without exposing sensitive data."""
        auth_status = []
        
        if self.auth_token:
            auth_status.append(f"✅ Auth Token: {self.auth_token[:20]}...")
        else:
            auth_status.append("❌ Auth Token: Missing")
        
        if self.cookie:
            auth_status.append(f"✅ Cookie: {len(self.cookie)} chars")
        else:
            auth_status.append("❌ Cookie: Missing")
        
        if self.csrf_token:
            auth_status.append(f"✅ CSRF Token: {self.csrf_token[:10]}...")
        else:
            auth_status.append("❌ CSRF Token: Missing")
        
        logger.info("🔐 CreatorIQ Authentication Status:")
        for status in auth_status:
            logger.info(f"   {status}")
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get complete headers dictionary for GraphQL requests.
        
        Returns:
            Dictionary of headers for API requests
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': self.user_agent,
            'Origin': 'https://app.creatoriq.com',
            'Referer': 'https://app.creatoriq.com/',
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        
        # Add authentication headers if available
        if self.auth_token:
            # Handle case where token already has "Bearer " prefix
            if self.auth_token.startswith("Bearer "):
                headers['Authorization'] = self.auth_token
            else:
                headers['Authorization'] = f"Bearer {self.auth_token}"
        
        if self.cookie:
            headers['Cookie'] = self.cookie
        
        if self.csrf_token:
            headers['X-CSRF-Token'] = self.csrf_token
            headers['X-CSRFToken'] = self.csrf_token  # Some APIs use this variant
        
        return headers
    
    def is_authenticated(self) -> bool:
        """
        Check if we have sufficient authentication credentials.
        
        Returns:
            True if we have at least auth token or cookie
        """
        return bool(self.auth_token or self.cookie)
    
    def get_auth_summary(self) -> Dict[str, bool]:
        """
        Get summary of available authentication methods.
        
        Returns:
            Dictionary showing which auth methods are available
        """
        return {
            'has_auth_token': bool(self.auth_token),
            'has_cookie': bool(self.cookie),
            'has_csrf_token': bool(self.csrf_token),
            'is_authenticated': self.is_authenticated()
        }

# Global auth instance
_auth_instance = None

def get_auth_headers() -> Dict[str, str]:
    """
    Convenience function to get authentication headers.
    
    Returns:
        Dictionary of headers for API requests
    """
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = CreatorIQAuth()
    
    return _auth_instance.get_headers()

def is_authenticated() -> bool:
    """
    Convenience function to check authentication status.
    
    Returns:
        True if authenticated
    """
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = CreatorIQAuth()
    
    return _auth_instance.is_authenticated()

def get_auth_summary() -> Dict[str, bool]:
    """
    Convenience function to get authentication summary.
    
    Returns:
        Dictionary showing authentication status
    """
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = CreatorIQAuth()
    
    return _auth_instance.get_auth_summary()

def validate_auth_setup() -> bool:
    """
    Validate that authentication is properly configured.
    
    Returns:
        True if auth is properly set up
        
    Raises:
        ValueError: If authentication is not properly configured
    """
    auth = CreatorIQAuth()
    
    if not auth.is_authenticated():
        missing_creds = []
        if not auth.auth_token:
            missing_creds.append("CREATORIQ_AUTH_TOKEN")
        if not auth.cookie:
            missing_creds.append("CREATORIQ_COOKIE")
        
        error_msg = f"""
❌ CreatorIQ Authentication Not Configured!

Missing environment variables: {', '.join(missing_creds)}

To fix this:
1. Log into CreatorIQ in your browser
2. Open DevTools → Network tab
3. Find a GraphQL request to /api/reporting/graphql
4. Copy the request headers
5. Add to your .env file:

CREATORIQ_AUTH_TOKEN=Bearer_your_token_here
CREATORIQ_COOKIE=your_full_cookie_string_here
CREATORIQ_CSRF_TOKEN=your_csrf_token_here

Example .env:
CREATORIQ_AUTH_TOKEN=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
CREATORIQ_COOKIE=sessionid=abc123; csrftoken=def456; other_cookies=xyz789
CREATORIQ_CSRF_TOKEN=abc123def456
        """
        
        logger.error(error_msg)
        raise ValueError("CreatorIQ authentication not configured")
    
    logger.info("✅ CreatorIQ authentication is properly configured")
    return True

# Test function
def test_auth_headers():
    """Test authentication headers setup."""
    logger.info("🧪 Testing CreatorIQ authentication setup...")
    
    try:
        validate_auth_setup()
        headers = get_auth_headers()
        summary = get_auth_summary()
        
        logger.info("✅ Authentication test successful!")
        logger.info(f"   Headers count: {len(headers)}")
        logger.info(f"   Auth summary: {summary}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Authentication test failed: {e}")
        return False

if __name__ == "__main__":
    test_auth_headers() 