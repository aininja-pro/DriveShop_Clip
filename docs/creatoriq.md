# CreatorIQ Module Documentation

## Module: `src/creatoriq/`

### Purpose

The CreatorIQ module provides comprehensive integration with the CreatorIQ influencer marketing platform to extract social media post data from campaigns. It implements multiple authentication methods, data extraction strategies, and export capabilities to reliably capture influencer content URLs and engagement metrics. The module is designed with fallback strategies to ensure data extraction even when API access is limited.

### Key Components

#### GraphQL Client (`graphql_client.py`)
```python
class CreatorIQClient:
    """
    Direct API client for CreatorIQ's GraphQL endpoint.
    Handles authentication, pagination, and data extraction.
    """
    
    def get_campaign_posts(self, campaign_id: int, limit: int = 1000) -> List[Dict]:
        """
        Fetches all posts for a campaign using GraphQL queries.
        Implements cursor-based pagination.
        """
```

#### CSV Exporter (`csv_exporter.py`)
```python
class CSVExporter:
    """
    Exports CreatorIQ post data to CSV format.
    Generates detailed exports and summary statistics.
    """
    
    def export_to_csv(self, posts: List[Dict], output_path: str, 
                     include_summary: bool = True):
        """
        Exports posts with cleaned data and optional summary statistics.
        """
```

#### Authentication Handlers

1. **Browser Session Auth (`auth_headers.py`)**:
   ```python
   def get_auth_headers():
       """
       Extracts authentication headers from browser session.
       Includes cookies, CSRF tokens, and auth tokens.
       """
   ```

2. **API Key Auth (`api_key_auth.py`)**:
   ```python
   class APIKeyClient:
       """
       Cleaner authentication using CreatorIQ API keys.
       Preferred method when available.
       """
   ```

3. **Hybrid Auth (`hybrid_auth_client.py`)**:
   ```python
   class HybridCreatorIQClient:
       """
       Automatically selects best available authentication method.
       Falls back gracefully between API key and browser auth.
       """
   ```

4. **Public Client (`public_client.py`)**:
   ```python
   class PublicCreatorIQClient:
       """
       Accesses public/shared reports without authentication.
       Uses browser automation for public campaign access.
       """
   ```

#### Web Scraping Components

1. **Playwright Scraper (`playwright_scraper.py`)**:
   ```python
   async def scrape_campaign_with_playwright(url: str, save_responses: bool = True):
       """
       Browser automation with network traffic capture.
       Implements infinite scrolling and response saving.
       """
   ```

2. **Browser Extractor (`browser_extractor.py`)**:
   ```python
   def extract_posts_from_browser(campaign_url: str):
       """
       Direct DOM extraction from rendered pages.
       Scrolls and extracts post data from HTML elements.
       """
   ```

3. **Parser (`parser.py`)**:
   ```python
   def extract_urls_from_html(html_content: str) -> List[str]:
       """
       Extracts social media URLs using multiple strategies.
       Handles API responses, embedded JSON, and regex patterns.
       """
   ```

### Expected Inputs/Outputs

#### Inputs
1. **Campaign URL**:
   ```
   https://app.creatoriq.com/campaigns/[CAMPAIGN_ID]/posts
   ```

2. **Authentication Options**:
   - API Key: `CREATORIQ_API_KEY` environment variable
   - Browser Headers: Interactive collection via terminal
   - Public Access: No authentication required

3. **Configuration**:
   ```python
   {
       'limit': 1000,  # Max posts to fetch
       'include_summary': True,  # Generate statistics
       'save_responses': True,  # Save raw API responses
       'scroll_delay': 2  # Seconds between scrolls
   }
   ```

#### Outputs
1. **Post Data Structure**:
   ```json
   {
       "url": "https://www.instagram.com/p/ABC123/",
       "creator_name": "John Doe",
       "creator_username": "@johndoe",
       "platform": "instagram",
       "impressions": 50000,
       "likes": 2500,
       "comments": 150,
       "shares": 75,
       "engagement_rate": 5.5,
       "caption": "Post caption text...",
       "published_at": "2024-01-15T10:30:00Z",
       "thumbnail_url": "https://..."
   }
   ```

2. **CSV Export Files**:
   - `campaign_posts.csv`: Detailed post data
   - `campaign_summary.txt`: Platform breakdown and top creators

3. **Saved Responses** (optional):
   - `campaign_[ID]_responses.json`: Raw API responses
   - `campaign_[ID]_html.html`: Captured page HTML

### Dependencies

```python
# External Libraries
import playwright  # Browser automation
import httpx       # HTTP client
import pandas      # Data processing
from bs4 import BeautifulSoup  # HTML parsing

# Internal Modules
from src.utils.logger import get_logger
```

### Data Extraction Strategies

#### 1. GraphQL API (Primary)
- Direct queries to CreatorIQ's GraphQL endpoint
- Most reliable and complete data
- Requires authentication
- Cursor-based pagination

#### 2. Network Interception
- Captures API responses during page load
- Useful when direct API access fails
- Extracts from XHR/Fetch responses
- Requires browser automation

#### 3. Embedded JSON
- Parses `window.__INITIAL_STATE__` from page
- Contains pre-loaded campaign data
- Fast but may be incomplete
- No pagination support

#### 4. DOM Parsing
- Extracts from rendered HTML elements
- Last resort when APIs fail
- Handles dynamic content via scrolling
- May miss some data fields

### Authentication Flow

```
1. Check for API Key → Use APIKeyClient
   ↓ (if not available)
2. Check for Browser Headers → Use BrowserAuthClient
   ↓ (if not available)
3. Check if Public URL → Use PublicClient
   ↓ (if not available)
4. Prompt for Authentication Method
```

### Error Handling

1. **Authentication Failures**:
   - Clear error messages with solutions
   - Automatic fallback to next method
   - Session refresh capabilities

2. **Rate Limiting**:
   - Configurable delays between requests
   - Exponential backoff on 429 errors
   - Request queuing

3. **Data Extraction Failures**:
   - Multiple extraction strategies
   - Partial data recovery
   - Detailed error logging

4. **Network Issues**:
   - Retry logic with backoff
   - Timeout configuration
   - Connection pooling

### Performance Considerations

- **Pagination**: Fetches 100 posts per request
- **Scrolling**: 2-second delay between scrolls
- **Network Capture**: ~10MB per 1000 posts
- **Export Time**: ~1 second per 1000 posts
- **Memory Usage**: Streaming for large datasets

### Usage Examples

#### Command Line
```bash
# Extract campaign URLs
python -m src.creatoriq.extract_campaign_urls [CAMPAIGN_URL]

# Export to CSV with API key
python -m src.creatoriq.scrape_campaign_report [CAMPAIGN_URL]

# Interactive browser extraction
python -m src.creatoriq.scrape_posts_from_browser
```

#### Python Integration
```python
from src.creatoriq import HybridCreatorIQClient, CSVExporter

# Initialize client
client = HybridCreatorIQClient()

# Get campaign posts
posts = client.get_campaign_posts(campaign_id=12345)

# Export to CSV
exporter = CSVExporter()
exporter.export_to_csv(posts, "output.csv", include_summary=True)
```

### Limitations

- **Platform Support**: Instagram, TikTok, YouTube primarily
- **Historical Data**: Limited by CreatorIQ retention
- **Real-time Updates**: Requires re-scraping
- **API Rate Limits**: Varies by subscription tier
- **Browser Detection**: May trigger anti-bot measures