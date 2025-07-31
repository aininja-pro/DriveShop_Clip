import os
import time
import json
import re
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
import tempfile

from src.utils.logger import setup_logger
from src.utils.rate_limiter import rate_limiter
from src.utils.model_matching import fuzzy_model_match, get_make_synonyms

logger = setup_logger(__name__)

# Common automotive hashtags on TikTok
AUTOMOTIVE_TAGS = [
    # General automotive
    'car', 'cars', 'auto', 'automotive', 'vehicle', 'carreview', 'carreviews',
    'newcar', 'newcars', 'carshow', 'autoshow', 'testdrive', 'cartest',
    
    # Specific categories
    'suv', 'truck', 'sedan', 'coupe', 'hatchback', 'minivan', 'crossover',
    'electriccar', 'ev', 'hybrid', 'phev', 
    
    # Enthusiast tags
    'carsoftiktok', 'cartok', 'carspotting', 'carcommunity', 'carlifestyle',
    'dailydriven', 'dreamcar', 'cargoals', 'instacar', 'cargram',
    
    # Review/opinion tags  
    'caradvice', 'whatcar', 'shouldibuy', 'carbuying', 'carbuyingguide',
    'honestreview', 'carproblems', 'prosandcons',
    
    # Model year tags
    '2024car', '2024cars', '2025car', '2025cars', 'newmodel',
    
    # Brand-specific (add more as needed)
    'toyota', 'honda', 'ford', 'chevy', 'mazda', 'hyundai', 'kia', 
    'bmw', 'mercedes', 'audi', 'volkswagen', 'nissan', 'subaru'
]

class TikTokRateLimiter:
    """
    Specialized rate limiter for TikTok with exponential backoff.
    More aggressive than general rate limiter due to TikTok's strict policies.
    """
    
    def __init__(self):
        self.last_request = 0
        self.backoff_multiplier = 1
        self.base_delay = 5  # Base 5 seconds between requests
        self.max_multiplier = 8  # Max 40 second delays
        
    def wait(self):
        """Apply rate limiting with exponential backoff"""
        current_time = time.time()
        time_since_last = current_time - self.last_request
        
        # Calculate required delay
        required_delay = self.base_delay * self.backoff_multiplier
        
        if time_since_last < required_delay:
            sleep_time = required_delay - time_since_last
            logger.info(f"TikTok rate limit: sleeping {sleep_time:.1f}s (multiplier: {self.backoff_multiplier}x)")
            time.sleep(sleep_time)
            
        self.last_request = time.time()
        
    def increase_backoff(self):
        """Increase backoff multiplier on errors"""
        if self.backoff_multiplier < self.max_multiplier:
            self.backoff_multiplier *= 2
            logger.warning(f"Increased TikTok backoff to {self.backoff_multiplier}x")
            
    def reset_backoff(self):
        """Reset backoff on successful request"""
        if self.backoff_multiplier > 1:
            self.backoff_multiplier = 1
            logger.info("Reset TikTok backoff to normal")

# Global rate limiter instance
tiktok_limiter = TikTokRateLimiter()

