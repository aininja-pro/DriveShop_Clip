"""
Date extraction utilities for web content and YouTube videos.
Handles extracting publication dates from various sources and formats.
"""

import re
import json
from typing import Optional
from datetime import datetime
from bs4 import BeautifulSoup
import dateutil.parser
import logging

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def extract_date_from_url(url: str) -> Optional[datetime]:
    """
    Extract date from URL path patterns.
    Very reliable for URLs that contain year information.
    
    Args:
        url: URL to check for date patterns
        
    Returns:
        datetime object or None if no date found
    """
    if not url:
        return None
    
    # Look for year patterns in URL path
    # Examples: 
    # - /2021-honda-odyssey/
    # - /reviews/441828/2021-honda-odyssey-first-drive/
    # - /2024/01/15/article-title/
    
    year_patterns = [
        r'/(\d{4})-[^/]*/',  # /2021-honda-odyssey/
        r'/(\d{4})/\d{2}/\d{2}/',  # /2024/01/15/
        r'/(\d{4})/\d{2}/',  # /2024/01/
        r'/(\d{4})/',  # /2024/
        r'(\d{4})-[a-zA-Z-]+',  # 2021-honda-odyssey anywhere in path
    ]
    
    current_year = datetime.now().year
    
    for pattern in year_patterns:
        matches = re.findall(pattern, url)
        for match in matches:
            try:
                year = int(match)
                # Sanity check: year should be reasonable (2000-current year)
                if 2000 <= year <= current_year:
                    # Return January 1st of that year as approximation
                    date = datetime(year, 1, 1)
                    logger.debug(f"Found URL year: {year} from {url}")
                    return date
            except (ValueError, TypeError):
                continue
    
    return None

def extract_date_from_html(html: str, url: str = "") -> Optional[datetime]:
    """
    Extract publication date from HTML content.
    Tries multiple methods in order of reliability.
    
    Args:
        html: HTML content to extract date from
        url: URL of the content (for context/debugging)
        
    Returns:
        datetime object or None if no date found
    """
    soup = BeautifulSoup(html, 'lxml')
    
    # DISABLED: URL date extraction is too aggressive and returns Jan 1st defaults
    # Method 0: Check URL for year patterns first (fast and reliable)
    # if url:
    #     url_date = extract_date_from_url(url)
    #     if url_date:
    #         logger.debug(f"Found date from URL: {url_date}")
    #         return url_date
    
    # Method 1: Structured data (JSON-LD, microdata)
    date = extract_date_from_structured_data(soup)
    if date:
        logger.info(f"📅 Found date from structured data: {date.strftime('%Y-%m-%d')} for {url}")
        return date
    
    # Method 2: Meta tags
    date = extract_date_from_meta_tags(soup)
    if date:
        logger.info(f"📅 Found date from meta tags: {date.strftime('%Y-%m-%d')} for {url}")
        return date
    
    # Method 3: Common CSS selectors
    date = extract_date_from_selectors(soup)
    if date:
        logger.info(f"📅 Found date from CSS selectors: {date.strftime('%Y-%m-%d')} for {url}")
        return date
    
    # Method 4: Site-specific patterns
    date = extract_date_site_specific(soup, url)
    if date:
        logger.info(f"📅 Found date from site-specific patterns: {date.strftime('%Y-%m-%d')} for {url}")
        return date
    
    # Method 5: Text pattern matching
    date = extract_date_from_text_patterns(soup)
    if date:
        logger.info(f"📅 Found date from text patterns: {date.strftime('%Y-%m-%d')} for {url}")
        return date
    
    logger.warning(f"⚠️ Could not extract publication date from: {url}")
    return None

def extract_date_from_structured_data(soup: BeautifulSoup) -> Optional[datetime]:
    """Extract date from JSON-LD and microdata structured data."""
    
    # JSON-LD
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            
            # Handle single object or array
            if isinstance(data, list):
                data = data[0] if data else {}
            
            # Look for common date fields
            date_fields = ['datePublished', 'dateCreated', 'uploadDate', 'dateModified']
            for field in date_fields:
                if field in data and data[field]:
                    return parse_date_string(data[field])
                    
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
    
    # Microdata
    for element in soup.find_all(attrs={'itemprop': ['datePublished', 'dateCreated', 'uploadDate']}):
        date_str = element.get('datetime') or element.get('content') or element.get_text()
        if date_str:
            date = parse_date_string(date_str)
            if date:
                return date
    
    return None

