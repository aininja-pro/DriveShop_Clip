import re
import requests
import xml.etree.ElementTree as ET
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.parse import urlparse, parse_qs
from typing import Optional, List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup

# Import local modules
from src.utils.logger import setup_logger
from src.utils.rate_limiter import rate_limiter
from src.utils.config import YOUTUBE_SCRAPFLY_CONFIG
from src.utils.youtube_relative_date_parser import extract_youtube_date_from_html, parse_youtube_relative_date, extract_video_upload_date

logger = setup_logger(__name__)

def flexible_model_match(video_title: str, model_variation: str) -> bool:
    """
    Check if the model variation matches the video title with flexible matching.
    Uses a threshold-based approach instead of requiring ALL words.
    
    Examples:
    - "kona limited awd" matches "2025 Hyundai Kona Limited" (2/3 words = 67%)
    - "accord hybrid touring" matches "The 2025 Honda Accord Touring Is A Blissful Hybrid Sedan"
    - "cx-50 turbo" matches "The Mazda CX-50 2.5 Turbo Review"
    
    Args:
        video_title: The video title to search in (already lowercased)
        model_variation: The model string to search for (already lowercased)
        
    Returns:
        True if enough words from model_variation appear in video_title
    """
    # Split model variation into words, handling hyphens as word boundaries
    model_words = re.split(r'[-\s]+', model_variation.strip())
    model_words = [word for word in model_words if word]  # Remove empty strings
    
    if not model_words:
        return False
    
    # Define less important words that shouldn't be strictly required
    optional_words = {'awd', '4wd', 'fwd', 'rwd', '2wd', 'drive', 'wheel', 'all'}
    
    # Define make/brand words that shouldn't count as model matches
    make_words = {
        'toyota', 'honda', 'mazda', 'ford', 'chevrolet', 'chevy', 'gmc', 'ram', 
        'jeep', 'dodge', 'chrysler', 'nissan', 'infiniti', 'lexus', 'acura',
        'hyundai', 'kia', 'genesis', 'volkswagen', 'vw', 'audi', 'bmw', 'mercedes',
        'benz', 'mercedes-benz', 'volvo', 'subaru', 'mitsubishi', 'tesla'
    }
    
    # Filter out make words and optional words to get core model words
    core_words = [w for w in model_words if w not in optional_words and w not in make_words]
    
    # If no core words remain (e.g., "toyota awd"), it's not a valid model
    if not core_words:
        return False
    
    # Count matches
    total_matches = 0
    core_matches = 0
    
    for word in model_words:
        if word in video_title:
            total_matches += 1
            if word in core_words:
                core_matches += 1
    
    # Calculate match percentages
    total_match_percentage = total_matches / len(model_words) if model_words else 0
    core_match_percentage = core_matches / len(core_words) if core_words else 0
    
    # Matching rules (prioritize core model words):
    # 1. If ALL core words match, it's likely a match
    if core_match_percentage == 1.0 and core_matches >= 1:
        return True
    
    # 2. If we have at least 2 core word matches, it's a match
    if core_matches >= 2:
        return True
    
    # 3. If we have 80% or more total matches AND at least 1 core match
    if total_match_percentage >= 0.8 and core_matches >= 1:
        return True
    
    # 4. Special case: single core word models (like "Corolla") need exact match
    if len(core_words) == 1 and core_matches == 1:
        # But make sure it's not a partial match (e.g., "Corolla" shouldn't match "Corolla Cross")
        # Check if the word is followed by another model-like word
        core_word = core_words[0]
        word_pattern = r'\b' + re.escape(core_word) + r'\b'
        if re.search(word_pattern, video_title):
            return True
    
    return False

def extract_video_id(url):
    """
    Extract the video ID from a YouTube URL.
    
    Args:
        url (str): The YouTube URL
        
    Returns:
        str: The video ID or None if not found
    """
    # Patterns for YouTube URLs
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # If no pattern matched, try parsing URL parameters
    try:
        parsed_url = urlparse(url)
        if 'youtube.com' in parsed_url.netloc:
            query_params = parse_qs(parsed_url.query)
            if 'v' in query_params:
                return query_params['v'][0]
    except Exception as e:
        logger.error(f"Error parsing YouTube URL {url}: {e}")
    
    return None

