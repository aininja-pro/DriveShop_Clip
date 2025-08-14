# Updated process_tiktok_url function for ingest.py
# This replaces the simple version with channel scanning support

def process_tiktok_url(url: str, loan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a TikTok URL - either a direct video or a channel.
    For channels, searches for videos mentioning the specific vehicle.
    
    Args:
        url: TikTok URL (video or channel)
        loan: Loan data dictionary
        
    Returns:
        Dictionary with video content or None if not found
    """
    try:
        logger.info(f"Processing TikTok URL: {url}")
        
        # Import the TikTok handler functions
        from src.utils.tiktok_handler import process_tiktok_video, search_channel_for_vehicle
        
        # Get vehicle info from loan
        make = loan.get('make', '')
        model = loan.get('model', '')
        start_date = loan.get('start_date')
        
        # Check if it's a channel URL or video URL
        if '@' in url and '/video/' not in url:
            # This is a channel URL - search for relevant videos
            logger.info(f"TikTok channel detected, searching for {make} {model} videos...")
            
            video_data = search_channel_for_vehicle(
                channel_url=url,
                make=make,
                model=model,
                start_date=start_date,
                days_forward=90
            )
            
            if not video_data:
                logger.warning(f"No {make} {model} videos found in TikTok channel: {url}")
                return None
                
        else:
            # This is a direct video URL - process it directly
            logger.info(f"Processing direct TikTok video: {url}")
            
            video_data = process_tiktok_video(url)
            
            if not video_data:
                logger.warning(f"Could not extract TikTok video data from: {url}")
                return None
            
            # Check video date against loan start date
            video_date = video_data.get('published_date')
            if not is_content_within_date_range(video_date, start_date, 90):
                if video_date and start_date:
                    days_diff = abs((video_date - start_date).days)
                    logger.warning(f"❌ TikTok video outside date range: {days_diff} days difference")
                return None
            
            # Verify it's about the right vehicle
            content = video_data.get('transcript', video_data.get('description', '')).lower()
            if make.lower() not in content or model.lower() not in content:
                logger.warning(f"TikTok video does not mention {make} {model}")
                return None
        
        # Format the response for the pipeline
        content = video_data.get('transcript', video_data.get('description', ''))
        
        if content:
            return {
                'url': video_data.get('url'),
                'content': content,
                'content_type': 'tiktok_video',
                'title': video_data.get('title', f"TikTok by @{video_data.get('creator_handle', 'unknown')}"),
                'published_date': video_data.get('published_date'),
                'channel_name': f"@{video_data.get('creator_handle', '')}",
                'view_count': str(video_data.get('views', 0)),
                # TikTok-specific fields
                'platform': 'tiktok',
                'creator_handle': video_data.get('creator_handle'),
                'video_id': video_data.get('video_id'),
                'hashtags': video_data.get('hashtags', []),
                'engagement_metrics': {
                    'views': video_data.get('views', 0),
                    'likes': video_data.get('likes', 0),
                    'comments': video_data.get('comments', 0),
                    'shares': video_data.get('shares', 0),
                    'engagement_rate': video_data.get('engagement_rate', 0)
                }
            }
        
        logger.info(f"No content extracted from TikTok")
        return None
        
    except Exception as e:
        logger.error(f"Error processing TikTok URL {url}: {e}")
        return None