def extract_date_from_meta_tags(soup: BeautifulSoup) -> Optional[datetime]:
    """Extract date from meta tags."""
    
    meta_properties = [
        'article:published_time',
        'article:created_time',
        'article:modified_time',
        'og:published_time',
        'og:updated_time',
        'dc.date',
        'dc.date.created',
        'date',
        'publish_date',
        'publication_date',
        'created_date'
    ]
    
    for prop in meta_properties:
        # Try property attribute
        meta = soup.find('meta', {'property': prop})
        if not meta:
            # Try name attribute
            meta = soup.find('meta', {'name': prop})
        
        if meta:
            content = meta.get('content')
            if content:
                date = parse_date_string(content)
                if date:
                    return date
    
    return None

def extract_date_from_selectors(soup: BeautifulSoup) -> Optional[datetime]:
    """Extract date using common CSS selectors."""
    
    selectors = [
        'time[datetime]',
        '.published-date',
        '.publish-date',
        '.publication-date',
        '.article-date',
        '.post-date',
        '.date-published',
        '.entry-date',
        '.byline-date',
        '.timestamp',
        '.date',
        'span.date',
        'div.date',
        'p.date'
    ]
    
    for selector in selectors:
        elements = soup.select(selector)
        for element in elements:
            # Check datetime attribute first
            datetime_attr = element.get('datetime')
            if datetime_attr:
                date = parse_date_string(datetime_attr)
                if date:
                    return date
            
            # Check text content
            text = element.get_text().strip()
            if text:
                date = parse_date_string(text)
                if date:
                    return date
    
    return None

def extract_date_site_specific(soup: BeautifulSoup, url: str) -> Optional[datetime]:
    """Extract dates using site-specific patterns."""
    
    if 'motor1.com' in url:
        # Motor1 specific patterns
        for selector in ['.post-meta-date', '.byline__date', '.article-meta .date']:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                date = parse_date_string(text)
                if date:
                    return date
    
    elif 'caranddriver.com' in url:
        # Car and Driver specific patterns
        for selector in ['.byline-date', '.publish-date', '.timestamp']:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                date = parse_date_string(text)
                if date:
                    return date
    
    elif 'roadandtrack.com' in url:
        # Road and Track specific patterns with detailed debugging
        logger.info(f"🔍 ROADANDTRACK DEBUG: Searching for date elements in {url}")
        
        selectors = ['.byline-date', '.publish-date', '.timestamp', '.date-published', 'time[datetime]', '.article-date']
        
        for selector in selectors:
            elements = soup.select(selector)  # Use select() to get all matches, not just first
            logger.info(f"🔍 ROADANDTRACK DEBUG: Selector '{selector}' found {len(elements)} elements")
            
            for i, element in enumerate(elements):
                # Check datetime attribute first
                datetime_attr = element.get('datetime')
                if datetime_attr:
                    logger.info(f"🔍 ROADANDTRACK DEBUG: Element {i+1} datetime='{datetime_attr}'")
                    date = parse_date_string(datetime_attr)
                    if date:
                        logger.info(f"✅ ROADANDTRACK DEBUG: Successfully parsed datetime attribute: {date.strftime('%Y-%m-%d')}")
                        return date
                
                # Check text content
                text = element.get_text().strip()
                if text:
                    logger.info(f"🔍 ROADANDTRACK DEBUG: Element {i+1} text='{text}'")
                    date = parse_date_string(text)
                    if date:
                        logger.info(f"✅ ROADANDTRACK DEBUG: Successfully parsed text content: {date.strftime('%Y-%m-%d')}")
                        return date
                    else:
                        logger.info(f"❌ ROADANDTRACK DEBUG: Failed to parse text '{text}'")
        
        # Additional debugging - look for any time elements
        all_time_elements = soup.find_all('time')
        logger.info(f"🔍 ROADANDTRACK DEBUG: Found {len(all_time_elements)} total <time> elements")
        for i, time_elem in enumerate(all_time_elements):
            datetime_attr = time_elem.get('datetime')
            text_content = time_elem.get_text().strip()
            logger.info(f"🔍 ROADANDTRACK DEBUG: <time> element {i+1}: datetime='{datetime_attr}', text='{text_content}'")
        
        # Look for any elements with date-related classes
        date_elements = soup.find_all(class_=lambda x: x and any(keyword in x.lower() for keyword in ['date', 'time', 'publish']))
        logger.info(f"🔍 ROADANDTRACK DEBUG: Found {len(date_elements)} elements with date-related classes")
        for i, elem in enumerate(date_elements[:5]):  # Limit to first 5 to avoid spam
            class_name = elem.get('class')
            text_content = elem.get_text().strip()[:50]  # First 50 chars
            logger.info(f"🔍 ROADANDTRACK DEBUG: Date element {i+1}: class='{class_name}', text='{text_content}...'")
        
        logger.info(f"❌ ROADANDTRACK DEBUG: No valid date found with site-specific selectors")
    
    elif 'edmunds.com' in url:
        # Edmunds specific patterns
        for selector in ['.publish-date', '.article-date', '.byline .date']:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                date = parse_date_string(text)
                if date:
                    return date
    
    return None