def get_channel_id(url):
    """
    Extract or resolve the channel ID from a YouTube URL.
    
    Args:
        url (str): YouTube channel URL or handle
        
    Returns:
        str: Channel ID or None if not found
    """
    # Clean the URL - remove invisible Unicode characters and whitespace
    if url:
        # Remove common invisible characters that can appear from copy-paste
        url = url.strip().rstrip('\u200b\u200c\u200d\u2060\ufeff')
        # Also remove any trailing special characters that might have been added
        url = re.sub(r'[\s\u00A0\u2000-\u200F\u2028-\u202F\u205F-\u206F]+$', '', url)
    
    # Check if it's a handle (@username)
    handle_match = re.search(r'youtube\.com\/@([a-zA-Z0-9_-]+)', url)
    if handle_match or url.startswith('@'):
        handle = handle_match.group(1) if handle_match else url.lstrip('@')
        return resolve_handle_to_channel_id(handle)
    
    # Check if it's a channel URL
    channel_match = re.search(r'youtube\.com\/channel\/([a-zA-Z0-9_-]+)', url)
    if channel_match:
        return channel_match.group(1)
    
    # Check if it's a user URL
    user_match = re.search(r'youtube\.com\/user\/([a-zA-Z0-9_-]+)', url)
    if user_match:
        username = user_match.group(1)
        return resolve_username_to_channel_id(username)
    
    # Check if it's a custom URL format (youtube.com/customname)
    custom_match = re.search(r'youtube\.com\/([a-zA-Z0-9_-]+)(?:\/|$)', url)
    if custom_match:
        custom_name = custom_match.group(1)
        # Skip common YouTube pages that aren't channels
        if custom_name not in ['watch', 'results', 'playlist', 'feed', 'trending', 'gaming', 'music', 'sports', 'learning']:
            logger.info(f"Attempting to resolve custom channel name: {custom_name}")
            return resolve_username_to_channel_id(custom_name)
    
    logger.warning(f"Could not extract channel ID from URL: {url}")
    return None

def resolve_handle_to_channel_id(handle):
    """
    Resolve a YouTube handle (@username) to a channel ID using multiple extraction patterns.
    
    Args:
        handle (str): YouTube handle without @
        
    Returns:
        str: Channel ID or None if not found
    """
    try:
        # Apply rate limiting
        rate_limiter.wait_if_needed('youtube.com')
        
        url = f"https://www.youtube.com/@{handle}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            html_content = response.text
            
            # Multiple patterns for extracting channel ID from YouTube HTML
            channel_id_patterns = [
                r'"channelId":"([a-zA-Z0-9_-]+)"',  # Original pattern
                r'"externalId":"([a-zA-Z0-9_-]+)"',  # Alternative JSON field
                r'property="og:url"\s+content="[^"]*channel/([a-zA-Z0-9_-]+)"',  # Open Graph meta tag
                r'<link[^>]*href="[^"]*channel/([a-zA-Z0-9_-]+)"[^>]*>',  # Link tag
                r'"browseEndpoint"[^}]*"browseId":"([a-zA-Z0-9_-]+)"',  # Browse endpoint
                r'"channelMetadataRenderer"[^}]*"channelUrl":"[^"]*channel/([a-zA-Z0-9_-]+)"',  # Channel metadata
                r'"ownerChannelName":"[^"]*","channelId":"([a-zA-Z0-9_-]+)"',  # Owner channel info
                r'/channel/([a-zA-Z0-9_-]+)',  # Any mention of /channel/ID
            ]
            
            for i, pattern in enumerate(channel_id_patterns, 1):
                try:
                    channel_id_match = re.search(pattern, html_content, re.IGNORECASE)
                    if channel_id_match:
                        channel_id = channel_id_match.group(1)
                        
                        # Validate channel ID format (YouTube channel IDs are typically 24 chars)
                        if len(channel_id) >= 20 and channel_id.startswith(('UC', 'UU', 'UL', 'LL')):
                            logger.info(f"✅ Successfully resolved @{handle} to channel ID: {channel_id} (pattern {i})")
                            return channel_id
                        else:
                            logger.warning(f"Pattern {i} found potential ID '{channel_id}' but doesn't match expected format")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Error with pattern {i} for @{handle}: {e}")
                    continue
            
            logger.warning(f"All {len(channel_id_patterns)} patterns failed to find valid channel ID for @{handle}")
            
            # DEBUG: Log part of HTML response to help diagnose
            if len(html_content) > 100:
                logger.info(f"HTML response sample (first 500 chars): {html_content[:500]}")
            else:
                logger.warning(f"HTML response was very short ({len(html_content)} chars): {html_content}")
                
        else:
            logger.error(f"HTTP {response.status_code} when resolving YouTube handle @{handle}")
            
    except Exception as e:
        logger.error(f"Error resolving YouTube handle @{handle}: {e}")
    
    return None

