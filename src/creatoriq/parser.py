import re
import json
from src.utils.logger import setup_logger

# Use the existing DriveShop logger system
logger = setup_logger(__name__)

def extract_social_urls(html: str, api_responses: list = None) -> list:
    """
    Extract social media URLs using multiple approaches.
    
    Args:
        html: HTML content from page
        api_responses: List of captured API responses (optional)
    
    Returns:
        List of social media URLs
    """
    logger.info(f"🔍 Starting URL extraction from {len(html):,} characters of HTML")
    
    # 🚀 APPROACH 2: Try network-captured API responses first (most likely to succeed)
    if api_responses:
        logger.info(f"📡 Analyzing {len(api_responses)} captured API responses...")
        api_urls = extract_from_api_responses(api_responses)
        
        if api_urls:
            logger.info(f"✅ Successfully extracted {len(api_urls)} URLs from API responses!")
            return api_urls
    
    # 🚀 APPROACH 1: Try to extract from embedded JSON
    logger.info("🔎 Searching for embedded JSON objects in script tags...")
    json_urls = extract_from_embedded_json(html)
    
    if json_urls:
        logger.info(f"✅ Successfully extracted {len(json_urls)} URLs from embedded JSON!")
        return json_urls
    
    # 🔄 FALLBACK: Use regex patterns if both API and JSON extraction fail
    logger.info("⚠️ No API responses or embedded JSON found, falling back to regex extraction...")
    return extract_from_regex_patterns(html)

def extract_from_api_responses(api_responses: list) -> list:
    """
    Extract post URLs from captured API responses.
    
    Args:
        api_responses: List of captured API response objects
        
    Returns:
        List of social media URLs
    """
    logger.info("📡 Processing captured API responses...")
    
    all_urls = []
    
    for i, response in enumerate(api_responses, 1):
        logger.info(f"🔍 Processing API response {i}/{len(api_responses)}: {response['url']}")
        logger.info(f"   📄 Response size: {response['size']:,} chars")
        
        try:
            # Extract URLs from this API response
            urls = extract_urls_from_json_object(response['data'], f"api_response_{i}")
            
            if urls:
                logger.info(f"   🔗 Found {len(urls)} URLs in this API response")
                all_urls.extend(urls)
                
                # Log sample URLs from this response
                sample_urls = urls[:3]
                for j, url in enumerate(sample_urls, 1):
                    platform = get_platform_from_url(url)
                    logger.info(f"      {j}. {platform}: {url}")
                if len(urls) > 3:
                    logger.info(f"      ... and {len(urls) - 3} more URLs")
            else:
                logger.info(f"   ❌ No social media URLs found in this API response")
                
        except Exception as e:
            logger.warning(f"   ❌ Error processing API response {i}: {e}")
    
    if all_urls:
        # Deduplicate
        unique_urls = list(set(all_urls))
        duplicates_removed = len(all_urls) - len(unique_urls)
        
        if duplicates_removed > 0:
            logger.info(f"🧹 Removed {duplicates_removed} duplicate URLs from API responses")
        
        logger.info(f"✅ API extraction result: {len(unique_urls)} unique URLs found")
        
        # Log platform breakdown
        platform_counts = {}
        for url in unique_urls:
            platform = get_platform_from_url(url)
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        logger.info("📊 Platform breakdown from API responses:")
        for platform, count in platform_counts.items():
            logger.info(f"   {platform}: {count} URLs")
        
        return unique_urls
    
    logger.info("❌ No URLs found in API responses")
    return []

def extract_from_embedded_json(html: str) -> list:
    """
    Extract post URLs from embedded JSON objects in script tags.
    
    Searches for common React state patterns like:
    - window.__INITIAL_STATE__ = { ... }
    - window.__PRELOADED_STATE__ = { ... }
    - window.APP_STATE = { ... }
    """
    logger.info("🔍 Searching for embedded JSON state objects...")
    
    # Common patterns for React app state
    json_patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
        r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
        r'window\.APP_STATE\s*=\s*({.*?});',
        r'window\.INITIAL_DATA\s*=\s*({.*?});',
        r'window\.appData\s*=\s*({.*?});',
        r'window\.pageData\s*=\s*({.*?});',
        r'__NEXT_DATA__\s*=\s*({.*?});',
        r'window\.store\s*=\s*({.*?});',
        r'window\.state\s*=\s*({.*?});'
    ]
    
    all_urls = []
    
    for i, pattern in enumerate(json_patterns, 1):
        logger.info(f"📱 Pattern {i}/{len(json_patterns)}: Searching for {pattern.split('=')[0].strip()}...")
        
        try:
            matches = re.findall(pattern, html, re.DOTALL)
            
            if matches:
                logger.info(f"   Found {len(matches)} JSON objects with this pattern")
                
                for j, json_text in enumerate(matches, 1):
                    logger.info(f"   📄 Processing JSON object {j}/{len(matches)}...")
                    
                    try:
                        # Parse the JSON
                        data = json.loads(json_text)
                        logger.info(f"   ✅ Successfully parsed JSON object ({len(json_text):,} chars)")
                        
                        # Extract URLs from this JSON object
                        urls = extract_urls_from_json_object(data)
                        if urls:
                            logger.info(f"   🔗 Found {len(urls)} URLs in this JSON object")
                            all_urls.extend(urls)
                        else:
                            logger.info(f"   ❌ No social media URLs found in this JSON object")
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"   ❌ Failed to parse JSON object {j}: {e}")
                        # Try to clean up the JSON and retry
                        cleaned_json = clean_json_text(json_text)
                        if cleaned_json != json_text:
                            try:
                                data = json.loads(cleaned_json)
                                logger.info(f"   ✅ Successfully parsed cleaned JSON object")
                                urls = extract_urls_from_json_object(data)
                                if urls:
                                    logger.info(f"   🔗 Found {len(urls)} URLs in cleaned JSON object")
                                    all_urls.extend(urls)
                            except json.JSONDecodeError:
                                logger.warning(f"   ❌ Failed to parse even after cleaning")
            else:
                logger.info(f"   No matches found for this pattern")
                
        except Exception as e:
            logger.warning(f"   ❌ Error processing pattern {i}: {e}")
    
    if all_urls:
        # Deduplicate
        unique_urls = list(set(all_urls))
        duplicates_removed = len(all_urls) - len(unique_urls)
        
        if duplicates_removed > 0:
            logger.info(f"🧹 Removed {duplicates_removed} duplicate URLs from JSON extraction")
        
        logger.info(f"✅ JSON extraction result: {len(unique_urls)} unique URLs found")
        
        # Log sample URLs
        if unique_urls:
            logger.info("📋 Sample URLs from JSON:")
            for i, url in enumerate(unique_urls[:3], 1):
                platform = get_platform_from_url(url)
                logger.info(f"   {i}. {platform}: {url}")
            if len(unique_urls) > 3:
                logger.info(f"   ... and {len(unique_urls) - 3} more URLs")
        
        return unique_urls
    
    logger.info("❌ No URLs found in embedded JSON objects")
    return []

