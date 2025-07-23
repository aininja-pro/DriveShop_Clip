# YouTube ScrapFly Configuration Guide

## Overview
The YouTube ScrapFly integration now supports configurable parameters for controlling how many videos to fetch from YouTube channels. This allows you to balance between comprehensive video coverage and API performance/costs.

## Configuration Options

### 1. Via config.py (Default Values)
Located in `src/utils/config.py`:
```python
YOUTUBE_SCRAPFLY_CONFIG = {
    'max_videos': 100,       # Maximum number of videos to try to fetch from a channel
    'scroll_actions': 5,     # Number of scroll actions to perform (each loads ~10-15 more videos)
    'scroll_wait_ms': 2000   # Milliseconds to wait after each scroll
}
```

### 2. Via Environment Variables (Override Defaults)
You can override the default values by setting environment variables in your `.env` file:

```bash
# YouTube ScrapFly Configuration
YOUTUBE_SCRAPFLY_MAX_VIDEOS=150       # Fetch up to 150 videos
YOUTUBE_SCRAPFLY_SCROLL_ACTIONS=8     # Perform 8 scroll actions (~120 videos)
YOUTUBE_SCRAPFLY_SCROLL_WAIT_MS=3000  # Wait 3 seconds between scrolls
```

### 3. Via Function Parameters (Runtime Override)
When calling the function directly, you can override the max_videos parameter:

```python
from src.utils.youtube_handler import scrape_channel_videos_with_scrapfly

# Use custom max_videos value
videos = scrape_channel_videos_with_scrapfly(
    channel_url="https://www.youtube.com/@JavierMota",
    make="Lexus",
    model="LX 700h",
    max_videos=200  # Override to fetch up to 200 videos
)
```

## Understanding the Parameters

### max_videos
- **Purpose**: Sets the upper limit on how many videos to attempt to fetch
- **Default**: 100 videos
- **Impact**: Higher values mean more comprehensive coverage but longer processing time
- **Recommendation**: 100-150 for most channels, 200+ for very active channels

### scroll_actions
- **Purpose**: Number of times to scroll down the page to load more videos
- **Default**: 5 scrolls
- **Impact**: Each scroll typically loads 10-15 more videos
- **Formula**: Approximate videos loaded = 30 (initial) + (scroll_actions × 12)
- **Recommendation**: 
  - 5 scrolls ≈ 90 videos
  - 8 scrolls ≈ 126 videos
  - 10 scrolls ≈ 150 videos

### scroll_wait_ms
- **Purpose**: Milliseconds to wait after each scroll for content to load
- **Default**: 2000ms (2 seconds)
- **Impact**: Shorter waits may miss content; longer waits increase total time
- **Recommendation**: 2000-3000ms for reliable loading

## Performance Considerations

1. **API Credits**: More scrolls = more JavaScript rendering = higher ScrapFly credit usage
2. **Time**: Total time ≈ (scroll_actions × scroll_wait_ms) + initial load time
3. **Network**: Slower connections may need longer scroll_wait_ms values

## Example Configurations

### Conservative (Default)
```bash
YOUTUBE_SCRAPFLY_MAX_VIDEOS=100
YOUTUBE_SCRAPFLY_SCROLL_ACTIONS=5
YOUTUBE_SCRAPFLY_SCROLL_WAIT_MS=2000
```
- Fetches ~90 videos in ~10 seconds

### Comprehensive Coverage
```bash
YOUTUBE_SCRAPFLY_MAX_VIDEOS=200
YOUTUBE_SCRAPFLY_SCROLL_ACTIONS=10
YOUTUBE_SCRAPFLY_SCROLL_WAIT_MS=2500
```
- Fetches ~150 videos in ~25 seconds

### Quick Scan
```bash
YOUTUBE_SCRAPFLY_MAX_VIDEOS=50
YOUTUBE_SCRAPFLY_SCROLL_ACTIONS=2
YOUTUBE_SCRAPFLY_SCROLL_WAIT_MS=1500
```
- Fetches ~50 videos in ~3 seconds

## Monitoring

The logs will show the configuration being used:
```
🎬 Scraping YouTube channel with ScrapFly (enhanced scrolling for 100 videos)...
📜 ScrapFly successfully extracted 52 videos after scrolling
```

## Troubleshooting

1. **Not finding enough videos**: Increase `scroll_actions`
2. **Videos not loading properly**: Increase `scroll_wait_ms`
3. **Taking too long**: Decrease `scroll_actions` or `max_videos`
4. **API credit concerns**: Reduce `scroll_actions` to minimize JavaScript rendering

## Best Practices

1. Start with default values and adjust based on your needs
2. Monitor ScrapFly credit usage when increasing scroll_actions
3. Consider channel posting frequency when setting max_videos
4. Use environment variables for easy configuration without code changes