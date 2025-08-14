# Instagram Reels Integration

This document describes the Instagram Reels integration for DriveShop Clip Tracking, which enables extraction and analysis of automotive content from Instagram.

## Overview

The Instagram integration follows the same pattern as our TikTok handler, providing:
- Metadata extraction from Instagram Reels and Posts
- Audio transcription via Whisper API for Reels
- Profile scanning for vehicle mentions
- Smart relevance scoring using hashtags, captions, and transcripts

## Features

### 1. Direct Reel/Post Processing
Extract content from specific Instagram URLs:
```python
from src.utils.instagram_handler import process_instagram_post

# Process a Reel or Post
result = process_instagram_post("https://www.instagram.com/reel/C1234567890/")
```

### 2. Profile Scanning
Search creator profiles for specific vehicles:
```python
from src.utils.instagram_handler import search_profile_for_vehicle

# Search for Toyota Crown Signia content
result = search_profile_for_vehicle(
    "https://www.instagram.com/carwow/",
    make="Toyota",
    model="Crown Signia",
    start_date=datetime(2024, 1, 1),
    days_forward=90
)
```

### 3. Content Scoring
Uses the same 100-point scoring system as TikTok:
- Hashtags: 40 points (most reliable)
- Caption: 30 points (reliable)
- Description: 20 points (semi-reliable)
- Transcript: 10 points (least reliable due to errors)
- Acceptance threshold: 35+ points

## Authentication

Instagram requires authentication for most operations:

### Environment Variables
```bash
export INSTAGRAM_USERNAME="your_username"
export INSTAGRAM_PASSWORD="your_password"
export INSTAGRAM_SESSION_FILE=".instaloader_session"  # Optional
```

### Best Practices
1. Use a dedicated Instagram account for scraping
2. The handler saves sessions to avoid repeated logins
3. Respect rate limits (8+ seconds between requests)

## URL Support

The handler supports various Instagram URL formats:
- `https://www.instagram.com/reel/XXXXX/` - Reels
- `https://www.instagram.com/p/XXXXX/` - Posts (including video posts)
- `https://www.instagram.com/username/` - Profile URLs

## Rate Limiting

Instagram has stricter rate limits than TikTok:
- Base delay: 8 seconds between requests
- Exponential backoff on errors (up to 128 seconds)
- Automatic session management to reduce login requests

## Integration with Main Pipeline

The Instagram handler is fully integrated into the main processing pipeline:

```python
# In process_loan_for_database() or process_loan()
if 'instagram.com' in url:
    result = process_instagram_url(url, loan)
```

## Data Structure

The handler returns data in the same format as other platforms:
```python
{
    'url': 'https://www.instagram.com/reel/...',
    'shortcode': 'C1234567890',
    'caption': 'Check out this amazing car...',
    'title': 'First 100 chars of caption...',
    'creator': 'Full Name',
    'creator_handle': 'username',
    'is_video': True,
    'duration': 30,  # seconds
    'views': 50000,  # for Reels
    'likes': 5000,
    'comments': 200,
    'published_date': datetime,
    'hashtags': ['cars', 'toyota', 'review'],
    'transcript': 'Whisper transcription...',
    'transcript_source': 'whisper|caption',
    'engagement_rate': 0.104,
    'platform': 'instagram'
}
```

## Automotive Content Detection

The handler includes automotive-specific hashtag detection:
- General: #car, #cars, #automotive, #carreview
- Categories: #suv, #truck, #sedan, #electriccar
- Enthusiast: #carsofinstagram, #instacar, #cargram
- Brands: All major automotive brands

## Cost Considerations

- Whisper API: $0.006 per minute of audio
- Only transcribes automotive content
- Falls back to captions when transcription fails
- Warns on videos over 5 minutes

## Error Handling

The handler includes comprehensive error handling:
- Login failures → Uses anonymous mode with limitations
- Rate limit errors → Exponential backoff
- Private profiles → Logged and skipped
- Missing captions → Falls back to description

## Testing

Run the test suite to verify functionality:
```bash
python test_instagram_handler.py
```

Example integration script:
```bash
python example_instagram_integration.py
```

## Popular Automotive Instagram Accounts

For testing and verification:
- @supercarblondie - Luxury car reviews
- @vehicle.virals - Automotive content aggregator
- @carwow - Car reviews and comparisons
- @motor1com - Automotive news
- @topgear - Top Gear official
- @carthrottle - Car culture
- @speedhunters - Performance cars

## Limitations

1. **No yt-dlp support** - Uses Instaloader library instead
2. **Authentication required** - Anonymous access is very limited
3. **Strict rate limits** - Much slower than TikTok processing
4. **No native transcription** - Relies on Whisper API

## Future Enhancements

1. Story support (currently only Posts/Reels)
2. IGTV long-form video support
3. Comment sentiment analysis
4. Creator collaboration detection
5. Branded content detection