import os
import time
import json
import re
import asyncio
import tempfile
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from apify_client import ApifyClient

from src.utils.logger import setup_logger
from src.utils.model_matching import fuzzy_model_match, get_make_synonyms

logger = setup_logger(__name__)

# Common automotive hashtags on Instagram
AUTOMOTIVE_TAGS = [
    # General automotive
    'car', 'cars', 'auto', 'automotive', 'vehicle', 'carreview', 'carreviews',
    'newcar', 'newcars', 'carshow', 'autoshow', 'testdrive', 'cartest',
    
    # Specific categories
    'suv', 'truck', 'sedan', 'coupe', 'hatchback', 'minivan', 'crossover',
    'electriccar', 'ev', 'hybrid', 'phev', 'electricvehicle',
    
    # Enthusiast tags
    'carsofinstagram', 'instacar', 'cargram', 'carspotting', 'carcommunity', 
    'carlifestyle', 'dailydriven', 'dreamcar', 'cargoals', 'carinstagram',
    
    # Review/opinion tags  
    'caradvice', 'whatcar', 'shouldibuy', 'carbuying', 'carbuyingguide',
    'honestreview', 'carproblems', 'prosandcons', 'carreviewer',
    
    # Model year tags
    '2024car', '2024cars', '2025car', '2025cars', 'newmodel', 'newrelease',
    
    # Brand-specific (add more as needed)
    'toyota', 'honda', 'ford', 'chevy', 'mazda', 'hyundai', 'kia', 
    'bmw', 'mercedes', 'audi', 'volkswagen', 'nissan', 'subaru',
    'porsche', 'lotus', 'ferrari', 'lamborghini', 'mclaren'
]

