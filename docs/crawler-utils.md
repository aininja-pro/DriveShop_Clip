# Crawler Utilities Documentation

## Module: `src/utils/enhanced_crawler_manager.py`

### Purpose

The Enhanced Crawler Manager implements a sophisticated 6+ tier escalation system for web content extraction. It provides intelligent content quality detection, caching, index page discovery, and seamless integration with multiple scraping services. This is the primary crawler orchestrator used in production.

### Key Functions/Classes

#### EnhancedCrawlerManager Class
```python
class EnhancedCrawlerManager:
    """
    Advanced web content extraction with multi-tier escalation.
    Features caching, quality checks, and intelligent routing.
    """
    
    def __init__(self):
        """Initialize with cache manager and API clients."""
```

#### Core Methods
```python
def extract_content(self, url: str, expected_make: str = None, 
                   expected_model: str = None, journalist_name: str = None,
                   publication_date: str = None, max_tier: int = 7) -> Dict:
    """
    Main extraction method with progressive escalation.
    Returns: {content, source, tier_used, byline_author, attribution_strength}
    """

def is_content_high_quality(self, content: str, url: str,
                           expected_make: str = None, 
                           expected_model: str = None) -> bool:
    """
    Validates content quality using multiple heuristics.
    Detects index pages and validates relevance.
    """
```

#### Tier Implementation Methods
```python
def try_tier_1_basic_http(self, url: str) -> Optional[str]:
    """Basic HTTP request with minimal headers."""

def try_tier_2_enhanced_http(self, url: str) -> Optional[str]:
    """Enhanced HTTP with browser-like headers and cookies."""

def try_tier_3_rss_feed(self, url: str, expected_make: str, 
                       expected_model: str) -> Optional[str]:
    """Extract content via RSS feed if available."""

def try_tier_4_scrapfly(self, url: str) -> Optional[str]:
    """Premium scraping via ScrapFly API."""

def try_tier_5_5_index_page_discovery(self, url: str, expected_make: str,
                                     expected_model: str) -> Optional[str]:
    """Discover article from index page."""

def try_tier_6_google_search(self, url: str, expected_make: str,
                            expected_model: str, journalist_name: str) -> Optional[str]:
    """Find article via Google Search."""
```

### Tiered Escalation Strategy

1. **Tier 1 - Basic HTTP** (0.5-1s)
   - Simple requests with standard headers
   - Fastest, works for ~40% of sites

2. **Tier 2 - Enhanced HTTP** (1-2s)
   - Browser-like headers and session management
   - Content quality validation
   - Works for ~60% of sites

3. **Tier 3 - RSS Feed** (1-2s)
   - Structured data extraction
   - Free and reliable when available
   - ~10% of sites support RSS

4. **Tier 4 - ScrapFly API** (2-5s)
   - Premium residential proxies
   - Handles anti-bot protection
   - 99.9% success rate

5. **Tier 5.5 - Index Discovery** (5-10s)
   - Crawls category/index pages
   - Finds specific article links
   - Similar to YouTube processing

6. **Tier 6 - Google Search** (3-5s)
   - Searches for specific article
   - Uses journalist + make/model
   - Fallback discovery method

7. **Tier 7 - Playwright** (10-20s)
   - Full browser automation
   - Last resort option
   - Handles complex JS sites

### Expected Inputs/Outputs

#### Inputs
```python
{
    'url': 'https://example.com/article',
    'expected_make': 'Honda',
    'expected_model': 'Accord',
    'journalist_name': 'John Doe',
    'publication_date': '2024-01-15',
    'max_tier': 7  # Stop at this tier
}
```

#### Outputs
```python
{
    'content': 'Extracted article text...',
    'source': 'tier_2_enhanced_http',
    'tier_used': 2,
    'byline_author': 'John Doe',
    'attribution_strength': 'strong',
    'cached': False,
    'extraction_time': 1.5
}
```

### Dependencies

```python
# External
import requests
from bs4 import BeautifulSoup
import feedparser

# Internal  
from src.utils.cache_manager import CacheManager
from src.utils.content_extractor import ContentExtractor
from src.utils.scrapfly_client import ScrapFlyClient
from src.utils.google_search import search_google
from src.utils.browser_crawler import BrowserCrawler
```

---

## Module: `src/utils/content_extractor.py`

### Purpose

The Content Extractor provides intelligent HTML content extraction with site-specific handlers and multiple fallback strategies. It focuses on extracting clean, relevant article text while filtering out navigation, ads, and other non-content elements.

### Key Functions/Classes

#### ContentExtractor Class
```python
class ContentExtractor:
    """
    Intelligent content extraction from HTML.
    Implements site-specific and generic extraction methods.
    """
```

#### Core Methods
```python
def extract_article_content(html_content: str, url: str = None,
                          expected_topic: str = None,
                          extraction_type: str = "default") -> Optional[str]:
    """
    Main extraction method with multiple strategies.
    Handles site-specific extractors and fallbacks.
    """

def extract_basic_content(soup: BeautifulSoup) -> str:
    """
    Generic content extraction using common selectors.
    Tries multiple article body indicators.
    """

def extract_alternative_methods(soup: BeautifulSoup, url: str,
                              expected_topic: str) -> Optional[str]:
    """
    Alternative extraction when basic method fails.
    Includes title-based, density-based, and full-text methods.
    """
```

#### Site-Specific Handlers
```python
def extract_fliphtml5_content(soup: BeautifulSoup) -> Optional[str]:
    """Extract from FlipHTML5 embedded viewers."""

def extract_spotlightepnews_content(soup: BeautifulSoup) -> Optional[str]:
    """Handle PDF viewers and flipbook format."""

def extract_thegentlemanracer_content(soup: BeautifulSoup) -> Optional[str]:
    """Remove sidebar content and extract main article."""
```

