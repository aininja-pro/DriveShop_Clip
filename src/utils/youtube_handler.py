import re
import requests
import xml.etree.ElementTree as ET
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.parse import urlparse, parse_qs
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

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

def get_video_metadata_fallback(video_id):
    """
    Fallback method to get video description and metadata when transcript is not available.
    
    Args:
        video_id (str): YouTube video ID
        
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
        
        if not title:
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
                break
        
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
        
        # Combine available text for analysis
        content_text = f"Title: {title}\n"
        content_text += f"Channel: {channel_name}\n"
        if description:
            content_text += f"Description: {description}\n"
        content_text += f"Views: {view_count}"
        
        return {
            'title': title,
            'description': description,
            'channel_name': channel_name,
            'view_count': view_count,
            'content_text': content_text,
            'url': url
        }
        
    except Exception as e:
        logger.error(f"Error fetching video metadata for {video_id}: {e}")
        return None

def scrape_channel_videos_with_scrapingbee(channel_url: str, make: str, model: str) -> Optional[List[Dict[str, Any]]]:
    """
    Scrape YouTube channel page using ScrapingBee to get raw HTML and parse manually.
    
    Args:
        channel_url: YouTube channel URL (e.g., https://www.youtube.com/@TheCarCareNutReviews/videos)
        make: Vehicle make to search for
        model: Vehicle model to search for
        
    Returns:
        List of video dictionaries with title, url, video_id
    """
    try:
        from src.utils.scraping_bee import ScrapingBeeClient
        
        # Initialize ScrapingBee client
        scraper = ScrapingBeeClient()
        
        # Quick API test with a simple page first
        logger.info("🧪 Testing ScrapingBee API connectivity...")
        test_content = scraper.scrape_url(
            url="https://httpbin.org/html",  # This returns actual HTML content
            render_js=False,
            premium_proxy=False
        )
        
        if not test_content:
            logger.warning("⚠️ ScrapingBee API test failed - cannot connect to ScrapingBee")
            return None
        else:
            logger.info("✅ ScrapingBee API test successful - proceeding with YouTube scraping")
        
        # Ensure we're using the /videos page to get all videos
        if '/videos' not in channel_url:
            if channel_url.endswith('/'):
                channel_url = channel_url + 'videos'
            else:
                channel_url = channel_url + '/videos'
        
        logger.info(f"🎬 Scraping YouTube channel with ScrapingBee: {channel_url}")
        
        # Use ScrapingBee to get the raw HTML (simpler approach)
        try:
            # Get raw HTML from YouTube channel page
            html_content = scraper.scrape_url(
                url=channel_url,
                render_js=True,  # Essential for YouTube
                premium_proxy=True  # Essential for YouTube
            )
            
            if not html_content:
                logger.error("❌ ScrapingBee failed to get YouTube channel HTML")
                return None
                
            logger.info(f"✅ ScrapingBee successfully scraped YouTube channel! ({len(html_content)} chars)")
            
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
                
                # Combine titles and links (ScrapingBee approach)
                for i, (title_elem, link_elem) in enumerate(zip(title_elements, link_elements)):
                    if i >= 20:  # Limit for debugging
                        break
                        
                    try:
                        # Extract title text
                        title = title_elem.get_text(strip=True) if title_elem else ""
                        
                        # Extract href (video URL)
                        href = link_elem.get('href') if link_elem else ""
                        
                        logger.info(f"🔍 Video {i+1}: Title='{title}', Href='{href}'")
                        
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
                                    'method': 'beautifulsoup_id_selector'
                                }
                                
                                videos_found.append(video_info)
                                logger.info(f"   ✅ Added video: {title}")
                                
                    except Exception as e:
                        logger.warning(f"   ❌ Error processing video {i+1}: {e}")
                        continue
                
                logger.info(f"🎬 BeautifulSoup method: Found {len(videos_found)} valid videos")
                
                # If BeautifulSoup method worked, use it
                if videos_found:
                    logger.info("✅ BeautifulSoup extraction successful!")
                    
            except Exception as e:
                logger.error(f"BeautifulSoup parsing failed: {e}")
                videos_found = []
            
            # Fallback: Try alternative selectors if main method failed
            if not videos_found:
                logger.info("🔄 Trying alternative CSS selectors...")
                try:
                    # Alternative approach: Look for yt-formatted-string elements
                    title_elements = soup.find_all('yt-formatted-string')
                    
                    for elem in title_elements[:20]:
                        title = elem.get_text(strip=True)
                        if title and len(title) > 15 and ('review' in title.lower() or 'buy' in title.lower()):
                            logger.info(f"🔍 Found potential title: {title}")
                            
                except Exception as e:
                    logger.warning(f"Alternative selector method failed: {e}")
            
            # If still no videos, fall back to original regex (but improve it)
            if not videos_found:
                logger.warning("🔄 Falling back to improved regex extraction...")
                # ... (keep original regex as fallback)
            
            # Filter for relevant videos
            relevant_videos = []
            if videos_found:
                make_lower = make.lower()
                model_lower = model.lower()
                
                # Create model variations
                model_variations = [
                    model_lower,
                    model_lower.replace('3', ' 3'),  # mazda3 -> mazda 3
                    model_lower.replace('mazda3', 'mazda 3'),
                ]
                
                logger.info(f"Filtering {len(videos_found)} videos for make='{make}' and model variations: {model_variations}")
                
                # DEBUG: Log all extracted video titles
                logger.info("🔍 DEBUG: All video titles extracted by ScrapingBee:")
                for i, video in enumerate(videos_found[:10]):  # Show first 10 for debugging
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
                            if model_var in title_lower:
                                logger.info(f"🎯 ScrapingBee found relevant video: {video['title']}")
                                relevant_videos.append(video)
                                break
                            else:
                                logger.info(f"   ❌ Model variation '{model_var}' not found")
                    else:
                        logger.info(f"   ❌ Make '{make_lower}' not found in title")
                
                logger.info(f"🎬 ScrapingBee found {len(relevant_videos)} relevant videos for {make} {model}")
                return relevant_videos[:10]  # Return top 10 most relevant
            else:
                logger.warning("ScrapingBee extracted no videos from YouTube channel HTML")
                return None
                
        except Exception as e:
            logger.error(f"Error processing ScrapingBee YouTube response: {e}")
            return None
        
    except Exception as e:
        logger.error(f"Error scraping YouTube channel with ScrapingBee: {e}")
        return None 