def extract_video_id_from_url(url: str) -> Optional[str]:
    """
    Extract TikTok video ID from various URL formats.
    
    Handles:
    - https://www.tiktok.com/@username/video/1234567890
    - https://vm.tiktok.com/XXXXXXXX/
    - https://tiktok.com/t/XXXXXXXX/
    """
    patterns = [
        r'tiktok\.com/@[\w.-]+/video/(\d+)',  # Standard format
        r'vm\.tiktok\.com/(\w+)',  # Short link
        r'tiktok\.com/t/(\w+)',  # New short format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_automotive_content(video_data: Dict[str, Any]) -> bool:
    """
    Check if TikTok content is automotive-related.
    
    Args:
        video_data: Metadata from yt-dlp
        
    Returns:
        True if content appears automotive-related
    """
    # Check description
    description = video_data.get('description', '').lower()
    title = video_data.get('title', '').lower()
    
    # Check hashtags if available
    hashtags = []
    # Extract hashtags from description
    hashtags_in_desc = re.findall(r'#(\w+)', description)
    hashtags.extend([tag.lower() for tag in hashtags_in_desc])
    
    # Check for automotive keywords
    text_to_check = f"{title} {description} {' '.join(hashtags)}"
    
    # Must have at least one automotive tag
    for tag in AUTOMOTIVE_TAGS:
        if tag in text_to_check:
            return True
            
    # Also check for make/model mentions in description
    # This catches reviews without hashtags
    automotive_brands = ['toyota', 'honda', 'ford', 'mazda', 'hyundai', 'kia', 
                        'nissan', 'subaru', 'bmw', 'mercedes', 'audi']
    for brand in automotive_brands:
        if brand in text_to_check:
            return True
            
    return False

def should_use_whisper(video_data: Dict[str, Any]) -> bool:
    """
    Determine if we should use Whisper for transcription.
    For DriveShop, we ALWAYS want transcription for sentiment analysis.
    
    Args:
        video_data: Video metadata
        
    Returns:
        True if Whisper should be used
    """
    # Must be automotive content
    if not is_automotive_content(video_data):
        logger.info("Skipping Whisper - not automotive content")
        return False
        
    # Check video duration (skip very long videos for cost control)
    duration = video_data.get('duration', 0)
    if duration > 300:  # 5 minutes = $0.03
        logger.warning(f"Video is {duration}s long (${(duration/60)*0.006:.3f} for transcription)")
        # Still transcribe but warn about cost
        
    # Always transcribe automotive content for sentiment analysis
    logger.info(f"Will transcribe: {duration}s video (${(duration/60)*0.006:.4f})")
    return True

async def extract_captions(video_id: str, ydl_opts: dict) -> Optional[str]:
    """
    Try to extract native TikTok captions.
    
    Args:
        video_id: TikTok video ID
        ydl_opts: yt-dlp options
        
    Returns:
        Caption text or None
    """
    try:
        # Update options for subtitle extraction
        caption_opts = ydl_opts.copy()
        caption_opts.update({
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'skip_download': True,
        })
        
        with yt_dlp.YoutubeDL(caption_opts) as ydl:
            info = ydl.extract_info(f"https://www.tiktok.com/@user/video/{video_id}", download=False)
            
            # Check for subtitles
            if info.get('subtitles'):
                # Get English subtitles
                en_subs = info['subtitles'].get('en', [])
                if en_subs and len(en_subs) > 0:
                    # Download the subtitle content
                    sub_url = en_subs[0]['url']
                    # This would need actual download logic
                    logger.info("Found native captions")
                    return None  # Placeholder - would need to download and parse
                    
            # Check for automatic captions
            if info.get('automatic_captions'):
                auto_en = info['automatic_captions'].get('en', [])
                if auto_en and len(auto_en) > 0:
                    logger.info("Found automatic captions")
                    return None  # Placeholder
                    
    except Exception as e:
        logger.debug(f"No captions available: {e}")
        
    return None

async def transcribe_with_whisper(video_url: str, ydl_opts: dict) -> Optional[str]:
    """
    Extract audio and transcribe with OpenAI Whisper API.
    
    Args:
        video_url: TikTok video URL
        ydl_opts: yt-dlp options
        
    Returns:
        Transcribed text or None
    """
    try:
        # Check for OpenAI API key
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            logger.error("OPENAI_API_KEY not found in environment")
            return None
            
        # Create temporary file for audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
            audio_file = tmp_file.name
            
        try:
            # Configure yt-dlp for audio extraction
            audio_opts = ydl_opts.copy()
            audio_opts.update({
                'format': 'bestaudio/best',
                'outtmpl': audio_file.replace('.mp3', '.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'quiet': True,
            })
            
            # Download audio
            logger.info("Extracting audio from TikTok video...")
            with yt_dlp.YoutubeDL(audio_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                duration = info.get('duration', 0)
                
                # Check duration to estimate cost
                cost_estimate = (duration / 60) * 0.006  # $0.006 per minute
                logger.info(f"Audio duration: {duration}s, estimated cost: ${cost_estimate:.4f}")
                
            # Use OpenAI Whisper API
            logger.info("Transcribing with OpenAI Whisper API...")
            
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            
            with open(audio_file, 'rb') as audio:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    response_format="text"
                )
            
            transcript = response.strip()
            logger.info(f"OpenAI Whisper transcription complete: {len(transcript)} characters")
            
            return transcript
            
        finally:
            # Clean up temporary file
            if os.path.exists(audio_file):
                os.remove(audio_file)
                
    except Exception as e:
        logger.error(f"OpenAI Whisper transcription failed: {e}")
        return None

def process_tiktok_video(url: str) -> Optional[Dict[str, Any]]:
    """
    Main function to process a TikTok video URL.
    Follows the same pattern as YouTube handler.
    
    Args:
        url: TikTok video URL
        
    Returns:
        Dictionary with video data or None if extraction fails
    """
    try:
        # Apply rate limiting
        tiktok_limiter.wait()
        
        logger.info(f"Processing TikTok URL: {url}")
        
        # Configure yt-dlp with better anti-detection
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'cookiefile': os.getenv('TIKTOK_COOKIES_FILE'),  # Optional: browser cookies
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extractor_args': {
                'tiktok': {
                    'api_hostname': 'api16-normal-c-useast1a.tiktokv.com'
                }
            },
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        }
        
        # Extract video metadata
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                tiktok_limiter.reset_backoff()  # Success - reset backoff
            except Exception as e:
                tiktok_limiter.increase_backoff()  # Error - increase backoff
                logger.error(f"yt-dlp extraction failed: {e}")
                return None
                
        # Extract relevant metadata
        video_data = {
            'url': url,
            'video_id': info.get('id', extract_video_id_from_url(url)),
            'title': info.get('title', ''),
            'description': info.get('description', ''),
            'creator': info.get('uploader', ''),
            'creator_handle': info.get('uploader_id', ''),
            'duration': info.get('duration', 0),
            'views': info.get('view_count', 0),
            'likes': info.get('like_count', 0),
            'comments': info.get('comment_count', 0),
            'shares': info.get('repost_count', 0),
            'published_date': None,
            'hashtags': [],
        }
        
        # Parse upload date
        timestamp = info.get('timestamp')
        if timestamp:
            video_data['published_date'] = datetime.fromtimestamp(timestamp)
        
        # Extract hashtags from description
        hashtags = re.findall(r'#(\w+)', video_data['description'])
        video_data['hashtags'] = hashtags
        
        # Log extraction success
        logger.info(f"Extracted TikTok metadata: @{video_data['creator_handle']} - {video_data['title'][:50]}...")
        logger.info(f"Stats: {video_data['views']} views, {video_data['likes']} likes")
        
        # Check if it's automotive content
        if not is_automotive_content(video_data):
            logger.info("Not automotive content - skipping transcript extraction")
            video_data['transcript'] = None
            return video_data
            
        # Try to get transcript/captions
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Step 1: Try native captions (60% success rate)
            logger.info("Attempting to extract native captions...")
            captions = loop.run_until_complete(extract_captions(video_data['video_id'], ydl_opts))
            
            if captions:
                logger.info("✅ Successfully extracted native captions")
                video_data['transcript'] = captions
                video_data['transcript_source'] = 'captions'
            else:
                # Step 2: Check if we should use Whisper
                if should_use_whisper(video_data):
                    logger.info("Native captions failed, trying Whisper transcription...")
                    transcript = loop.run_until_complete(transcribe_with_whisper(url, ydl_opts))
                    
                    if transcript:
                        logger.info("✅ Successfully transcribed with Whisper")
                        video_data['transcript'] = transcript
                        video_data['transcript_source'] = 'whisper'
                    else:
                        # Step 3: Fallback to description
                        logger.info("Falling back to description text")
                        video_data['transcript'] = video_data['description']
                        video_data['transcript_source'] = 'description'
                else:
                    # Low-value content - just use description
                    logger.info("Low engagement - using description only")
                    video_data['transcript'] = video_data['description']
                    video_data['transcript_source'] = 'description'
                    
        finally:
            loop.close()
            
        # Calculate engagement rate
        if video_data['views'] > 0:
            engagement = (video_data['likes'] + video_data['comments'] + video_data['shares']) / video_data['views']
            video_data['engagement_rate'] = round(engagement, 3)
        else:
            video_data['engagement_rate'] = 0
            
        return video_data
        
    except Exception as e:
        logger.error(f"Error processing TikTok URL {url}: {e}")
        tiktok_limiter.increase_backoff()
        return None