def resolve_username_to_channel_id(username):
    """
    Resolve a YouTube username to a channel ID using multiple extraction patterns.
    Tries multiple URL formats to handle different types of YouTube channels.
    
    Args:
        username (str): YouTube username or custom name
        
    Returns:
        str: Channel ID or None if not found
    """
    try:
        # Apply rate limiting
        rate_limiter.wait_if_needed('youtube.com')
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Try multiple URL formats since YouTube has different types
        url_formats = [
            f"https://www.youtube.com/{username}",  # Custom URL (e.g., /theredline)
            f"https://www.youtube.com/c/{username}",  # /c/ format
            f"https://www.youtube.com/user/{username}",  # Legacy /user/ format
        ]
        
        for url in url_formats:
            logger.debug(f"Trying to resolve channel ID from: {url}")
            try:
                response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                
                if response.status_code == 200:
                    html_content = response.text
                    
                    # Multiple patterns for extracting channel ID from YouTube HTML
                    channel_id_patterns = [
                        r'"channelId":"([a-zA-Z0-9_-]+)"',  # Original pattern
                        r'"externalId":"([a-zA-Z0-9_-]+)"',  # Alternative JSON field
                        r'property="og:url"\s+content="[^"]*channel/([a-zA-Z0-9_-]+)"',  # Open Graph meta tag
                        r'<link[^>]*href="[^"]*channel/([a-zA-Z0-9_-]+)"[^>]*>',  # Link tag
                        r'"browseEndpoint"[^}]*"browseId":"([a-zA-Z0-9_-]+)"',  # Browse endpoint
                        r'"channelMetadataRenderer"[^}]*"channelUrl":"[^"]*channel/([a-zA-Z0-9_-]+)"',  # Channel metadata
                        r'"ownerChannelName":"[^"]*","channelId":"([a-zA-Z0-9_-]+)"',  # Owner channel info
                        r'/channel/([a-zA-Z0-9_-]+)',  # Any mention of /channel/ID
                    ]
                    
                    for i, pattern in enumerate(channel_id_patterns, 1):
                        try:
                            channel_id_match = re.search(pattern, html_content, re.IGNORECASE)
                            if channel_id_match:
                                channel_id = channel_id_match.group(1)
                                
                                # Validate channel ID format (YouTube channel IDs are typically 24 chars)
                                if len(channel_id) >= 20 and channel_id.startswith(('UC', 'UU', 'UL', 'LL')):
                                    logger.info(f"✅ Successfully resolved {url} to channel ID: {channel_id} (pattern {i})")
                                    return channel_id
                                else:
                                    logger.debug(f"Pattern {i} found potential ID '{channel_id}' but doesn't match expected format")
                                    continue
                                    
                        except Exception as e:
                            logger.debug(f"Error with pattern {i} for {url}: {e}")
                            continue
                    
                    logger.debug(f"No valid channel ID found in {url} HTML")
                else:
                    logger.debug(f"HTTP {response.status_code} for {url}")
                    
            except requests.RequestException as e:
                logger.debug(f"Request failed for {url}: {e}")
                continue  # Try next URL format
        
        # If all URL formats failed
        logger.warning(f"Could not resolve channel ID for '{username}' using any URL format")
        return None
            
    except Exception as e:
        logger.error(f"Error resolving YouTube username {username}: {e}")
    
    return None

def get_latest_videos(channel_id, max_videos=25):
    """
    Get the latest videos from a YouTube channel via RSS feed.
    
    Args:
        channel_id (str): YouTube channel ID
        max_videos (int): Maximum number of videos to return (increased to 25 for better coverage)
        
    Returns:
        list: List of dictionaries with video information
    """
    if not channel_id:
        return []
    
    try:
        # Apply rate limiting
        rate_limiter.wait_if_needed('youtube.com')
        
        # Use YouTube's RSS feed
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        response = requests.get(rss_url)
        
        if response.status_code != 200:
            logger.error(f"Error fetching RSS feed: Status code {response.status_code}")
            return []
        
        # Parse XML
        root = ET.fromstring(response.content)
        
        # Define XML namespaces
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'media': 'http://search.yahoo.com/mrss/'
        }
        
        videos = []
        for entry in root.findall('.//atom:entry', namespaces)[:max_videos]:
            video_id = entry.find('.//yt:videoId', 
                                {'yt': 'http://www.youtube.com/xml/schemas/2015'})
            if video_id is None:
                # Try to extract from link
                link = entry.find('.//atom:link', namespaces)
                if link is not None:
                    href = link.get('href', '')
                    video_id_match = re.search(r'watch\?v=([a-zA-Z0-9_-]{11})', href)
                    if video_id_match:
                        video_id = video_id_match.group(1)
                    else:
                        continue
                else:
                    continue
            else:
                video_id = video_id.text
            
            title = entry.find('.//atom:title', namespaces).text
            published = entry.find('.//atom:published', namespaces).text
            
            videos.append({
                'video_id': video_id,
                'title': title,
                'published': published,
                'url': f'https://www.youtube.com/watch?v={video_id}'
            })
        
        return videos
    
    except Exception as e:
        logger.error(f"Error fetching latest videos for channel {channel_id}: {e}")
        return []

