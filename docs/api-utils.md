# API Utilities Documentation

## Module: `src/utils/youtube_api.py`

### Purpose

The YouTube API module provides a clean interface to YouTube Data API v3 for searching and retrieving video information. It implements intelligent search strategies with model variations, date filtering, and comprehensive error handling while respecting API quotas.

### Key Functions/Classes

#### YouTubeAPIClient Class
```python
class YouTubeAPIClient:
    """
    YouTube Data API v3 client with rate limiting and error handling.
    Provides video search and channel video listing capabilities.
    """
    
    def __init__(self):
        """Initialize with API key from environment."""
```

#### Core Methods
```python
def search_videos(self, make: str, model: str, journalist_name: str = None,
                 start_date: str = None, end_date: str = None) -> List[Dict]:
    """
    Search YouTube videos with intelligent query building.
    Implements model variations for better matching.
    """

def get_channel_videos(self, channel_id: str, max_results: int = 10) -> List[Dict]:
    """
    Retrieve latest videos from a specific channel.
    Used for RSS feed alternative.
    """

def get_video_details(self, video_id: str) -> Optional[Dict]:
    """
    Get detailed information for a specific video.
    Includes duration, views, likes, etc.
    """
```

#### Helper Methods
```python
def generate_model_variations(model: str) -> List[str]:
    """
    Generate search variations for vehicle models.
    Example: "X5" → ["X5", "BMW X5", "X5 BMW"]
    """

def _make_api_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
    """
    Internal method for API requests with rate limiting.
    Handles errors and returns parsed JSON.
    """
```

### Expected Inputs/Outputs

#### Inputs
```python
# Video search
{
    'make': 'Honda',
    'model': 'Accord',
    'journalist_name': 'Doug DeMuro',
    'start_date': '2024-01-01',
    'end_date': '2024-01-31'
}

# Channel videos
{
    'channel_id': 'UC123abc...',
    'max_results': 10
}
```

#### Outputs
```python
# Video data structure
{
    'video_id': 'dQw4w9WgXcQ',
    'title': '2024 Honda Accord Review',
    'channel': 'Car Reviews',
    'channel_id': 'UC123...',
    'published_at': '2024-01-15T10:00:00Z',
    'description': 'Full review of...',
    'thumbnail': 'https://i.ytimg.com/...',
    'url': 'https://youtube.com/watch?v=...'
}
```

### Dependencies

```python
import os
import requests
from datetime import datetime
from typing import List, Dict, Optional

from src.utils.logger import logger
from src.utils.rate_limiter import rate_limiter
```

### API Integration Patterns

1. **Rate Limiting**: Centralized rate limiter before each API call
2. **Error Handling**: Graceful degradation with empty results
3. **Query Building**: Progressive search from specific to general
4. **Pagination**: Handles up to 50 results per request
5. **Quota Management**: Efficient API usage with targeted queries

---

## Module: `src/utils/youtube_handler.py`

### Purpose

The YouTube Handler provides comprehensive YouTube content extraction using multiple methods including RSS feeds, direct scraping, and API fallbacks. It specializes in extracting video metadata and transcripts without requiring API keys for most operations.

### Key Functions/Classes

#### Core Functions
```python
def extract_youtube_content(url: str, make: str = None, model: str = None,
                          journalist_name: str = None,
                          start_date: str = None, end_date: str = None) -> Dict:
    """
    Main extraction function with multiple fallback methods.
    Attempts RSS → Direct scraping → API.
    """

def extract_channel_videos_from_rss(channel_url: str, limit: int = 10) -> List[Dict]:
    """
    Extract videos via YouTube RSS feed (no API needed).
    Fast and reliable for recent videos.
    """

def extract_channel_id(channel_url: str) -> Optional[str]:
    """
    Extract channel ID using multiple methods.
    Handles various YouTube URL formats.
    """

def check_model_in_title(title: str, model: str) -> bool:
    """
    Flexible model matching in video titles.
    Handles variations and partial matches.
    """
```

#### Transcript Extraction
```python
def get_video_transcript(video_id: str) -> Optional[str]:
    """
    Extract video transcript/captions.
    Falls back to metadata if transcript unavailable.
    """
```

### Content Extraction Methods

1. **RSS Feed Method** (Preferred)
   - No API key required
   - Returns latest 15 videos
   - Structured XML data
   - Very fast and reliable

2. **Direct Scraping**
   - BeautifulSoup HTML parsing
   - Pattern matching for data extraction
   - Works when RSS unavailable

3. **API Fallback**
   - Uses YouTube API client
   - Only when other methods fail
   - Preserves API quota

### Expected Inputs/Outputs

#### Inputs
```python
{
    'url': 'https://youtube.com/watch?v=abc123',
    'make': 'Toyota',
    'model': 'Camry',
    'journalist_name': 'Alex on Autos',
    'start_date': '2024-01-01',
    'end_date': '2024-01-31'
}
```

#### Outputs
```python
{
    'content': 'Video transcript or description...',
    'title': '2024 Toyota Camry Review',
    'url': 'https://youtube.com/watch?v=abc123',
    'published_date': '2024-01-15',
    'channel': 'Alex on Autos',
    'views': '50000',
    'duration': 'PT15M30S'
}
```

---

## Module: `src/utils/google_search.py`

### Purpose

The Google Search module provides web search capabilities using Google Custom Search API with Bing as a fallback. It implements intelligent query building, result filtering, and attribution verification for finding automotive journalism content.

### Key Functions/Classes