def get_channel_videos(channel_url: str, max_videos: int = 50) -> List[Dict[str, Any]]:
    """
    Get a list of videos from a TikTok channel using yt-dlp.
    This extracts metadata only, not full video content.
    
    Args:
        channel_url: TikTok channel URL (e.g., https://www.tiktok.com/@username)
        max_videos: Maximum number of videos to retrieve
        
    Returns:
        List of video metadata dictionaries
    """
    try:
        # Apply rate limiting
        tiktok_limiter.wait()
        
        logger.info(f"Scanning TikTok channel: {channel_url}")
        
        # Configure yt-dlp for channel scanning
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',  # Only extract metadata, not full videos
            'playlistend': max_videos,      # Limit number of videos
            'cookiefile': os.getenv('TIKTOK_COOKIES_FILE'),
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Extract channel info
                channel_info = ydl.extract_info(channel_url, download=False)
                
                if not channel_info:
                    logger.error(f"Could not extract channel info from: {channel_url}")
                    return []
                
                # Get video entries
                entries = channel_info.get('entries', [])
                logger.info(f"Found {len(entries)} videos in channel")
                
                videos = []
                for entry in entries[:max_videos]:
                    if entry:
                        video_data = {
                            'url': entry.get('url', f"https://www.tiktok.com/@{channel_info.get('uploader_id')}/video/{entry.get('id')}"),
                            'video_id': entry.get('id'),
                            'title': entry.get('title', ''),
                            'description': entry.get('description', ''),
                            'duration': entry.get('duration', 0),
                            'timestamp': entry.get('timestamp'),
                            'view_count': entry.get('view_count', 0),
                            'like_count': entry.get('like_count', 0),
                        }
                        
                        # Parse timestamp to datetime
                        if video_data['timestamp']:
                            video_data['published_date'] = datetime.fromtimestamp(video_data['timestamp'])
                        else:
                            video_data['published_date'] = None
                            
                        videos.append(video_data)
                
                tiktok_limiter.reset_backoff()
                return videos
                
            except Exception as e:
                tiktok_limiter.increase_backoff()
                logger.error(f"Error extracting channel videos: {e}")
                return []
                
    except Exception as e:
        logger.error(f"Error scanning TikTok channel {channel_url}: {e}")
        return []

