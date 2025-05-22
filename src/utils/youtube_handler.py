import re
import requests
import xml.etree.ElementTree as ET
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.parse import urlparse, parse_qs

# Import local modules
from src.utils.logger import setup_logger
from src.utils.rate_limiter import rate_limiter

logger = setup_logger(__name__)

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
    
    logger.warning(f"Could not extract channel ID from URL: {url}")
    return None

def resolve_handle_to_channel_id(handle):
    """
    Resolve a YouTube handle (@username) to a channel ID.
    
    Args:
        handle (str): YouTube handle without @
        
    Returns:
        str: Channel ID or None if not found
    """
    try:
        # Apply rate limiting
        rate_limiter.wait_if_needed('youtube.com')
        
        url = f"https://www.youtube.com/@{handle}"
        response = requests.get(url)
        
        if response.status_code == 200:
            # Extract channel ID from HTML
            channel_id_match = re.search(r'"channelId":"([a-zA-Z0-9_-]+)"', response.text)
            if channel_id_match:
                return channel_id_match.group(1)
    except Exception as e:
        logger.error(f"Error resolving YouTube handle @{handle}: {e}")
    
    return None

def resolve_username_to_channel_id(username):
    """
    Resolve a YouTube username to a channel ID.
    
    Args:
        username (str): YouTube username
        
    Returns:
        str: Channel ID or None if not found
    """
    try:
        # Apply rate limiting
        rate_limiter.wait_if_needed('youtube.com')
        
        url = f"https://www.youtube.com/user/{username}"
        response = requests.get(url)
        
        if response.status_code == 200:
            # Extract channel ID from HTML
            channel_id_match = re.search(r'"channelId":"([a-zA-Z0-9_-]+)"', response.text)
            if channel_id_match:
                return channel_id_match.group(1)
    except Exception as e:
        logger.error(f"Error resolving YouTube username {username}: {e}")
    
    return None

def get_latest_videos(channel_id, max_videos=5):
    """
    Get the latest videos from a YouTube channel via RSS feed.
    
    Args:
        channel_id (str): YouTube channel ID
        max_videos (int): Maximum number of videos to return
        
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

def get_transcript(video_id):
    """
    Get the transcript for a YouTube video.
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        str: Transcript text or None if not available
    """
    if not video_id:
        return None
    
    try:
        # Apply rate limiting
        rate_limiter.wait_if_needed('youtube.com')
        
        # Get transcript
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to get English transcript first
        try:
            transcript = transcript_list.find_transcript(['en'])
        except NoTranscriptFound:
            # If no English transcript, get the first available
            transcript = transcript_list.find_transcript(['en-US', 'en-GB'])
        
        # Get the transcript data
        transcript_data = transcript.fetch()
        
        # Combine all text parts
        full_text = ' '.join([part['text'] for part in transcript_data])
        
        return full_text
    
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        logger.warning(f"No transcript available for video {video_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching transcript for video {video_id}: {e}")
        return None 