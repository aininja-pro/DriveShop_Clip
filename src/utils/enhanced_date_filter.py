"""
Enhanced Date Filtering with Platform-Specific Logic
Prevents old content while being smart about YouTube's date extraction challenges
"""

import re
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def is_content_acceptable(
    content_date: Optional[datetime], 
    loan_start_date: Optional[datetime], 
    content_type: str = "unknown",
    content_url: Optional[str] = None
) -> bool:
    """
    Unified date filtering with platform-specific handling.
    
    Args:
        content_date: When the content was published (may be None)
        loan_start_date: Loan start date for relative filtering
        content_type: Type of content (youtube, tiktok, instagram, web, article)
        content_url: URL of the content (for additional heuristics)
        
    Returns:
        bool: True if content should be accepted, False if rejected
    """
    # Configuration
    MAX_AGE_MONTHS = 18  # Absolute limit for content WITH dates
    DAYS_BEFORE_LOAN = 60  # Allow content up to 60 days before loan
    DAYS_AFTER_LOAN = 180  # Look up to 180 days after loan
    
    today = datetime.now()
    
    # Case 1: We have a content date
    if content_date:
        # Check absolute age
        content_age_days = (today - content_date).days
        
        # Special handling for future dates (might be extraction errors)
        if content_age_days < -7:  # Allow up to 7 days in future for timezone issues
            logger.warning(f"Content date is in the future ({content_date}) - likely extraction error")
            return False
            
        if content_age_days > (MAX_AGE_MONTHS * 30):
            logger.warning(f"Content too old: {content_age_days} days old (max: {MAX_AGE_MONTHS} months)")
            return False
            
        # Check relative to loan date if available
        if loan_start_date:
            earliest = loan_start_date - timedelta(days=DAYS_BEFORE_LOAN)
            latest = loan_start_date + timedelta(days=DAYS_AFTER_LOAN)
            
            if not (earliest <= content_date <= latest):
                if content_date < earliest:
                    days_before = (earliest - content_date).days
                    logger.warning(f"Content {days_before} days before acceptable window")
                else:
                    days_after = (content_date - latest).days
                    logger.warning(f"Content {days_after} days after acceptable window")
                return False
                
        logger.info(f"✅ Content date {content_date.strftime('%Y-%m-%d')} is acceptable")
        return True
        
    # Case 2: No content date - handle by platform
    else:
        # YouTube: Generally trust it (date extraction is unreliable)
        if content_type == "youtube":
            logger.info("YouTube content without date - accepting (dates rarely extractable)")
            # But still check URL for obvious old content
            if content_url and _is_url_obviously_old(content_url):
                logger.warning("YouTube URL indicates very old content - rejecting")
                return False
            return True
            
        # TikTok/Instagram: Be more cautious but still allow
        elif content_type in ["tiktok", "instagram"]:
            logger.warning(f"{content_type.title()} content without date - accepting with caution")
            # Check URL patterns
            if content_url and _is_url_obviously_old(content_url):
                logger.warning(f"{content_type.title()} URL indicates old content - rejecting")
                return False
            return True
            
        # Web articles: Apply stricter rules
        elif content_type in ["web", "article"]:
            # Check URL for year indicators
            if content_url:
                # Look for year in URL (e.g., /2020/05/article-name)
                year_match = re.search(r'/20(\d{2})/', content_url)
                if year_match:
                    url_year = 2000 + int(year_match.group(1))
                    current_year = today.year
                    if current_year - url_year > 2:
                        logger.warning(f"Web article URL indicates old content: {url_year} - rejecting")
                        return False
                        
                # Check for archive indicators
                if any(indicator in content_url.lower() for indicator in ['archive', 'wayback', 'cached']):
                    logger.warning("URL appears to be archived content - rejecting")
                    return False
                    
            # For web content without determinable dates, reject for safety
            logger.warning("Web content without determinable date - rejecting for safety")
            return False
            
        # Unknown content type
        else:
            logger.warning(f"Unknown content type '{content_type}' without date - rejecting for safety")
            return False

def _is_url_obviously_old(url: str) -> bool:
    """
    Check if URL contains obvious indicators of old content.
    
    Args:
        url: URL to check
        
    Returns:
        bool: True if URL appears to be for old content
    """
    if not url:
        return False
        
    url_lower = url.lower()
    
    # Check for very old years in URL
    import re
    # Look for 4-digit years before 2022
    year_matches = re.findall(r'/20(\d{2})/', url)
    for year_suffix in year_matches:
        year = 2000 + int(year_suffix)
        if year < 2022:  # Content from before 2022 is likely too old
            return True
            
    # Check for archive/cache indicators
    old_indicators = [
        'archive.org',
        'archive.is',
        'wayback',
        'cached',
        '/cache/',
        'webcache.googleusercontent',
    ]
    
    return any(indicator in url_lower for indicator in old_indicators)

def get_date_filter_summary() -> dict:
    """
    Get a summary of current date filtering configuration.
    
    Returns:
        dict: Configuration summary
    """
    return {
        "max_age_months": 18,
        "days_before_loan": 60,
        "days_after_loan": 180,
        "platform_rules": {
            "youtube": "Accept without date (extraction unreliable)",
            "tiktok": "Accept without date with caution",
            "instagram": "Accept without date with caution",
            "web": "Reject without date (likely old content)",
            "article": "Reject without date (likely old content)"
        }
    }

# Test the filter
if __name__ == "__main__":
    from datetime import datetime, timedelta
    
    # Test cases
    today = datetime.now()
    loan_start = today - timedelta(days=30)  # Loan started 30 days ago
    
    test_cases = [
        # (content_date, content_type, url, expected_result, description)
        (today - timedelta(days=10), "youtube", None, True, "Recent YouTube video"),
        (today - timedelta(days=500), "youtube", None, False, "Old YouTube video (>18 months)"),
        (None, "youtube", "https://youtube.com/watch?v=abc123", True, "YouTube without date"),
        (None, "youtube", "https://youtube.com/2020/old-video", False, "YouTube with old year in URL"),
        (None, "web", "https://example.com/article", False, "Web article without date"),
        (None, "web", "https://example.com/2020/05/article", False, "Web article with old year"),
        (loan_start - timedelta(days=30), "youtube", None, True, "Video 30 days before loan"),
        (loan_start - timedelta(days=90), "youtube", None, False, "Video 90 days before loan"),
        (loan_start + timedelta(days=100), "youtube", None, True, "Video 100 days after loan"),
        (loan_start + timedelta(days=200), "youtube", None, False, "Video 200 days after loan"),
    ]
    
    print("Testing Enhanced Date Filter:")
    print("-" * 80)
    
    for content_date, content_type, url, expected, description in test_cases:
        result = is_content_acceptable(content_date, loan_start, content_type, url)
        status = "✅" if result == expected else "❌"
        print(f"{status} {description}: {result} (expected: {expected})")
        if content_date:
            print(f"   Content date: {content_date.strftime('%Y-%m-%d')}")
        else:
            print(f"   Content date: None")
        print(f"   Type: {content_type}, URL: {url or 'None'}")
        print()