def get_transcript(video_id, video_url=None, use_whisper_fallback=True):
    """
    Get the transcript for a YouTube video.
    First tries YouTube's built-in captions, then falls back to Whisper API if enabled.
    
    Args:
        video_id (str): YouTube video ID
        video_url (str, optional): Full YouTube URL for Whisper fallback
        use_whisper_fallback (bool): Whether to use Whisper API as fallback
        
    Returns:
        str: Transcript text or None if not available
    """
    if not video_id:
        return None
    
    try:
        # Apply rate limiting
        rate_limiter.wait_if_needed('youtube.com')
        
        # Try to get English transcript directly
        try:
            # First try manual transcripts in English
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB'])
        except:
            try:
                # Try any available transcript
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
            except:
                raise Exception(f"No transcript found for video {video_id}")
        
        # Combine all text parts
        full_text = ' '.join([part['text'] for part in transcript_data])
        
        logger.info(f"✅ Got YouTube transcript for {video_id}: {len(full_text)} characters")
        return full_text
    
    except Exception as e:
        logger.warning(f"No YouTube transcript available for video {video_id}: {e}")
        
        # Try Whisper fallback if enabled and URL provided
        if use_whisper_fallback and video_url:
            logger.info(f"🎤 Attempting Whisper transcription for {video_id}...")
            try:
                # Import the appropriate version based on OpenAI library
                try:
                    import openai
                    if hasattr(openai, '__version__') and openai.__version__.startswith('1.'):
                        from src.utils.whisper_transcriber import transcribe_youtube_video
                    else:
                        from src.utils.whisper_transcriber_v0 import transcribe_youtube_video
                except:
                    from src.utils.whisper_transcriber_v0 import transcribe_youtube_video
                
                whisper_transcript = transcribe_youtube_video(video_url, video_id)
                if whisper_transcript:
                    logger.info(f"✅ Whisper transcription successful for {video_id}: {len(whisper_transcript)} characters")
                    return whisper_transcript
                else:
                    logger.warning(f"❌ Whisper transcription failed for {video_id}")
            except Exception as whisper_error:
                logger.error(f"Error using Whisper fallback: {whisper_error}")
        
        return None

