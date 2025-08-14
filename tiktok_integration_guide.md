# TikTok Integration Guide

## 1. Integration into ingest.py

### Add Import (line ~46)
```python
from src.utils.tiktok_handler import process_tiktok_video
```

### Update URL Detection (line ~1036)
```python
# Determine URL type (YouTube, TikTok, or web)
if 'youtube.com' in url or 'youtu.be' in url:
    url_attempt['content_type'] = 'youtube'
    url_attempt['processing_method'] = 'YouTube API'
    clip_data = process_youtube_url(url, loan)
elif 'tiktok.com' in url or 'vm.tiktok.com' in url:
    url_attempt['content_type'] = 'tiktok'
    url_attempt['processing_method'] = 'TikTok Handler'
    clip_data = process_tiktok_url(url, loan)
else:
    url_attempt['content_type'] = 'web'
    url_attempt['processing_method'] = 'Web Crawler'
    clip_data = process_web_url(url, loan)
```

### Add process_tiktok_url Function (after line ~850)
```python
def process_tiktok_url(url: str, loan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a TikTok URL to extract video content with date filtering.
    
    Args:
        url: TikTok URL
        loan: Loan data dictionary
        
    Returns:
        Dictionary with video content or None if not found
    """
    try:
        logger.info(f"Processing TikTok video: {url}")
        
        # Extract TikTok video data
        video_data = process_tiktok_video(url)
        
        if not video_data:
            logger.warning(f"Could not extract TikTok video data from: {url}")
            return None
        
        # Check video upload date against loan start date
        start_date = loan.get('start_date')
        video_date = video_data.get('published_date')
        
        # Apply date filtering (forward from start date)
        if not is_content_within_date_range(video_date, start_date, 90):
            if video_date and start_date:
                days_diff = abs((video_date - start_date).days)
                logger.warning(f"❌ TikTok video outside date range: {days_diff} days difference")
            return None
        
        # Check if video is relevant to the vehicle
        make = loan.get('make', '').lower()
        model = loan.get('model', '').lower()
        
        # Check title, description, and hashtags for relevance
        title_desc = f"{video_data.get('title', '')} {video_data.get('description', '')}".lower()
        hashtags_text = ' '.join(video_data.get('hashtags', [])).lower()
        full_text = f"{title_desc} {hashtags_text}"
        
        if make in full_text or model in full_text:
            logger.info(f"✅ Found relevant TikTok video: {video_data.get('title')}")
            
            # Get transcript/captions or fallback to description
            content = video_data.get('transcript', video_data.get('description', ''))
                
            if content:
                return {
                    'url': url,
                    'content': content,
                    'content_type': 'tiktok_video',
                    'title': video_data.get('title', f"TikTok by @{video_data.get('creator_handle', 'unknown')}"),
                    'published_date': video_date,
                    'channel_name': f"@{video_data.get('creator_handle', '')}",
                    'view_count': str(video_data.get('views', 0)),
                    # Add TikTok-specific fields
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
        
        logger.info(f"TikTok video not relevant to {make} {model}")
        return None
        
    except Exception as e:
        logger.error(f"Error processing TikTok URL {url}: {e}")
        return None
```

## 2. Database Migration

Create a new migration file: `migrations/add_tiktok_support.sql`

```sql
-- Add TikTok support to clips table
BEGIN;

-- Add platform column
ALTER TABLE clips ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT 'web' 
    CHECK (platform IN ('web', 'youtube', 'tiktok'));

-- Update existing YouTube clips
UPDATE clips 
SET platform = 'youtube' 
WHERE clip_url LIKE '%youtube.com%' OR clip_url LIKE '%youtu.be%';

-- Add TikTok-specific columns
ALTER TABLE clips ADD COLUMN IF NOT EXISTS creator_handle TEXT;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS video_id TEXT;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS hashtags TEXT[];
ALTER TABLE clips ADD COLUMN IF NOT EXISTS engagement_metrics JSONB;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_clips_platform ON clips(platform);
CREATE INDEX IF NOT EXISTS idx_clips_creator_handle ON clips(creator_handle);
CREATE INDEX IF NOT EXISTS idx_clips_video_id ON clips(video_id);
CREATE INDEX IF NOT EXISTS idx_clips_hashtags ON clips USING GIN(hashtags);

COMMIT;
```

## 3. Environment Variables

Add to your `.env` file:
```bash
# TikTok Configuration
TIKTOK_COOKIES_FILE=/path/to/cookies.txt  # Optional: browser cookies for better access

# Whisper Configuration  
WHISPER_MODEL=base  # Options: tiny, base, small, medium, large
```

## 4. Dependencies

Add to `requirements.txt`:
```
yt-dlp>=2024.1.0
openai-whisper>=20231106
```

## 5. ScrapFly Integration (Optional)

ScrapFly CAN be used for TikTok, but yt-dlp is more reliable for video metadata extraction. However, ScrapFly could be useful for:

1. **Creator Page Scraping**: Getting list of videos from a creator
2. **Trending Discovery**: Finding trending automotive content
3. **Fallback Method**: When yt-dlp is blocked

Example ScrapFly TikTok integration:
```python
def scrape_tiktok_with_scrapfly(url: str) -> Optional[Dict[str, Any]]:
    """Use ScrapFly as fallback for TikTok scraping"""
    from scrapfly import ScrapflyClient, ScrapeConfig
    
    client = ScrapflyClient(key=os.getenv('SCRAPFLY_API_KEY'))
    
    try:
        result = client.scrape(ScrapeConfig(
            url=url,
            render_js=True,
            wait_for_selector="video",
            country="US",
            asp=True  # Anti-bot bypass
        ))
        
        # Parse TikTok page structure
        # ... extraction logic ...
        
    except Exception as e:
        logger.error(f"ScrapFly TikTok scrape failed: {e}")
        return None
```

## 6. Testing URLs

Here are some automotive TikTok URLs you can test with:

```python
test_urls = [
    # Standard format
    "https://www.tiktok.com/@dougjdemuro/video/7381957204817292581",
    "https://www.tiktok.com/@carwow/video/7382145623456789012",
    
    # Short links (vm.tiktok.com)
    "https://vm.tiktok.com/ZMh4Kx9pL/",
    "https://vm.tiktok.com/ZMh4KABnr/",
    
    # New format
    "https://www.tiktok.com/t/ZPRLcXkNf/",
]
```

## 7. Cost Optimization

The handler includes smart cost optimization:

1. **Pre-filtering**: Only processes automotive content
2. **View Threshold**: Only uses Whisper for videos with >10k views  
3. **Duration Limit**: Skips videos longer than 5 minutes
4. **Fallback Strategy**: Description-only for low-value content

## 8. Monitoring

Add to your logging configuration:
```python
# Track TikTok-specific metrics
logger.info(f"TikTok extraction stats: {method} - {success_rate}%")
logger.info(f"Whisper usage: {whisper_calls} calls, ${whisper_cost} total")
```

## 9. Future Enhancements

1. **Batch Processing**: Process multiple TikToks concurrently
2. **Creator Monitoring**: Track specific automotive influencers
3. **Trend Detection**: Identify viral automotive content
4. **Language Support**: Multi-language transcription with Whisper