### Content Extraction Strategies

1. **Site-Specific Extraction**
   - Custom handlers for known problematic sites
   - Handles embedded viewers, PDFs, flipbooks

2. **Basic Extraction**
   - Common article selectors (article, .content, etc.)
   - Paragraph concatenation
   - Clean text output

3. **Alternative Methods**
   - Title-based discovery
   - Paragraph density analysis  
   - Longest text block
   - Full text with filtering

4. **Content Quality Scoring**
   - Paragraph count and structure
   - Text length validation
   - Navigation element detection
   - Article indicator presence

### Expected Inputs/Outputs

#### Inputs
```python
{
    'html_content': '<html>...</html>',
    'url': 'https://example.com/article',
    'expected_topic': 'Honda Accord',
    'extraction_type': 'default'  # or 'basic', 'alternative'
}
```

#### Outputs
- Clean article text (string)
- None if extraction fails
- Filtered content without navigation/ads

---

## Module: `src/utils/browser_crawler.py`

### Purpose

The Browser Crawler provides thread-safe headless browser automation using Playwright. It implements anti-detection measures and handles JavaScript-heavy sites that require full browser rendering.

### Key Functions/Classes

#### BrowserCrawler Class
```python
class BrowserCrawler:
    """
    Thread-safe Playwright browser automation.
    Creates fresh browser instance per crawl.
    """
    
    def crawl(self, url: str, wait_for: str = "networkidle",
             wait_time: int = 5, scroll: bool = True) -> str:
        """
        Crawl URL with headless browser.
        Returns page HTML after rendering.
        """
```

#### MockBrowserCrawler Class
```python
class MockBrowserCrawler:
    """
    Mock implementation for testing.
    Returns simple HTML without browser overhead.
    """
```

### Browser Configuration

1. **Stealth Features**
   - Hides webdriver properties
   - Randomized viewport sizes
   - Realistic user agent strings

2. **Navigation Strategies**
   - `networkidle`: Wait for network quiet
   - `domcontentloaded`: Wait for DOM ready
   - `load`: Wait for page load event

3. **Resource Management**
   - Fresh browser per crawl
   - Automatic cleanup
   - Thread-safe operation

### Expected Inputs/Outputs

#### Inputs
```python
{
    'url': 'https://example.com',
    'wait_for': 'networkidle',
    'wait_time': 5,
    'scroll': True
}
```

#### Outputs
- Rendered HTML content (string)
- Empty string on failure

---

## Module: `src/utils/date_extractor.py`

### Purpose

The Date Extractor provides comprehensive publication date extraction from web content using multiple methods including structured data, meta tags, CSS selectors, and text patterns.

### Key Functions/Classes

#### Core Functions
```python
def extract_published_date(html_content: str, url: str = None) -> Optional[str]:
    """
    Extract publication date using multiple strategies.
    Returns ISO format date string or None.
    """

def extract_date_from_structured_data(soup: BeautifulSoup) -> Optional[str]:
    """Extract from JSON-LD, microdata schemas."""

def extract_date_from_meta_tags(soup: BeautifulSoup) -> Optional[str]:
    """Extract from Open Graph, Dublin Core meta tags."""

def extract_date_from_selectors(soup: BeautifulSoup) -> Optional[str]:
    """Extract using common CSS date selectors."""

def extract_date_from_text_patterns(text: str) -> Optional[str]:
    """Extract using regex patterns for date formats."""
```

### Extraction Methods Hierarchy

1. **Structured Data** (Most reliable)
   - JSON-LD schemas
   - Microdata markup
   - Schema.org properties

2. **Meta Tags**
   - Open Graph (og:published_time)
   - Dublin Core (DC.date)
   - Article metadata

3. **CSS Selectors**
   - Common date classes (.date, .publish-date)
   - Time elements
   - Site-specific patterns

4. **Text Patterns** (Fallback)
   - Regex for various date formats
   - Natural language parsing
   - Sanity validation

### Expected Inputs/Outputs

#### Inputs
```python
{
    'html_content': '<html>...</html>',
    'url': 'https://example.com/article'
}
```

#### Outputs
- ISO format date string: "2024-01-15"
- None if no valid date found

---

## Module: `src/utils/escalation.py`

### Purpose

The Escalation module manages domain-specific crawling strategies, determining the appropriate starting tier and escalation path based on site characteristics and configuration.

### Key Functions/Classes

#### Core Functions
```python
def load_media_sources() -> pd.DataFrame:
    """
    Load media source configuration from CSV.
    Contains domain-specific crawl strategies.
    """

def get_domain_crawl_level(domain: str, media_sources_df: pd.DataFrame) -> int:
    """
    Determine starting crawl level for domain.
    Based on js_mode and other indicators.
    """

def requires_js_rendering(domain: str) -> bool:
    """
    Check if domain requires JavaScript rendering.
    Uses configuration and heuristics.
    """
```

### Configuration Management

1. **Media Sources CSV**
   ```csv
   domain,js_mode,start_tier
   example.com,true,4
   simple.com,false,1
   ```

2. **Domain Classification**
   - JavaScript-heavy sites
   - Simple HTML sites
   - API-required sites
   - Premium proxy sites

3. **Escalation Rules**
   - Start tier selection
   - Max tier limits
   - Skip tier options

### Expected Inputs/Outputs

#### Inputs
- Domain name (string)
- Media sources configuration

#### Outputs
- Starting crawl level (integer)
- JavaScript requirement (boolean)
- Escalation strategy parameters

### Integration with Crawler Manager

The escalation module provides the intelligence for:
- Selecting optimal starting tier
- Avoiding unnecessary escalation
- Domain-specific optimizations
- Performance tuning per site