def search_channel_for_vehicle(channel_url: str, make: str, model: str, start_date: Optional[datetime] = None, days_forward: int = 90) -> Optional[Dict[str, Any]]:
    """
    Search a TikTok channel for videos mentioning a specific vehicle.
    Pre-filters by title/description before expensive content extraction.
    
    Args:
        channel_url: TikTok channel URL
        make: Vehicle make (e.g., "Toyota")
        model: Vehicle model (e.g., "Crown Signia")
        start_date: Loan start date (videos must be after this)
        days_forward: Days forward from start date to search
        
    Returns:
        First matching video with full content, or None
    """
    try:
        logger.info(f"Searching {channel_url} for {make} {model}")
        
        # Get list of videos from channel
        channel_videos = get_channel_videos(channel_url, max_videos=50)
        
        if not channel_videos:
            logger.warning(f"No videos found in channel: {channel_url}")
            return None
            
        logger.info(f"Found {len(channel_videos)} videos to scan")
        
        # Pre-filter videos by make/model FIRST, date filtering later
        make_lower = make.lower()
        model_lower = model.lower()
        model_words = model_lower.split()  # Handle multi-word models
        
        relevant_videos = []
        
        for video in channel_videos:
            
            # Check title and description for make/model
            search_text = f"{video.get('title', '')} {video.get('description', '')}".lower()
            
            # Check for make using scalable synonym matching
            make_found = False
            make_synonyms = get_make_synonyms(make)
            for synonym in make_synonyms:
                if synonym in search_text:
                    make_found = True
                    break
            
            if not make_found:
                continue
                
            # Check for model using fuzzy matching (scalable for any model)
            model_found = fuzzy_model_match(search_text, model)
            
            if model_found:
                logger.info(f"✅ Found potential match: {video['title'][:80]}...")
                if video.get('published_date'):
                    logger.info(f"   Published: {video['published_date'].strftime('%Y-%m-%d')}")
                    # Check date AFTER finding match
                    if start_date and video['published_date'] < start_date:
                        logger.info(f"   ⏭️ Skipping - published before loan start date")
                        continue
                    if start_date and days_forward:
                        end_date = start_date + timedelta(days=days_forward)
                        if video['published_date'] > end_date:
                            logger.info(f"   ⏭️ Skipping - published after {days_forward} days window")
                            continue
                relevant_videos.append(video)
        
        if not relevant_videos:
            logger.info(f"No videos found mentioning {make} {model} in titles/descriptions")
            return None
            
        logger.info(f"Found {len(relevant_videos)} potential matches, processing most recent...")
        
        # Sort by date (newest first)
        relevant_videos.sort(key=lambda x: x.get('published_date') or datetime.min, reverse=True)
        
        # Process videos until we find one with good content
        for video in relevant_videos:
            logger.info(f"Processing: {video['title'][:80]}...")
            
            # Get full video content
            full_video_data = process_tiktok_video(video['url'])
            
            if full_video_data and full_video_data.get('transcript'):
                # Verify make/model in actual content
                transcript = full_video_data.get('transcript', '').lower()
                
                # Use smart content scoring that weighs hashtags higher than transcript
                from src.utils.tiktok_content_scorer import score_tiktok_relevance
                
                # Score the content based on all signals
                relevance_score = score_tiktok_relevance(full_video_data, make, model)
                
                logger.info(f"Content relevance score: {relevance_score['total_score']}/100")
                logger.info(f"  Hashtags: {relevance_score['hashtag_score']}/40")
                logger.info(f"  Title: {relevance_score['title_score']}/30")
                logger.info(f"  Transcript: {relevance_score['transcript_score']}/10")
                logger.info(f"Recommendation: {relevance_score['recommendation']}")
                
                # Accept if score is high enough
                if relevance_score['total_score'] >= 35:  # Lowered threshold since hashtags are reliable
                    logger.info(f"🎯 SUCCESS: Found {make} {model} content (score: {relevance_score['total_score']})")
                    # Add scoring data to response
                    full_video_data['relevance_score'] = relevance_score
                    return full_video_data
                else:
                    logger.info(f"Score too low ({relevance_score['total_score']}/100), trying next video...")
            else:
                logger.warning(f"Could not extract content from video, trying next...")
        
        logger.info(f"Processed all potential matches, none had {make} {model} in content")
        return None
        
    except Exception as e:
        logger.error(f"Error searching channel for vehicle: {e}")
        return None