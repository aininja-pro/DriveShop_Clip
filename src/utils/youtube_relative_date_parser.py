"""
YouTube Relative Date Parser
Extracts publication dates from YouTube's relative date strings like "2 days ago", "3 months ago", etc.
"""

import re
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

def parse_youtube_relative_date(relative_str: str) -> Optional[datetime]:
    """
    Parse YouTube's relative date strings into actual dates.
    
    Examples:
    - "2 hours ago" -> datetime 2 hours before now
    - "3 days ago" -> datetime 3 days before now
    - "1 month ago" -> datetime ~30 days before now
    - "2 years ago" -> datetime ~730 days before now
    
    Args:
        relative_str: String containing relative date (e.g., "2 days ago")
        
    Returns:
        datetime object or None if parsing fails
    """
    if not relative_str:
        return None
        
    # Clean the string
    relative_str = relative_str.strip().lower()
    
    # Common patterns
    patterns = [
        # Standard "X time_unit ago" format
        (r'(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago', 'standard'),
        # "1 day ago" vs "a day ago"
        (r'(a|an|one)\s*(second|minute|hour|day|week|month|year)\s*ago', 'single'),
        # "yesterday", "today"
        (r'(yesterday|today)', 'special'),
        # Streamed/Premiered format
        (r'streamed\s*(\d+)\s*(hour|day|week|month|year)s?\s*ago', 'streamed'),
        (r'premiered\s*(\d+)\s*(hour|day|week|month|year)s?\s*ago', 'premiered'),
    ]
    
    now = datetime.now()
    
    for pattern, pattern_type in patterns:
        match = re.search(pattern, relative_str)
        if match:
            try:
                if pattern_type == 'special':
                    if match.group(1) == 'today':
                        return now.replace(hour=12, minute=0, second=0, microsecond=0)
                    elif match.group(1) == 'yesterday':
                        return (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
                        
                elif pattern_type == 'single':
                    # Handle "a day ago", "an hour ago"
                    unit = match.group(2)
                    return calculate_date_from_relative(1, unit, now)
                    
                else:
                    # Standard numeric format
                    if pattern_type in ['streamed', 'premiered']:
                        number = int(match.group(1))
                        unit = match.group(2)
                    else:
                        number = int(match.group(1))
                        unit = match.group(2)
                    
                    return calculate_date_from_relative(number, unit, now)
                    
            except Exception as e:
                logger.warning(f"Error parsing relative date '{relative_str}': {e}")
                continue
    
    # If no pattern matched, log for debugging
    logger.debug(f"Could not parse relative date: '{relative_str}'")
    return None

def calculate_date_from_relative(number: int, unit: str, reference_date: datetime) -> datetime:
    """
    Calculate actual date from relative time.
    
    Args:
        number: Number of units
        unit: Time unit (second, minute, hour, day, week, month, year)
        reference_date: Date to calculate from (usually now)
        
    Returns:
        Calculated datetime
    """
    unit = unit.lower().rstrip('s')  # Remove plural 's' if present
    
    if unit in ['second', 'sec']:
        return reference_date - timedelta(seconds=number)
    elif unit in ['minute', 'min']:
        return reference_date - timedelta(minutes=number)
    elif unit == 'hour':
        return reference_date - timedelta(hours=number)
    elif unit == 'day':
        return reference_date - timedelta(days=number)
    elif unit == 'week':
        return reference_date - timedelta(weeks=number)
    elif unit == 'month':
        # Approximate: 30 days per month
        return reference_date - timedelta(days=number * 30)
    elif unit == 'year':
        # Approximate: 365 days per year
        return reference_date - timedelta(days=number * 365)
    else:
        logger.warning(f"Unknown time unit: {unit}")
        return reference_date

def extract_youtube_date_from_html(html_content: str) -> Optional[datetime]:
    """
    Extract publication date from YouTube HTML content.
    Looks for relative date strings in various locations.
    
    Args:
        html_content: Raw HTML from YouTube page
        
    Returns:
        datetime object or None if not found
    """
    if not html_content:
        return None
    
    # Common patterns where YouTube shows relative dates
    date_patterns = [
        # In video metadata
        r'"dateText"[^}]*"simpleText"\s*:\s*"([^"]*ago[^"]*)"',
        r'"publishedTimeText"[^}]*"simpleText"\s*:\s*"([^"]*ago[^"]*)"',
        # In video renderer
        r'"publishedTimeText"[^:]*:\s*"([^"]*ago[^"]*)"',
        # Simplified patterns
        r'"simpleText"\s*:\s*"(\d+\s*(?:hour|day|week|month|year)s?\s*ago)"',
        # In accessibility labels
        r'aria-label="[^"]*(\d+\s*(?:hour|day|week|month|year)s?\s*ago)[^"]*"',
        # Generic catch-all for relative dates
        r'(\d+\s*(?:second|minute|hour|day|week|month|year)s?\s*ago)',
        r'((?:a|an)\s*(?:second|minute|hour|day|week|month|year)\s*ago)',
        r'(yesterday|today)',
        # Streamed/Premiered
        r'((?:streamed|premiered)\s*\d+\s*(?:hour|day|week|month|year)s?\s*ago)',
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        if matches:
            # Try each match until we get a valid date
            for match in matches:
                date = parse_youtube_relative_date(match)
                if date:
                    logger.info(f"Found YouTube date from '{match}' -> {date.strftime('%Y-%m-%d')}")
                    return date
    
    return None

def extract_multiple_youtube_dates(html_content: str, limit: int = 20) -> List[Tuple[str, Optional[datetime]]]:
    """
    Extract multiple relative dates from YouTube HTML.
    Returns a list of (date_text, datetime) tuples.
    
    This is useful for matching dates to specific videos when parsing channel pages.
    """
    if not html_content:
        return []
    
    results = []
    seen_dates = set()
    
    # Look for inline-metadata-item spans which often contain dates
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Method 1: Look for metadata spans
    metadata_items = soup.find_all('span', class_='inline-metadata-item')
    for item in metadata_items[:limit * 2]:  # Check more items than needed
        text = item.get_text(strip=True)
        if re.search(r'\d+\s*(second|minute|hour|day|week|month|year)s?\s*ago', text, re.I):
            if text not in seen_dates:
                seen_dates.add(text)
                date = parse_youtube_relative_date(text)
                results.append((text, date))
                if len(results) >= limit:
                    break
    
    # Method 2: Look in aria-labels
    if len(results) < limit:
        elements_with_aria = soup.find_all(attrs={'aria-label': True})
        for elem in elements_with_aria:
            aria_label = elem.get('aria-label', '')
            match = re.search(r'(\d+\s*(?:second|minute|hour|day|week|month|year)s?\s*ago)', aria_label, re.I)
            if match:
                date_text = match.group(1)
                if date_text not in seen_dates:
                    seen_dates.add(date_text)
                    date = parse_youtube_relative_date(date_text)
                    results.append((date_text, date))
                    if len(results) >= limit:
                        break
    
    return results

def extract_video_upload_date(html_content: str) -> Optional[datetime]:
    """
    Extract upload date specifically for a single YouTube video page.
    This is more accurate than extract_youtube_date_from_html() as it looks
    for dates in specific contexts related to the video's metadata.
    
    Args:
        html_content: Raw HTML from a YouTube video page
        
    Returns:
        datetime object or None if not found
    """
    if not html_content:
        return None
    
    # First try to find ISO dates in structured data
    iso_date_patterns = [
        r'"uploadDate"\s*:\s*"([^"]+)"',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"publishDate"\s*:\s*"([^"]+)"',
    ]
    
    for pattern in iso_date_patterns:
        match = re.search(pattern, html_content)
        if match:
            date_str = match.group(1)
            try:
                # Parse ISO date format
                date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                logger.info(f"Found ISO upload date: {date.strftime('%Y-%m-%d')}")
                return date
            except:
                pass
    
    # Look for relative dates specifically in video metadata sections
    # These patterns are more specific to avoid catching dates from comments
    video_metadata_patterns = [
        # In the primary video info renderer
        r'"videoPrimaryInfoRenderer"[^}]*"dateText"[^}]*"simpleText"\s*:\s*"([^"]*ago[^"]*)"',
        # In initial player response
        r'"videoDetails"[^}]*"publishDate"\s*:\s*"([^"]+)"',
        # In microformat
        r'"microformat"[^}]*"publishDate"\s*:\s*"([^"]+)"',
        r'"microformat"[^}]*"uploadDate"\s*:\s*"([^"]+)"',
    ]
    
    for pattern in video_metadata_patterns:
        match = re.search(pattern, html_content, re.DOTALL)
        if match:
            date_str = match.group(1)
            # Check if it's a relative date
            if 'ago' in date_str:
                date = parse_youtube_relative_date(date_str)
                if date:
                    logger.info(f"Found relative upload date in metadata: '{date_str}' -> {date.strftime('%Y-%m-%d')}")
                    return date
            else:
                # Try to parse as ISO date
                try:
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    logger.info(f"Found ISO date in metadata: {date.strftime('%Y-%m-%d')}")
                    return date
                except:
                    pass
    
    # As a last resort, look for the first relative date that's likely the upload date
    # But be more restrictive to avoid comments
    restricted_patterns = [
        # Only in specific metadata contexts
        r'"dateText"\s*:\s*{\s*"simpleText"\s*:\s*"([^"]*ago[^"]*)"',
        r'"publishedTimeText"\s*:\s*{\s*"simpleText"\s*:\s*"([^"]*ago[^"]*)"',
    ]
    
    for pattern in restricted_patterns:
        match = re.search(pattern, html_content)
        if match:
            relative_date_str = match.group(1)
            date = parse_youtube_relative_date(relative_date_str)
            if date:
                logger.info(f"Found relative upload date: '{relative_date_str}' -> {date.strftime('%Y-%m-%d')}")
                return date
    
    return None