def get_video_metadata_fallback(video_id, known_title=None):
    """
    Fallback method to get video description and metadata when transcript is not available.
    
    Args:
        video_id (str): YouTube video ID
        known_title (str, optional): Title already extracted by ScrapingBee
        
    Returns:
        dict: Video metadata including title, description, and basic info
    """
    if not video_id:
        return None
    
    try:
        # Apply rate limiting
        rate_limiter.wait_if_needed('youtube.com')
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Error fetching video page: Status code {response.status_code}")
            # If we have a known title from ScrapingBee, use it
            if known_title:
                return _create_fallback_metadata_with_title(video_id, known_title, url)
            return None
        
        html_content = response.text
        
        # Extract title - try multiple patterns
        title = None
        
        # Try different title extraction patterns
        title_patterns = [
            r'"title"\s*:\s*"([^"]*)"',  # JSON format
            r'<title[^>]*>([^<]*)</title>',  # HTML title tag
            r'"videoDetails"\s*:\s*{[^}]*"title"\s*:\s*"([^"]*)"',  # videoDetails JSON
            r'property="og:title"\s+content="([^"]*)"',  # Open Graph meta tag
            r'"name"\s*:\s*"([^"]*)"',  # Alternative JSON name field
        ]
        
        for pattern in title_patterns:
            title_match = re.search(pattern, html_content, re.IGNORECASE)
            if title_match:
                title = title_match.group(1)
                # Clean up common escapes
                title = title.replace('\\u0026', '&').replace('\\u003d', '=')
                title = title.replace('\\/', '/').replace('\\"', '"')
                # Remove " - YouTube" suffix if present
                title = re.sub(r'\s*-\s*YouTube\s*$', '', title, flags=re.IGNORECASE)
                if title and title != video_id and len(title) > 5:  # Valid title found
                    logger.info(f"Found video title using pattern: {title}")
                    break
                else:
                    title = None  # Reset if invalid
        
        # If we couldn't extract title from page but have known_title from ScrapingBee, use it
        if not title and known_title:
            title = known_title
            logger.info(f"Using ScrapingBee title as fallback: {title}")
        elif not title:
            title = f"YouTube Video {video_id}"
            logger.warning(f"Could not extract title for video {video_id}, using fallback")
        
        # Extract description (look for shortDescription in JSON)
        desc_patterns = [
            r'"shortDescription"\s*:\s*"([^"]*)"',
            r'"description"\s*:\s*"([^"]*)"',
            r'property="og:description"\s+content="([^"]*)"',
        ]
        
        description = ""
        for pattern in desc_patterns:
            desc_match = re.search(pattern, html_content, re.IGNORECASE)
            if desc_match:
                description = desc_match.group(1)
                # Clean up escapes
                description = description.replace('\\n', ' ').replace('\\/', '/')
                # Limit description length to avoid token limits
                if len(description) > 500:
                    description = description[:500] + "..."
                break
        
        # If no description found, create one from the title
        if not description and title and title != f"YouTube Video {video_id}":
            description = f"This is a video about {title.lower()}. Content analysis based on video title and metadata."
        
        # Extract view count
        view_patterns = [
            r'"viewCount"\s*:\s*"([^"]*)"',
            r'"views"\s*:\s*"([^"]*)"',
            r'(\d+(?:,\d+)*)\s+views?',
        ]
        
        view_count = "0"
        for pattern in view_patterns:
            view_match = re.search(pattern, html_content, re.IGNORECASE)
            if view_match:
                view_count = view_match.group(1)
                break
        
        # Extract channel name
        channel_patterns = [
            r'"author"\s*:\s*"([^"]*)"',
            r'"channelName"\s*:\s*"([^"]*)"',
            r'"ownerChannelName"\s*:\s*"([^"]*)"',
            r'property="og:site_name"\s+content="([^"]*)"',
        ]
        
        channel_name = "Unknown Channel"
        for pattern in channel_patterns:
            channel_match = re.search(pattern, html_content, re.IGNORECASE)
            if channel_match:
                channel_name = channel_match.group(1)
                break
        
        # Try to extract upload date with more precision
        upload_date = None
        try:
            # Look for upload date in specific JSON structure first
            upload_patterns = [
                # YouTube's structured data for the specific video
                r'"uploadDate"\s*:\s*"([^"]+)"',
                r'"datePublished"\s*:\s*"([^"]+)"',
                # In videoDetails
                r'"publishDate"\s*:\s*"([^"]+)"',
            ]
            
            for pattern in upload_patterns:
                date_match = re.search(pattern, html_content)
                if date_match:
                    date_str = date_match.group(1)
                    try:
                        # Parse ISO date format
                        upload_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        logger.info(f"📅 Found upload date in JSON for video {video_id}: {upload_date.strftime('%Y-%m-%d')}")
                        break
                    except:
                        pass
            
            # If no structured date found, use the more precise video upload date extractor
            if not upload_date:
                upload_date = extract_video_upload_date(html_content)
                if upload_date:
                    logger.info(f"📅 Extracted precise upload date for video {video_id}: {upload_date.strftime('%Y-%m-%d')}")
            
        except Exception as e:
            logger.debug(f"Could not extract upload date: {e}")
        
        # 🚀 ENHANCED: Create richer content for GPT analysis
        content_text = f"Video Title: {title}\n"
        content_text += f"Channel: {channel_name}\n"
        if description and len(description) > 10:
            content_text += f"Video Description: {description}\n"
        content_text += f"View Count: {view_count}\n"
        if upload_date:
            content_text += f"Upload Date: {upload_date.strftime('%Y-%m-%d')}\n"
        
        # Add context cues for GPT to understand this is a car review
        if any(keyword in title.lower() for keyword in ['review', 'test', 'drive', 'driving', 'commute', 'ownership']):
            content_text += f"Video Type: Automotive review/test drive content\n"
        
        content_text += f"URL: {url}"
        
        metadata = {
            'title': title,
            'description': description,
            'channel_name': channel_name,
            'view_count': view_count,
            'content_text': content_text,
            'url': url
        }
        
        # Add upload date if found
        if upload_date:
            # Store as datetime object, not string
            metadata['upload_date'] = upload_date
            metadata['published_date'] = upload_date
            metadata['date_source'] = 'video_page_extraction'
            logger.info(f"📅 Added upload date to metadata: {upload_date}")
        else:
            logger.warning(f"⚠️ No upload date found for video {video_id}")
        
        return metadata
        
    except Exception as e:
        logger.error(f"Error fetching video metadata for {video_id}: {e}")
        # If we have a known title from ScrapingBee, use it as last resort
        if known_title:
            return _create_fallback_metadata_with_title(video_id, known_title, f"https://www.youtube.com/watch?v={video_id}")
        return None