class InstagramHandler:
    """
    Instagram Reels handler using Apify's instagram-scraper actor.
    Follows the same interface as TikTokHandler for consistency.
    """
    
    def __init__(self):
        self.api_token = os.getenv('APIFY_API_TOKEN')
        if not self.api_token:
            logger.warning("APIFY_API_TOKEN not found in environment variables")
            
        self.client = ApifyClient(self.api_token) if self.api_token else None
        self.actor_id = "xMc5Ga1oCONPmWJIa"  # Instagram Reel Scraper actor ID
        self._cache = {}  # Simple in-memory cache
        
    def extract_hashtags_from_caption(self, caption: str) -> List[str]:
        """Extract hashtags from Instagram caption"""
        if not caption:
            return []
        hashtags = re.findall(r'#(\w+)', caption)
        return [tag.lower() for tag in hashtags]
    
    def is_automotive_content(self, post_data: Dict[str, Any]) -> bool:
        """Check if Instagram content is automotive-related"""
        caption = post_data.get('caption', '').lower()
        hashtags = post_data.get('hashtags', [])
        
        # Combine text for checking
        text_to_check = f"{caption} {' '.join(hashtags)}"
        
        # Must have at least one automotive tag
        for tag in AUTOMOTIVE_TAGS:
            if tag in text_to_check:
                return True
                
        # Also check for make/model mentions
        automotive_brands = ['toyota', 'honda', 'ford', 'mazda', 'hyundai', 'kia', 
                            'nissan', 'subaru', 'bmw', 'mercedes', 'audi', 'porsche']
        for brand in automotive_brands:
            if brand in text_to_check:
                return True
                
        return False
    
    def should_use_whisper(self, post_data: Dict[str, Any]) -> bool:
        """Determine if we should use Whisper for transcription"""
        # Must be automotive content
        if not self.is_automotive_content(post_data):
            logger.info("Skipping Whisper - not automotive content")
            return False
            
        # Check if it's a video (Reel)
        if post_data.get('type') != 'Video':
            logger.info("Skipping Whisper - not a video")
            return False
            
        # Check video duration if available
        duration = post_data.get('videoDuration', 0)
        if duration > 300:  # 5 minutes
            logger.warning(f"Video is {duration}s long (${(duration/60)*0.006:.3f} for transcription)")
            
        # Always transcribe automotive video content
        logger.info(f"Will transcribe: {duration}s video (${(duration/60)*0.006:.4f})")
        return True
    
    async def download_and_transcribe_video(self, video_url: str) -> Optional[str]:
        """Download Instagram video and transcribe with Whisper API"""
        if not video_url:
            logger.warning("No video URL provided for transcription")
            return None
            
        try:
            # Check for OpenAI API key
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                logger.error("OPENAI_API_KEY not found in environment")
                return None
                
            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_video:
                video_file = tmp_video.name
                
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_audio:
                audio_file = tmp_audio.name
                
            try:
                # Download video
                logger.info("Downloading Instagram video...")
                response = requests.get(video_url, stream=True)
                response.raise_for_status()
                
                with open(video_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Extract audio using ffmpeg
                import subprocess
                logger.info("Extracting audio from video...")
                cmd = [
                    'ffmpeg', '-i', video_file,
                    '-vn', '-acodec', 'mp3',
                    '-ab', '128k', '-ar', '44100',
                    '-y', audio_file
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                
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
                logger.info(f"Transcription complete: {len(transcript)} characters")
                
                return transcript
                
            finally:
                # Clean up temporary files
                for file_path in [video_file, audio_file]:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        
        except Exception as e:
            logger.error(f"Video transcription failed: {e}")
            return None
    
    def extract_content(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract content from a single Instagram Reel URL using Apify"""
        if not self.client:
            logger.error("Apify client not initialized (missing API token)")
            return None
            
        # Check cache
        if url in self._cache:
            logger.info(f"Returning cached result for {url}")
            return self._cache[url]
            
        try:
            logger.info(f"Processing Instagram URL with Apify: {url}")
            
            # Configure the actor run for Instagram Reel Scraper
            # The actor accepts full URLs in the username field for direct URLs
            run_input = {
                "username": [url],  # Can be username or direct URL
                "resultsLimit": 1
            }
            
            # Start the actor and wait for it to finish
            logger.info("Starting Apify actor run...")
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            
            # Get results from the dataset
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            
            if not items:
                logger.warning(f"No data returned from Apify for URL: {url}")
                return None
                
            # Process the first (and only) item
            item = items[0]
            
            # Extract caption and hashtags
            caption = item.get('caption', '')
            hashtags = self.extract_hashtags_from_caption(caption)
            
            # Format the response to match TikTok handler
            post_data = {
                'url': url,
                'shortcode': item.get('shortCode', ''),
                'caption': caption,
                'title': caption[:100] if caption else '',  # First 100 chars as title
                'description': caption,  # Full caption as description
                'creator': item.get('ownerFullName', ''),
                'creator_handle': item.get('ownerUsername', ''),
                'type': item.get('type', 'Unknown'),
                'is_video': item.get('type') == 'Video',
                'duration': item.get('videoDuration', 0),
                'videoUrl': item.get('videoUrl'),
                'views': item.get('videoViewCount', 0),
                'plays': item.get('videoPlayCount', 0),
                'likes': item.get('likesCount', 0),
                'comments': item.get('commentsCount', 0),
                'published_date': datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00')) if item.get('timestamp') else None,
                'hashtags': hashtags,
                'platform': 'instagram',
                'engagement_rate': 0  # Calculate later
            }
            
            # Calculate engagement rate
            if post_data['views'] > 0:
                engagement = (post_data['likes'] + post_data['comments']) / post_data['views']
                post_data['engagement_rate'] = round(engagement, 3)
            
            # Check if it's automotive content
            if not self.is_automotive_content(post_data):
                logger.info("Not automotive content - skipping transcript extraction")
                post_data['transcript'] = None
                post_data['transcript_source'] = None
            else:
                # For video content, try to get transcript
                if post_data['is_video'] and self.should_use_whisper(post_data):
                    video_url = post_data.get('videoUrl')
                    if video_url:
                        # Run async function in sync context
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        try:
                            transcript = loop.run_until_complete(
                                self.download_and_transcribe_video(video_url)
                            )
                            
                            if transcript:
                                logger.info("✅ Successfully transcribed with Whisper")
                                post_data['transcript'] = transcript
                                post_data['transcript_source'] = 'whisper'
                            else:
                                # Fallback to caption
                                logger.info("Falling back to caption text")
                                post_data['transcript'] = caption
                                post_data['transcript_source'] = 'caption'
                        finally:
                            loop.close()
                    else:
                        logger.warning("No video URL available for transcription")
                        post_data['transcript'] = caption
                        post_data['transcript_source'] = 'caption'
                else:
                    # For non-video posts or low-value content
                    post_data['transcript'] = caption
                    post_data['transcript_source'] = 'caption'
            
            # Cache the result
            self._cache[url] = post_data
            
            logger.info(f"✅ Extracted Instagram data: @{post_data['creator_handle']} - {post_data['title'][:50]}...")
            logger.info(f"Stats: {post_data['views']} views, {post_data['likes']} likes")
            
            return post_data
            
        except Exception as e:
            logger.error(f"Error processing Instagram URL {url}: {e}")
            return None
    
    def get_channel_videos(self, username: str, max_videos: int = 50) -> List[Dict[str, Any]]:
        """Get recent Reels from an Instagram profile using Apify"""
        if not self.client:
            logger.error("Apify client not initialized (missing API token)")
            return []
            
        # Clean username (remove @ if present)
        username = username.lstrip('@')
        
        try:
            logger.info(f"Scanning Instagram profile @{username} for Reels")
            
            # Configure the actor run for Instagram Reel Scraper
            run_input = {
                "username": [username],
                "resultsLimit": max_videos,
            }
            
            # Start the actor and wait for it to finish
            logger.info("Starting Apify actor run for profile scan...")
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            
            # Get results from the dataset
            videos = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                # Only include video content (Reels)
                if item.get('type') == 'Video':
                    video_data = {
                        'url': item.get('url', f"https://www.instagram.com/reel/{item.get('shortCode')}/"),
                        'shortcode': item.get('shortCode', ''),
                        'caption': item.get('caption', ''),
                        'title': item.get('caption', '')[:100] if item.get('caption') else '',
                        'is_video': True,
                        'duration': item.get('videoDuration', 0),
                        'published_date': datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00')).replace(tzinfo=None) if item.get('timestamp') else None,
                        'view_count': item.get('videoViewCount', 0),
                        'like_count': item.get('likesCount', 0),
                        'comment_count': item.get('commentsCount', 0),
                        'hashtags': self.extract_hashtags_from_caption(item.get('caption', ''))
                    }
                    videos.append(video_data)
            
            logger.info(f"Found {len(videos)} Reels from @{username}")
            return videos
            
        except Exception as e:
            logger.error(f"Error scanning Instagram profile @{username}: {e}")
            return []
    
    def search_channel_for_vehicle(self, channel_url: str, make: str, model: str, 
                                  start_date: Optional[datetime] = None, 
                                  days_forward: int = 90) -> Optional[Dict[str, Any]]:
        """Search an Instagram profile for posts mentioning a specific vehicle"""
        # Extract username from URL
        username_match = re.search(r'instagram\.com/([^/?]+)', channel_url)
        if not username_match:
            logger.error(f"Could not extract username from URL: {channel_url}")
            return None
            
        username = username_match.group(1)
        
        logger.info(f"Searching @{username} for {make} {model}")
        
        # Get list of videos from channel
        channel_videos = self.get_channel_videos(username, max_videos=50)
        
        if not channel_videos:
            logger.warning(f"No videos found in channel: @{username}")
            return None
            
        logger.info(f"Found {len(channel_videos)} videos to scan")
        
        # Pre-filter videos by make/model FIRST, date filtering later
        make_lower = make.lower()
        model_lower = model.lower()
        
        relevant_videos = []
        
        for video in channel_videos:
            
            # Check caption and hashtags for make/model
            search_text = f"{video.get('caption', '')} {' '.join(video.get('hashtags', []))}".lower()
            
            # Check for make
            make_found = False
            make_synonyms = get_make_synonyms(make)
            for synonym in make_synonyms:
                if synonym in search_text:
                    make_found = True
                    break
            
            if not make_found:
                continue
                
            # Check for model
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
            logger.info(f"No videos found mentioning {make} {model}")
            return None
            
        logger.info(f"Found {len(relevant_videos)} potential matches, processing most recent...")
        
        # Sort by date (newest first)
        relevant_videos.sort(key=lambda x: x.get('published_date') or datetime.min, reverse=True)
        
        # Process videos until we find one with good content
        for video in relevant_videos:
            logger.info(f"Processing: {video['title'][:80]}...")
            
            # Get full video content
            full_video_data = self.extract_content(video['url'])
            
            if full_video_data and full_video_data.get('transcript'):
                # Use the same scoring system as TikTok
                from src.utils.tiktok_content_scorer import score_tiktok_relevance
                
                # Score the content
                relevance_score = score_tiktok_relevance(full_video_data, make, model)
                
                logger.info(f"Content relevance score: {relevance_score['total_score']}/100")
                logger.info(f"  Hashtags: {relevance_score['hashtag_score']}/40")
                logger.info(f"  Caption: {relevance_score['title_score']}/30")
                logger.info(f"  Transcript: {relevance_score['transcript_score']}/10")
                logger.info(f"Recommendation: {relevance_score['recommendation']}")
                
                # Accept if score is high enough
                if relevance_score['total_score'] >= 35:
                    logger.info(f"🎯 SUCCESS: Found {make} {model} content (score: {relevance_score['total_score']})")
                    full_video_data['relevance_score'] = relevance_score
                    return full_video_data
                else:
                    logger.info(f"Score too low ({relevance_score['total_score']}/100), trying next video...")
            else:
                logger.warning(f"Could not extract content from video, trying next...")
        
        logger.info(f"Processed all potential matches, none had {make} {model} in content")
        return None

# Global handler instance
_handler = None

def get_handler() -> InstagramHandler:
    """Get or create singleton InstagramHandler instance"""
    global _handler
    if _handler is None:
        _handler = InstagramHandler()
    return _handler

# Wrapper functions to match TikTok interface exactly
def process_instagram_post(url: str) -> Optional[Dict[str, Any]]:
    """Process an Instagram post/reel URL (matches TikTok interface)"""
    handler = get_handler()
    return handler.extract_content(url)

def get_profile_posts(profile_url: str, max_posts: int = 50) -> List[Dict[str, Any]]:
    """Get posts from an Instagram profile (matches TikTok interface)"""
    # Extract username from URL
    username_match = re.search(r'instagram\.com/([^/?]+)', profile_url)
    if not username_match:
        logger.error(f"Could not extract username from URL: {profile_url}")
        return []
    
    username = username_match.group(1)
    handler = get_handler()
    return handler.get_channel_videos(username, max_posts)

def search_profile_for_vehicle(profile_url: str, make: str, model: str, 
                               start_date: Optional[datetime] = None, 
                               days_forward: int = 90) -> Optional[Dict[str, Any]]:
    """Search Instagram profile for vehicle (matches TikTok interface)"""
    handler = get_handler()
    return handler.search_channel_for_vehicle(profile_url, make, model, start_date, days_forward)

# Additional wrapper for compatibility
def process_tiktok_video(url: str) -> Optional[Dict[str, Any]]:
    """Wrapper to match TikTok interface - processes Instagram posts/reels"""
    return process_instagram_post(url)

def get_channel_videos(channel_url: str, max_videos: int = 50) -> List[Dict[str, Any]]:
    """Wrapper to match TikTok interface - gets Instagram profile posts"""
    return get_profile_posts(channel_url, max_videos)

def search_channel_for_vehicle(channel_url: str, make: str, model: str, 
                              start_date: Optional[datetime] = None, 
                              days_forward: int = 90) -> Optional[Dict[str, Any]]:
    """Wrapper to match TikTok interface - searches Instagram profile"""
    return search_profile_for_vehicle(channel_url, make, model, start_date, days_forward)