def extract_urls_from_json_object(data, path="root") -> list:
    """
    Recursively search through a JSON object to find social media URLs.
    """
    urls = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            # Look for keys that might contain post data
            if any(keyword in key.lower() for keyword in ['post', 'content', 'media', 'url', 'link', 'item', 'data', 'campaign']):
                urls.extend(extract_urls_from_json_object(value, f"{path}.{key}"))
            else:
                urls.extend(extract_urls_from_json_object(value, f"{path}.{key}"))
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            urls.extend(extract_urls_from_json_object(item, f"{path}[{i}]"))
    
    elif isinstance(data, str):
        # Check if this string is a social media URL
        if is_social_media_url(data):
            urls.append(data)
    
    return urls

def is_social_media_url(url: str) -> bool:
    """Check if a URL is a social media post URL."""
    if not isinstance(url, str) or not url.startswith('http'):
        return False
    
    social_patterns = [
        r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+/',
        r'https?://(?:www\.)?tiktok\.com/@[\w.]+/video/[\d]+',
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://(?:www\.)?twitter\.com/[a-zA-Z0-9_]+/status/[\d]+',
        r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9.]+/posts/[\d]+'
    ]
    
    for pattern in social_patterns:
        if re.match(pattern, url):
            return True
    
    return False

def get_platform_from_url(url: str) -> str:
    """Get platform name from URL."""
    if 'instagram.com' in url:
        return 'Instagram'
    elif 'tiktok.com' in url:
        return 'TikTok'
    elif 'youtube.com' in url:
        return 'YouTube'
    elif 'twitter.com' in url:
        return 'Twitter'
    elif 'facebook.com' in url:
        return 'Facebook'
    else:
        return 'Unknown'

def clean_json_text(json_text: str) -> str:
    """
    Clean up JSON text that might have trailing commas or other issues.
    """
    # Remove trailing commas before closing braces/brackets
    json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
    
    # Remove any trailing semicolons
    json_text = json_text.rstrip(';')
    
    return json_text

def extract_from_regex_patterns(html: str) -> list:
    """
    Fallback method: Extract URLs using regex patterns on the HTML.
    This is the original method.
    """
    logger.info("🔎 Using regex patterns as fallback...")
    
    patterns = [
        r'https:\/\/www\.instagram\.com\/[a-zA-Z0-9_.]+\/',
        r'https:\/\/www\.tiktok\.com\/@[\w.]+\/video\/[\d]+',
        r'https:\/\/www\.youtube\.com\/watch\?v=[\w-]+',
        r'https:\/\/twitter\.com\/[a-zA-Z0-9_]+\/status\/[\d]+',
        r'https:\/\/www\.facebook\.com\/[a-zA-Z0-9.]+\/posts\/[\d]+'
    ]

    urls = []
    
    for i, pattern in enumerate(patterns, 1):
        platform = ["Instagram", "TikTok", "YouTube", "Twitter", "Facebook"][i-1]
        logger.info(f"📱 Pattern {i}/5: Searching for {platform} URLs...")
        
        matches = re.findall(pattern, html)
        logger.info(f"   Found {len(matches)} {platform} URLs")
        
        urls.extend(matches)

    logger.info(f"🔗 Total URLs found before deduplication: {len(urls)}")
    
    # Deduplicate
    unique_urls = list(set(urls))
    duplicates_removed = len(urls) - len(unique_urls)
    
    if duplicates_removed > 0:
        logger.info(f"🧹 Removed {duplicates_removed} duplicate URLs")
    
    logger.info(f"✅ Regex extraction result: {len(unique_urls)} unique social media URLs extracted")
    
    # Log first few URLs as examples
    if unique_urls:
        logger.info("📋 Sample URLs found:")
        for i, url in enumerate(unique_urls[:3], 1):
            platform = get_platform_from_url(url)
            logger.info(f"   {i}. {platform}: {url}")
        if len(unique_urls) > 3:
            logger.info(f"   ... and {len(unique_urls) - 3} more URLs")
    
    return unique_urls 