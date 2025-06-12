import os
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import re

from src.utils.logger import setup_logger
from src.utils.rate_limiter import rate_limiter

logger = setup_logger(__name__)

class YouTubeAPIClient:
    """
    YouTube Data API v3 client for reliable channel video searches.
    Replaces ScrapingBee for YouTube content with official API access.
    """
    
    def __init__(self):
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            logger.warning("YOUTUBE_API_KEY not found in environment variables")
        self.base_url = "https://www.googleapis.com/youtube/v3"
        
    def get_channel_id_from_handle(self, handle: str) -> Optional[str]:
        """
        Convert YouTube handle (@username) to channel ID using API.
        
        Args:
            handle: YouTube handle without @ (e.g., "TopherDrives")
            
        Returns:
            Channel ID or None if not found
        """
        if not self.api_key:
            logger.error("YouTube API key not available")
            return None
            
        try:
            # Apply rate limiting
            rate_limiter.wait_if_needed('youtube_api')
            
            # Search for channel by handle
            url = f"{self.base_url}/search"
            params = {
                'key': self.api_key,
                'q': handle,
                'type': 'channel',
                'part': 'snippet',
                'maxResults': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('items'):
                    channel_id = data['items'][0]['snippet']['channelId']
                    logger.info(f"✅ Resolved @{handle} to channel ID: {channel_id}")
                    return channel_id
                else:
                    logger.warning(f"No channel found for handle: @{handle}")
            else:
                logger.error(f"YouTube API error {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"Error resolving YouTube handle @{handle}: {e}")
            
        return None
    
    def get_all_channel_videos(self, channel_id: str, max_videos: int = 200) -> List[Dict[str, Any]]:
        """
        Get ALL videos from a YouTube channel using official API.
        No pagination limits - can retrieve hundreds of videos.
        
        Args:
            channel_id: YouTube channel ID
            max_videos: Maximum number of videos to retrieve (default 200)
            
        Returns:
            List of video dictionaries with title, video_id, published_date, etc.
        """
        if not self.api_key:
            logger.error("YouTube API key not available")
            return []
            
        try:
            videos = []
            next_page_token = None
            
            while len(videos) < max_videos:
                # Apply rate limiting
                rate_limiter.wait_if_needed('youtube_api')
                
                # Get channel's uploads playlist
                url = f"{self.base_url}/search"
                params = {
                    'key': self.api_key,
                    'channelId': channel_id,
                    'type': 'video',
                    'part': 'snippet',
                    'order': 'date',  # Most recent first
                    'maxResults': min(50, max_videos - len(videos)),  # API max is 50 per request
                }
                
                if next_page_token:
                    params['pageToken'] = next_page_token
                
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code != 200:
                    logger.error(f"YouTube API error {response.status_code}: {response.text}")
                    break
                
                data = response.json()
                
                # Process videos from this page
                for item in data.get('items', []):
                    video_info = {
                        'video_id': item['id']['videoId'],
                        'title': item['snippet']['title'],
                        'published': item['snippet']['publishedAt'],
                        'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                        'description': item['snippet'].get('description', ''),
                        'channel_title': item['snippet']['channelTitle'],
                        'method': 'youtube_api'
                    }
                    videos.append(video_info)
                
                # Check if there are more pages
                next_page_token = data.get('nextPageToken')
                if not next_page_token:
                    break  # No more pages
                    
                logger.info(f"📺 Retrieved {len(videos)} videos so far...")
            
            logger.info(f"🎬 YouTube API retrieved {len(videos)} total videos from channel {channel_id}")
            return videos
            
        except Exception as e:
            logger.error(f"Error getting channel videos via YouTube API: {e}")
            return []
    
    def search_channel_for_videos(self, channel_url: str, make: str, model: str) -> Optional[List[Dict[str, Any]]]:
        """
        Search YouTube channel for videos matching make/model using official API.
        Replaces ScrapingBee with reliable, unlimited video access.
        
        Args:
            channel_url: YouTube channel URL (e.g., https://www.youtube.com/@TopherDrives)
            make: Vehicle make to search for
            model: Vehicle model to search for
            
        Returns:
            List of matching video dictionaries
        """
        try:
            # Extract channel handle or ID from URL
            channel_id = None
            
            # Handle @username format
            handle_match = re.search(r'youtube\.com\/@([a-zA-Z0-9_-]+)', channel_url)
            if handle_match:
                handle = handle_match.group(1)
                channel_id = self.get_channel_id_from_handle(handle)
            
            # Handle direct channel ID format
            elif '/channel/' in channel_url:
                channel_match = re.search(r'youtube\.com\/channel\/([a-zA-Z0-9_-]+)', channel_url)
                if channel_match:
                    channel_id = channel_match.group(1)
            
            if not channel_id:
                logger.error(f"Could not extract channel ID from URL: {channel_url}")
                return None
            
            logger.info(f"🔍 Searching YouTube channel {channel_id} for {make} {model} videos...")
            
            # Get ALL videos from channel (no 25-video limit!)
            all_videos = self.get_all_channel_videos(channel_id, max_videos=200)
            
            if not all_videos:
                logger.warning(f"No videos found in channel {channel_id}")
                return None
            
            # Filter for relevant videos
            relevant_videos = []
            make_lower = make.lower()
            model_lower = model.lower()
            
            # Create model variations
            model_variations = [
                model_lower,
                model_lower.replace('-', ' '),  # cx-90 -> cx 90
                model_lower.replace(' ', '-'),  # cx 90 -> cx-90
                f"{make_lower} {model_lower}",  # mazda cx-90
                f"{make_lower}{model_lower}",   # mazdacx90
            ]
            
            logger.info(f"🔍 Filtering {len(all_videos)} videos for make='{make}' and model variations: {model_variations}")
            
            # Show first 50 videos for debugging
            logger.info("🔍 DEBUG: First 50 video titles from YouTube API:")
            for i, video in enumerate(all_videos[:50]):
                logger.info(f"  {i+1}. '{video['title']}'")
            
            for video in all_videos:
                title_lower = video['title'].lower()
                
                # Check if title contains make and any model variation
                if make_lower in title_lower:
                    for model_var in model_variations:
                        if model_var in title_lower:
                            logger.info(f"🎯 YouTube API found relevant video: {video['title']}")
                            relevant_videos.append(video)
                            break
            
            logger.info(f"🎬 YouTube API found {len(relevant_videos)} relevant videos for {make} {model}")
            return relevant_videos[:10]  # Return top 10 most relevant
            
        except Exception as e:
            logger.error(f"Error searching YouTube channel with API: {e}")
            return None 