# Crawler Module Documentation

## Module: `src/crawler/crawler/spiders/loan_spider.py`

### Purpose

The Crawler module implements a Scrapy-based spider for discovering and extracting automotive media content from web pages. It provides intelligent content discovery with multi-level crawling capabilities, automatically following relevant links when initial pages don't contain vehicle-specific content. The spider is designed as the foundation layer for the tiered web scraping strategy, focusing on standard HTML extraction before escalation to more advanced techniques.

### Key Functions/Classes

#### LoanSpider Class
```python
class LoanSpider(scrapy.Spider):
    """
    Scrapy spider for crawling automotive media sites.
    Implements smart discovery and multi-level crawling.
    """
    
    name = 'loan_spider'
    allowed_domains = []  # Set dynamically from loan URLs
    start_urls = []      # Set dynamically from loan data
```

#### Initialization
```python
def __init__(self, loans_data: List[Dict[str, Any]] = None, *args, **kwargs):
    """
    Initialize spider with loan data.
    Dynamically generates allowed domains from URLs.
    """
```

#### Request Generation
```python
def start_requests(self) -> Generator[Request, None, None]:
    """
    Generate initial requests from loans data.
    Attaches loan metadata to each request.
    """

def _discover_relevant_pages(self, response: Response, 
                           loan_data: Dict[str, Any]) -> Generator[Request, None, None]:
    """
    Discover and follow links that might contain relevant content.
    Implements smart discovery for review/blog/news sections.
    """
```

#### Content Processing
```python
def parse(self, response: Response) -> Generator[LoanItem, None, None]:
    """
    Main parsing function that extracts content.
    Implements two-level crawling strategy.
    """

def handle_error(self, failure):
    """
    Handle request failures gracefully.
    Creates error items for tracking.
    """
```

#### Extraction Functions
```python
def _extract_title(self, response: Response) -> str:
    """
    Extract page title using multiple strategies.
    Falls back from <title> to <h1> tags.
    """

def _extract_content(self, response: Response, make: str, model: str) -> str:
    """
    Extract main content using common article selectors.
    Progressive fallback from specific to generic selectors.
    """

def _extract_date(self, response: Response) -> Optional[str]:
    """
    Extract publication date from meta tags or HTML elements.
    Checks multiple date formats and locations.
    """
```

#### Utility Functions
```python
def _content_mentions_vehicle(self, content: str, make: str, model: str) -> bool:
    """
    Check if content mentions the vehicle make and model.
    Case-insensitive matching.
    """

def _extract_domain(self, url: str) -> Optional[str]:
    """
    Extract domain from URL for allowed_domains.
    """

def _is_media_file(self, url: str) -> bool:
    """
    Check if URL points to a media file.
    Filters out images, videos, PDFs.
    """
```

### Expected Inputs/Outputs

#### Inputs
1. **Loan Data Structure**:
   ```python
   {
       'work_order': 'WO12345',
       'make': 'Honda',
       'model': 'Accord',
       'source': 'Car and Driver',
       'urls': [
           'https://caranddriver.com/reviews/...',
           'https://motortrend.com/...'
       ]
   }
   ```

2. **Spider Configuration**:
   - Crawl levels: 1 (direct URL), 2 (discovered links)
   - Max discovered links: 5 per page
   - Follow patterns: review, test-drive, road-test, etc.

#### Outputs
1. **LoanItem Structure**:
   ```python
   LoanItem(
       work_order='WO12345',
       make='Honda',
       model='Accord',
       source='Car and Driver',
       url='https://...',
       content='Extracted article text...',
       title='2024 Honda Accord Review',
       publication_date='2024-01-15',
       content_type='article',  # or 'error'
       crawl_date='2024-01-20T10:30:00',
       crawl_level=1,  # 1 or 2
       error=None  # Error message if failed
   )
   ```

### Dependencies

```python
# External Libraries
import scrapy
from scrapy.http import Response, Request

# Standard Library
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Generator, Optional
from urllib.parse import urlparse

# Internal Modules
from crawler.items import LoanItem
```

### Content Discovery Strategy

#### Level 1 Crawling (Direct URLs)
1. Fetch the provided URL
2. Extract content using article selectors
3. Check if content mentions vehicle
4. If not relevant, trigger discovery

#### Level 2 Crawling (Discovery)
1. **Link Pattern Matching**:
   - Vehicle make/model in URL
   - Review keywords: "review", "test-drive", "road-test"
   - Section links: "/review/", "/blog/", "/news/"

2. **Discovery Limits**:
   - Maximum 5 links per page
   - Excludes media files
   - Deduplicates discovered URLs

### Content Extraction Hierarchy

1. **Article-Specific Selectors**:
   - `article`
   - `div.content`
   - `div.article-content`
   - `div.post-content`
   - `div.entry-content`
   - `div.main-content`
   - `.story`

2. **Fallback Strategies**:
   - All `<p>` tags
   - All text from `<body>`
   - Progressive degradation ensures some content

### Error Handling

1. **Request Failures**:
   - Logged with full error details
   - Error items created for tracking
   - Preserves loan metadata in error items

2. **Extraction Failures**:
   - Empty strings returned (not None)
   - Graceful degradation in selectors
   - No exceptions thrown to caller

3. **Discovery Failures**:
   - Silently skips bad links
   - Continues with remaining URLs
   - Logs domain extraction errors

### Performance Considerations

- **Concurrent Requests**: Controlled by Scrapy settings
- **Domain Filtering**: Dynamic allowed_domains prevents sprawl
- **Content Limits**: No explicit size limits (handled upstream)
- **Discovery Depth**: Limited to 2 levels
- **Link Limits**: Max 5 discovered links per page

### Integration Notes

This spider is typically not used directly but through:
1. **EnhancedCrawlerManager**: Orchestrates tiered escalation
2. **Scrapy Settings**: Configured for 2s delay, 1 concurrent request
3. **Item Pipeline**: Results processed by Scrapy pipelines

### Limitations

- **JavaScript Sites**: No JS rendering (Level 1 only)
- **Authentication**: No login support
- **Cookies**: Basic cookie jar only
- **Rate Limiting**: Relies on Scrapy delays
- **Content Types**: HTML only, no PDF extraction