#### Core Search Functions
```python
def search_google(query: str, site: str = None, num_results: int = 10) -> List[Dict]:
    """
    Search using Google Custom Search API.
    Supports site-specific searches.
    """

def search_for_article(make: str, model: str, journalist_name: str,
                      media_outlet: str = None, start_date: str = None,
                      end_date: str = None) -> List[Dict]:
    """
    Comprehensive article search with multiple strategies.
    Implements fallback from Google to Bing.
    """

async def search_for_article_async(make: str, model: str, 
                                  journalist_name: str, **kwargs) -> List[Dict]:
    """
    Async version for concurrent searches.
    """
```

#### Result Processing
```python
def filter_and_score_results(results: List[Dict], make: str, model: str,
                           journalist_name: str, start_date: str = None) -> List[Dict]:
    """
    Score and filter search results.
    Implements relevance scoring algorithm.
    """

def verify_author_attribution(url: str, content: str, 
                            journalist_name: str) -> Dict:
    """
    Verify if content is actually by the journalist.
    Returns attribution strength.
    """
```

### Search Strategy

1. **Query Building Hierarchy**:
   - Full query: `"John Doe" Honda Accord review site:example.com`
   - Without quotes: `John Doe Honda Accord review`
   - Model only: `Honda Accord review site:example.com`
   - Broad search: `Honda Accord`

2. **Result Scoring Algorithm**:
   - URL keyword matches (+3 per keyword)
   - Title matches for make/model/journalist
   - Domain restrictions
   - Date filtering

3. **Attribution Verification**:
   - Byline extraction
   - Author meta tag checking
   - Name proximity to article markers

### API Configuration

```python
# Google Custom Search
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID')

# Bing Search (Fallback)
BING_API_KEY = os.getenv('BING_SEARCH_API_KEY')
```

---

## Module: `src/utils/scraping_bee.py`

### Purpose

The ScrapingBee module provides integration with ScrapingBee API for handling JavaScript-heavy sites and bypassing anti-bot measures. It implements domain-specific configurations and intelligent retry mechanisms.

### Key Functions/Classes

#### ScrapingBeeClient Class
```python
class ScrapingBeeClient:
    """
    ScrapingBee API client with retry logic and domain configurations.
    Handles JavaScript rendering and premium proxies.
    """
    
    def __init__(self, api_key: str = None):
        """Initialize with API key validation."""
```

#### Core Methods
```python
def scrape(self, url: str, render_js: bool = True, 
          premium_proxy: bool = False, **kwargs) -> Optional[str]:
    """
    Scrape URL with configurable options.
    Implements retry with exponential backoff.
    """

def get_credits_used(self) -> Dict[str, int]:
    """
    Check API credit usage.
    Returns used and remaining credits.
    """
```

### Domain-Specific Configurations

```python
# YouTube configuration
if 'youtube.com' in url:
    params.update({
        'block_ads': True,
        'wait': 3000,
        'wait_for': '#description'
    })

# Spotlight configuration  
if 'spotlightautomotive.com' in url:
    params.update({
        'wait': 5000,
        'screenshot': False
    })
```

### Retry Strategy

1. **Max Retries**: 3 attempts
2. **Exponential Backoff**: 1s → 2s → 4s
3. **Error-Specific Handling**:
   - 403: Upgrade to premium proxy
   - 422: Validation error (no retry)
   - 429: Rate limit (longer wait)
   - 500: Server error (retry)

---

## Module: `src/utils/scrapfly_client.py`

### Purpose

The ScrapFly module provides the most sophisticated web scraping integration with circuit breaker pattern, advanced rate limiting, and comprehensive error handling. It serves as the primary premium scraping service.

### Key Functions/Classes

#### ScrapFlyClient Class
```python
class ScrapFlyClient:
    """
    ScrapFly API client with circuit breaker and rate limiting.
    Most robust scraping solution in the stack.
    """
    
    def __init__(self):
        """Initialize with API key and circuit breaker state."""
```

#### Core Methods
```python
def scrape(self, url: str, render_js: bool = True,
          country: str = "US", **kwargs) -> Optional[str]:
    """
    Scrape with circuit breaker protection.
    Implements sophisticated rate limiting.
    """

def extract_scrapfly_content(self, url: str, config: Dict = None) -> Optional[str]:
    """
    Main extraction method with fallback strategies.
    Handles retries and circuit breaker logic.
    """
```

#### Circuit Breaker Implementation
```python
def _check_circuit_breaker(self) -> bool:
    """Check if circuit breaker is open."""

def _update_circuit_breaker(self, success: bool):
    """Update circuit breaker state based on result."""

def _reset_circuit_breaker(self):
    """Reset circuit breaker after timeout."""
```

### Advanced Features

1. **Circuit Breaker Pattern**:
   - Opens after 3 consecutive failures
   - 5-minute timeout before reset
   - Prevents cascading failures

2. **Rate Limiting**:
   - Minimum 2-second delay between requests
   - Retry-after header parsing
   - Progressive backoff on rate limits

3. **Configuration Options**:
   ```python
   {
       'asp': True,           # Anti-bot bypass
       'country': 'US',       # Geo-location
       'rendering_wait': 3000, # JS wait time
       'retry': False,        # Internal retry
       'cache': True,         # Response caching
       'debug': True          # Debug info
   }
   ```

### Error Handling Sophistication

1. **Rate Limit Detection**:
   ```python
   # Parses multiple rate limit formats
   - "Request rate limit exceeded (2/sec)"
   - "API rate limit exceeded"
   - Retry-After headers
   ```

2. **Progressive Degradation**:
   - Standard request → ASP mode → Country change → Circuit break

3. **Credit Monitoring**:
   - Tracks usage in response headers
   - Logs credit consumption
   - Warns on low credits

### Performance Metrics

- **Success Rate**: ~99.9% with ASP enabled
- **Average Response Time**: 3-5 seconds
- **Circuit Breaker Recovery**: 5 minutes
- **Rate Limit Compliance**: Automatic