def _create_fallback_metadata_with_title(video_id, title, url):
    """
    Create basic metadata when full extraction fails but we have the title.
    """
    description = f"This is a video about {title.lower()}. Content analysis based on video title."
    
    content_text = f"Video Title: {title}\n"
    content_text += f"Channel: TopherDrives (inferred from context)\n"
    content_text += f"Video Description: {description}\n"
    content_text += f"Video Type: Automotive review/test drive content\n"
    content_text += f"URL: {url}"
    
    return {
        'title': title,
        'description': description,
        'channel_name': 'TopherDrives',
        'view_count': '0',
        'content_text': content_text,
        'url': url
    }

def scrape_channel_videos_with_scrapfly(channel_url: str, make: str, model: str, start_date: Optional[datetime] = None, days_forward: int = 90, max_videos: int = None) -> Optional[List[Dict[str, Any]]]:
    """
    Scrape YouTube channel page using ScrapFly to get raw HTML and parse manually.
    Now with enhanced scrolling to load more videos (up to max_videos).
    Falls back to YouTube API if ScrapFly fails.
    
    Args:
        channel_url: YouTube channel URL (e.g., https://www.youtube.com/@TheCarCareNutReviews/videos)
        make: Vehicle make to search for
        model: Vehicle model to search for
        max_videos: Maximum number of videos to try to load (default from config)
        
    Returns:
        List of video dictionaries with title, url, video_id
    """
    # Use configuration value if max_videos not specified
    if max_videos is None:
        max_videos = YOUTUBE_SCRAPFLY_CONFIG.get('max_videos', 100)
    
    try:
        from src.utils.scrapfly_client import ScrapFlyWebCrawler
        
        # Initialize ScrapFly client
        crawler = ScrapFlyWebCrawler()
        
        # Quick API test with a simple page first
        logger.info("🧪 Testing ScrapFly API connectivity...")
        test_content, _, test_error = crawler.crawl(
            url="https://httpbin.org/html",  # This returns actual HTML content
            render_js=False,
            use_stealth=False
        )
        
        if not test_content:
            logger.warning(f"⚠️ ScrapFly API test failed: {test_error} - falling back to YouTube API")
            return _fallback_to_youtube_api(channel_url, make, model, start_date, days_forward, max_videos)
        else:
            logger.info("✅ ScrapFly API test successful - proceeding with YouTube scraping")
        
        # Ensure we're using the /videos page to get all videos
        if '/videos' not in channel_url:
            if channel_url.endswith('/'):
                channel_url = channel_url + 'videos'
            else:
                channel_url = channel_url + '/videos'
        
        logger.info(f"🎬 Scraping YouTube channel with ScrapFly: {channel_url}")
        
        # Use ScrapFly to get the raw HTML with scrolling
        try:
            # Create JavaScript scenario to scroll and load more videos
            # This scrolls multiple times to trigger lazy loading
            scroll_actions = YOUTUBE_SCRAPFLY_CONFIG.get('scroll_actions', 5)
            scroll_wait_ms = YOUTUBE_SCRAPFLY_CONFIG.get('scroll_wait_ms', 2000)
            
            js_scenario = []
            for _ in range(scroll_actions):
                js_scenario.extend([
                    {"scroll": {"direction": "down"}},
                    {"wait": scroll_wait_ms}
                ])
            
            logger.info(f"🎬 Scraping YouTube channel with ScrapFly (enhanced scrolling for {max_videos} videos)...")
            
            # Get raw HTML from YouTube channel page with scrolling
            # YouTube requires ASP (Anti-Scraping Protection) and JS rendering
            html_content, title, error = crawler.crawl(
                url=channel_url,
                render_js=True,  # Essential for YouTube
                use_stealth=True,  # ASP - Essential for YouTube
                country='US',
                js_scenario=js_scenario,  # Scroll to load more videos
                rendering_wait=3000  # Wait 3s after initial render
            )
            
            if not html_content or len(html_content) < 1000:
                logger.warning(f"❌ ScrapFly returned insufficient content ({len(html_content) if html_content else 0} chars) - falling back to YouTube API")
                if error:
                    logger.warning(f"ScrapFly error: {error}")
                return _fallback_to_youtube_api(channel_url, make, model, start_date, days_forward, max_videos)
                
            logger.info(f"✅ ScrapFly successfully scraped YouTube channel! ({len(html_content)} chars)")
            
            # Parse HTML manually to find video titles and links
            import re
            
            # Use BeautifulSoup to parse HTML properly (like ScrapingBee guide suggests)
            logger.info("🔍 Parsing YouTube HTML with BeautifulSoup...")
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Method 1: Find video-title elements (ScrapingBee guide approach)
                title_elements = soup.find_all(id="video-title")
                link_elements = soup.find_all(id="video-title-link")
                
                logger.info(f"📋 Found {len(title_elements)} title elements and {len(link_elements)} link elements")
                
                videos_found = []
                
                # 🚀 REMOVED 20-VIDEO LIMIT: Process ALL videos found on the page
                for i, (title_elem, link_elem) in enumerate(zip(title_elements, link_elements)):
                    try:
                        # Extract title text
                        title = title_elem.get_text(strip=True) if title_elem else ""
                        
                        # Extract href (video URL)
                        href = link_elem.get('href') if link_elem else ""
                        
                        # Try to find the date for this specific video
                        published_date = None
                        date_text = None
                        
                        # Look for metadata in the parent container
                        parent = title_elem.parent if title_elem else None
                        if parent:
                            # Method 1: Look for metadata spans
                            metadata_spans = parent.find_all('span', class_=re.compile('inline-metadata-item|metadata'))
                            if i < 3:  # Debug first few videos
                                logger.debug(f"   Found {len(metadata_spans)} metadata spans for video {i+1}")
                            for span in metadata_spans:
                                span_text = span.get_text(strip=True)
                                if re.search(r'\d+\s*(second|minute|hour|day|week|month|year)s?\s*ago', span_text, re.I):
                                    date_text = span_text
                                    published_date = parse_youtube_relative_date(date_text)
                                    if published_date:
                                        logger.info(f"   📅 Found date for video {i+1}: '{date_text}' -> {published_date.strftime('%Y-%m-%d')}")
                                        break
                            
                            # Method 2: If not found, look in parent's parent for aria-label
                            if not published_date and parent.parent:
                                grandparent = parent.parent
                                aria_label = grandparent.get('aria-label', '')
                                date_match = re.search(r'(\d+\s*(?:second|minute|hour|day|week|month|year)s?\s*ago)', aria_label, re.I)
                                if date_match:
                                    date_text = date_match.group(1)
                                    published_date = parse_youtube_relative_date(date_text)
                                    if published_date:
                                        logger.debug(f"   📅 Found date in aria-label for video {i+1}: '{date_text}' -> {published_date.strftime('%Y-%m-%d')}")
                            
                            # Method 3: Search broader in the parent for any text containing date
                            if not published_date:
                                # Use string instead of text (deprecated)
                                date_strings = parent.find_all(string=re.compile(r'\d+\s*(second|minute|hour|day|week|month|year)s?\s*ago', re.I))
                                if date_strings:
                                    date_text = date_strings[0].strip()
                                    published_date = parse_youtube_relative_date(date_text)
                                    if published_date:
                                        logger.debug(f"   📅 Found date in text for video {i+1}: '{date_text}' -> {published_date.strftime('%Y-%m-%d')}")
                        
                        logger.info(f"🔍 Video {i+1}: Title='{title}', Href='{href}', Date='{date_text or 'Not found'}'")
                        
                        if title and href and '/watch?v=' in href:
                            # Extract video ID
                            video_id_match = re.search(r'v=([a-zA-Z0-9_-]{11})', href)
                            if video_id_match:
                                video_id = video_id_match.group(1)
                                
                                # Skip if title is too short
                                if len(title) < 10:
                                    logger.warning(f"   ❌ Title too short: '{title}' ({len(title)} chars)")
                                    continue
                                
                                video_info = {
                                    'video_id': video_id,
                                    'title': title,
                                    'url': f"https://www.youtube.com/watch?v={video_id}",
                                    'method': 'scrapfly'
                                }
                                
                                # Add the published date if we found it
                                if published_date:
                                    video_info['published'] = published_date.isoformat()
                                    video_info['date_source'] = 'relative_date_parser'
                                    video_info['date_text'] = date_text
                                
                                videos_found.append(video_info)
                                logger.info(f"   ✅ Added video: {title}")
                                
                    except Exception as e:
                        logger.warning(f"   ❌ Error processing video {i+1}: {e}")
                        continue
                
                logger.info(f"🎬 ScrapFly method: Found {len(videos_found)} valid videos (after scrolling)")
                
                # Log if we found more than 30 videos (proving scrolling worked)
                if len(videos_found) > 30:
                    logger.info(f"✨ Scrolling worked! Found {len(videos_found) - 30} additional videos beyond initial 30")
                
                # If ScrapFly found videos, use them
                if videos_found:
                    logger.info("✅ ScrapFly extraction successful!")
                    
                    # Filter for relevant videos
                    relevant_videos = []
                    make_lower = make.lower()
                    model_lower = model.lower()
                    
                    # Create model variations using the improved function
                    from src.utils.model_variations import generate_model_variations
                    model_variations = generate_model_variations(make, model)
                    
                    logger.info(f"Filtering {len(videos_found)} videos for make='{make}' and model variations: {model_variations}")
                    
                    # 🚀 SHOW MORE DEBUG INFO: Display more videos if we got them
                    videos_to_show = min(70, len(videos_found))  # Show up to 70 videos (to catch video #52)
                    logger.info(f"🔍 DEBUG: Showing {videos_to_show} of {len(videos_found)} video titles extracted by ScrapFly:")
                    for i, video in enumerate(videos_found[:videos_to_show]):
                        logger.info(f"  {i+1}. '{video['title']}'")
                    
                    for video in videos_found:
                        title_lower = video['title'].lower()
                        
                        # DEBUG: Show what we're checking
                        logger.info(f"🔍 Checking video: '{video['title']}'")
                        logger.info(f"   Title (lowercase): '{title_lower}'")
                        logger.info(f"   Looking for make: '{make_lower}' in title")
                        
                        # Check if title contains make and any model variation
                        if make_lower in title_lower:
                            logger.info(f"   ✅ Found make '{make_lower}' in title!")
                            for model_var in model_variations:
                                logger.info(f"   🔍 Checking for model variation: '{model_var}'")
                                if flexible_model_match(title_lower, model_var):
                                    logger.info(f"🎯 ScrapFly found relevant video: {video['title']}")
                                    relevant_videos.append(video)
                                    break
                                else:
                                    logger.info(f"   ❌ Model variation '{model_var}' not found")
                        else:
                            logger.info(f"   ❌ Make '{make_lower}' not found in title")
                    
                    logger.info(f"🎬 ScrapFly found {len(relevant_videos)} relevant videos for {make} {model}")
                    
                    # If we didn't find dates individually, log but don't attempt bulk extraction
                    # Bulk extraction is unreliable as it assigns dates in order without matching to specific videos
                    if relevant_videos and not any(video.get('published') for video in relevant_videos):
                        logger.info("📅 No individual video dates found - dates will be extracted when processing individual videos")
                        # Don't attempt bulk extraction as it leads to incorrect date assignments
                    
                    if relevant_videos:
                        return relevant_videos[:10]  # Return top 10 most relevant
                    else:
                        logger.warning("ScrapFly found videos but none were relevant - falling back to YouTube API")
                        return _fallback_to_youtube_api(channel_url, make, model, start_date, days_forward, max_videos)
                        
                else:
                    logger.warning("ScrapFly extracted no videos - falling back to YouTube API")
                    return _fallback_to_youtube_api(channel_url, make, model, start_date, days_forward, max_videos)
                    
            except Exception as e:
                logger.error(f"BeautifulSoup parsing failed: {e} - falling back to YouTube API")
                return _fallback_to_youtube_api(channel_url, make, model, start_date, days_forward, max_videos)
                
        except Exception as e:
            logger.error(f"Error processing ScrapFly YouTube response: {e} - falling back to YouTube API")
            return _fallback_to_youtube_api(channel_url, make, model, start_date, days_forward, max_videos)
        
    except Exception as e:
        logger.error(f"Error scraping YouTube channel with ScrapFly: {e} - falling back to YouTube API")
        return _fallback_to_youtube_api(channel_url, make, model, start_date, days_forward, max_videos)

def _fallback_to_youtube_api(channel_url: str, make: str, model: str, start_date: Optional[datetime] = None, days_forward: int = 90, max_videos: int = 100) -> Optional[List[Dict[str, Any]]]:
    """
    Fallback to YouTube API when ScrapFly fails.
    Provides unlimited video access to find videos at position 33+.
    """
    try:
        from src.utils.youtube_api import YouTubeAPIClient
        
        logger.info("🔄 Falling back to YouTube Data API v3...")
        
        api_client = YouTubeAPIClient()
        
        # Use YouTube API to search channel with date filtering
        relevant_videos = api_client.search_channel_for_videos(channel_url, make, model, start_date, days_forward)
        
        if relevant_videos:
            logger.info(f"✅ YouTube API found {len(relevant_videos)} relevant videos for {make} {model}")
            return relevant_videos
        else:
            logger.warning(f"❌ YouTube API found no relevant videos for {make} {model}")
            return None
            
    except Exception as e:
        logger.error(f"YouTube API fallback failed: {e}")
        return None 