def extract_date_from_text_patterns(soup: BeautifulSoup) -> Optional[datetime]:
    """Extract dates using regex patterns on visible text."""
    
    # Get all text content
    text = soup.get_text()
    
    # Common date patterns
    date_patterns = [
        r'Published:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
        r'Posted:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
        r'Created:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\d{4}-\d{2}-\d{2})',
        r'([A-Za-z]+ \d{1,2},? \d{4})',
        r'(\d{1,2} [A-Za-z]+ \d{4})'
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            date = parse_date_string(match)
            if date:
                # Basic sanity check - not too old or in the future
                current_date = datetime.now()
                if (current_date - date).days < 3650 and date <= current_date:  # Not older than 10 years
                    return date
    
    return None

def parse_date_string(date_str: str) -> Optional[datetime]:
    """
    Parse a date string into a datetime object.
    Handles various formats and edge cases.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None
    
    try:
        # Clean the string
        original_date_str = str(date_str)
        date_str = str(date_str).strip()
        
        # Remove common prefixes
        prefixes = ['Published:', 'Posted:', 'Created:', 'Date:', 'Updated:']
        for prefix in prefixes:
            if date_str.startswith(prefix):
                date_str = date_str[len(prefix):].strip()
        
        logger.debug(f"🔍 DATE PARSE DEBUG: Original='{original_date_str}' -> Cleaned='{date_str}'")
        
        # Use dateutil parser which is very flexible
        parsed_date = dateutil.parser.parse(date_str)
        
        logger.info(f"📅 DATE PARSE SUCCESS: '{original_date_str}' -> {parsed_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Basic sanity check
        current_date = datetime.now()
        if parsed_date > current_date:
            # Date is in the future, probably parsed incorrectly
            logger.warning(f"⚠️ DATE PARSE WARNING: Future date detected: {parsed_date.strftime('%Y-%m-%d')} > {current_date.strftime('%Y-%m-%d')}")
            return None
        
        if (current_date - parsed_date).days > 3650:
            # Date is more than 10 years old, probably not what we want
            logger.warning(f"⚠️ DATE PARSE WARNING: Very old date detected: {parsed_date.strftime('%Y-%m-%d')} (>10 years old)")
            return None
        
        return parsed_date
    
    except (ValueError, TypeError, OverflowError) as e:
        logger.debug(f"❌ DATE PARSE FAILED: '{original_date_str}' -> Error: {e}")
        return None

def extract_youtube_upload_date(video_metadata: dict) -> Optional[datetime]:
    """
    Extract upload date from YouTube video metadata.
    
    Args:
        video_metadata: Dictionary containing video metadata
        
    Returns:
        datetime object or None if not found
    """
    if not video_metadata:
        return None
    
    # Try different date fields that might be present
    date_fields = ['upload_date', 'uploadDate', 'published', 'datePublished']
    
    for field in date_fields:
        if field in video_metadata and video_metadata[field]:
            date = parse_date_string(str(video_metadata[field]))
            if date:
                return date
    
    return None 