def enhance_youtube_metadata_with_date(metadata: dict, html_content: str = None) -> dict:
    """
    Enhance YouTube metadata by adding extracted publication date.
    
    Args:
        metadata: Existing metadata dictionary
        html_content: Optional HTML content to extract date from
        
    Returns:
        Enhanced metadata with 'published_date' field
    """
    if not metadata:
        metadata = {}
    
    # If we already have a date, return as-is
    if metadata.get('published_date'):
        return metadata
    
    # Try to extract from HTML if provided
    if html_content:
        date = extract_youtube_date_from_html(html_content)
        if date:
            metadata['published_date'] = date
            metadata['date_source'] = 'relative_date_parser'
            logger.info(f"Added publication date to metadata: {date.strftime('%Y-%m-%d')}")
    
    return metadata

# Test the parser
if __name__ == "__main__":
    # Test cases
    test_cases = [
        "2 hours ago",
        "1 day ago",
        "3 days ago",
        "1 week ago",
        "2 months ago",
        "1 year ago",
        "yesterday",
        "today",
        "Streamed 5 days ago",
        "Premiered 2 weeks ago",
        "a day ago",
        "an hour ago",
    ]
    
    print("Testing YouTube relative date parser:")
    print("-" * 50)
    
    for test in test_cases:
        result = parse_youtube_relative_date(test)
        if result:
            print(f"'{test}' -> {result.strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"'{test}' -> Could not parse")