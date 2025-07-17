# Other Utilities Documentation

## Module: `src/utils/sentiment_analysis.py`

### Purpose

The Sentiment Analysis module provides a high-level interface for analyzing automotive media clips using GPT-4. It wraps the core analysis functionality with batch processing capabilities, progress tracking, and both synchronous and asynchronous execution patterns for UI integration.

### Key Functions/Classes

#### SentimentAnalyzer Class
```python
class SentimentAnalyzer:
    """
    High-level sentiment analysis for automotive clips.
    Supports batch processing with progress tracking.
    """
    
    def __init__(self):
        """Initialize analyzer (placeholder for future config)."""
```

#### Core Methods
```python
async def analyze_clip_sentiment(self, clip_data: Dict) -> Dict:
    """
    Analyze single clip asynchronously.
    Returns comprehensive sentiment analysis.
    """

def analyze_clips_sync(self, clips: List[Dict], 
                      progress_callback=None) -> List[Dict]:
    """
    Synchronous batch analysis with progress updates.
    Processes in batches of 5 to respect rate limits.
    """

async def analyze_clips_batch(self, clips: List[Dict],
                            batch_size: int = 5) -> List[Dict]:
    """
    Asynchronous batch processing.
    Implements concurrent processing with rate limiting.
    """
```

#### Utility Functions
```python
def run_sentiment_analysis(clips: List[Dict], 
                          progress_callback=None) -> List[Dict]:
    """
    Main entry point for sentiment analysis.
    Handles async loop creation for sync callers.
    """

def calculate_relevance_score_gpt(content: str, make: str, 
                                model: str) -> float:
    """
    Calculate relevance score using GPT.
    Cost-optimized version for database pipeline.
    """
```

### Expected Inputs/Outputs

#### Inputs
```python
# Single clip
{
    'content': 'Article or transcript text...',
    'url': 'https://example.com/review',
    'make': 'Honda',
    'model': 'Accord'
}

# Batch processing
clips = [clip1, clip2, clip3, ...]
progress_callback = lambda current, total: print(f"{current}/{total}")
```

#### Outputs
```python
{
    'relevance_score': 85,
    'overall_score': 8,
    'overall_sentiment': 'positive',
    'brand_alignment': True,
    'summary': 'Comprehensive review highlighting...',
    'aspects': {
        'performance': {'score': 9, 'note': 'Excellent acceleration'},
        'design': {'score': 7, 'note': 'Conservative but elegant'},
        # ... other aspects
    },
    'pros': ['Fuel efficiency', 'Reliability', 'Tech features'],
    'cons': ['Road noise', 'Firm suspension'],
    'recommendation': 'Strong buy for family sedan buyers'
}
```

### Dependencies

```python
import asyncio
from typing import List, Dict, Optional, Callable

from src.analysis.gpt_analysis import analyze_clip
from src.utils.logger import setup_logger
```

### Processing Features

1. **Batch Size Management**: Processes 5 clips at a time to avoid rate limits
2. **Progress Tracking**: Real-time updates for UI progress bars
3. **Error Resilience**: Continues processing even if individual clips fail
4. **Async/Sync Bridge**: Handles async operations for sync callers
5. **Delay Management**: 1-second delay between batches

---

## Module: `src/utils/notifications.py`

### Purpose

The Notifications module provides Slack webhook integration for sending real-time alerts and status updates. It implements retry logic with exponential backoff and supports formatted messages for better visibility in Slack channels.

### Key Functions/Classes

#### Core Function
```python
def send_slack_message(message: str, webhook_url: str = None, 
                      max_retries: int = 3) -> bool:
    """
    Send notification to Slack channel.
    Implements retry with exponential backoff.
    """
```

### Message Formatting

1. **Status Prefixes**:
   - `"approved"` → ✅ prefix
   - `"rejected"` → ❌ prefix
   - Others → no prefix

2. **Block Format**:
   ```json
   {
       "blocks": [{
           "type": "section",
           "text": {
               "type": "mrkdwn",
               "text": "✅ Clip approved for Honda Accord"
           }
       }]
   }
   ```

### Expected Inputs/Outputs

#### Inputs
```python
# Simple message
send_slack_message("Processing completed")

# Status message
send_slack_message("Clip approved for Honda Accord")

# Custom webhook
send_slack_message("Alert!", webhook_url="https://hooks.slack.com/...")
```

#### Outputs
- `True`: Message sent successfully
- `False`: Failed after all retries

### Dependencies

```python
import os
import json
import time
import requests
from src.utils.logger import setup_logger
```

### Configuration

```bash
# Environment variable
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
```

### Error Handling

1. **Retry Strategy**: 3 attempts with exponential backoff (1s, 2s, 4s)
2. **HTTP Errors**: Catches and logs all request exceptions
3. **Missing Webhook**: Returns False with warning log
4. **Non-blocking**: Never raises exceptions to caller

---

## Module: `src/utils/rate_limiter.py`

### Purpose

The Rate Limiter implements a token bucket algorithm to enforce rate limits on external API calls. It provides per-domain rate limiting with automatic domain detection and thread-safe operation for concurrent requests.

### Key Functions/Classes

#### RateLimiter Class
```python
class RateLimiter:
    """
    Token bucket rate limiter with per-domain limits.
    Thread-safe implementation for concurrent access.
    """
    
    def __init__(self):
        """Initialize with default rate configurations."""
```

#### Core Methods
```python
def wait_if_needed(self, url_or_domain: str, 
                  custom_rate: float = None,
                  custom_per: float = None):
    """
    Wait if rate limit would be exceeded.
    Automatically detects and normalizes domains.
    """

def _ensure_bucket_exists(self, domain: str, rate: float, per: float):
    """
    Create token bucket for new domain.
    Initializes with full token capacity.
    """

def _refill_bucket(self, domain: str):
    """
    Refill tokens based on elapsed time.
    Implements token bucket algorithm.
    """
```

### Default Rate Limits

```python
default_rates = {
    'openai.com': (5, 60),      # 5 requests per minute
    'youtube.com': (10, 60),    # 10 requests per minute
    'googleapis.com': (10, 60), # 10 requests per minute
    # Unknown domains: 1 request per 2 seconds
}
```

### Expected Inputs/Outputs

#### Inputs
```python
# URL-based (auto-detects domain)
rate_limiter.wait_if_needed("https://api.openai.com/v1/completions")

# Domain-based
rate_limiter.wait_if_needed("openai.com")

# Custom rate
rate_limiter.wait_if_needed("custom-api.com", custom_rate=100, custom_per=60)
```

#### Outputs
- No return value
- Blocks (sleeps) if rate limit would be exceeded
- Logs wait times when blocking

### Dependencies

```python
import time
import threading
from urllib.parse import urlparse
from src.utils.logger import setup_logger
```

### Token Bucket Algorithm

1. **Bucket Capacity**: Equal to rate limit (e.g., 5 tokens)
2. **Refill Rate**: Based on configured rate/period
3. **Token Consumption**: 1 token per request
4. **Blocking**: Waits for next token if bucket empty
5. **Thread Safety**: Uses locks for concurrent access

---

## Module: `src/utils/cache_manager.py`

### Purpose

The Cache Manager provides SQLite-based caching for web scraping results with automatic expiration. **IMPORTANT: Caching is currently DISABLED** - the `get_cached_result` method always returns None to ensure fresh data retrieval.

### Key Functions/Classes

#### CacheManager Class
```python
class CacheManager:
    """
    SQLite-based cache for scraping results.
    Currently DISABLED - always returns cache miss.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize SQLite database with schema."""
```

#### Core Methods
```python
def get_cached_result(self, person_id: str, domain: str,
                     make: str, model: str) -> Optional[Dict]:
    """
    Check for cached result. 
    CURRENTLY DISABLED - always returns None.
    """

def store_result(self, person_id: str, domain: str, make: str,
                model: str, url: str, content: str,
                metadata: Dict = None) -> bool:
    """
    Store scraping result with 24-hour TTL.
    Still functional for future use.
    """

def cleanup_expired(self) -> int:
    """
    Remove expired cache entries.
    Returns count of deleted entries.
    """

def get_cache_stats(self) -> Dict:
    """
    Get cache statistics.
    Returns entry counts and sizes.
    """
```

### Database Schema

```sql
CREATE TABLE scraping_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    url TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,  -- JSON string
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    UNIQUE(person_id, domain, make, model)
);

-- Indexes for performance
CREATE INDEX idx_cache_lookup ON scraping_cache(person_id, domain, make, model);
CREATE INDEX idx_cache_expiry ON scraping_cache(expires_at);
```

### Configuration

- **Database Path**: `data/scraping_cache.db`
- **TTL**: 24 hours (86,400 seconds)
- **Cache Status**: DISABLED for reliability

### Dependencies

```python
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from src.utils.logger import setup_logger
```

---

## Module: `src/utils/model_variations.py`

### Purpose

The Model Variations module generates multiple formatting variations of vehicle model names to improve search coverage across different automotive websites. It handles common patterns like hyphenation, spacing, and make-model combinations.

### Key Functions/Classes

#### Core Function
```python
def generate_model_variations(make: str, model: str) -> List[str]:
    """
    Generate model name variations for better search coverage.
    Handles spacing, hyphenation, and make combinations.
    """
```

### Variation Strategies

1. **Space/Hyphen Variations**:
   - "CX-90" → ["cx-90", "cx 90", "cx90"]
   - Handles both directions: with/without spaces/hyphens

2. **Make Prefix Combinations**:
   - Adds make name: "accord" → "honda accord"
   - Both spaced and unspaced versions

3. **Numeric Patterns**:
   - "3 Series" ↔ "3series"
   - "ES 350" ↔ "ES350"

4. **Abbreviation Handling**:
   - Very limited due to ambiguity concerns
   - Only complete word matches

### Expected Inputs/Outputs

#### Inputs
```python
generate_model_variations("Mazda", "CX-90")
```

#### Outputs
```python
[
    "cx-90",
    "cx 90", 
    "cx90",
    "mazda cx-90",
    "mazda cx 90",
    "mazda cx90",
    "mazdacx-90",
    "mazdacx 90",
    "mazdacx90"
]
```

### Dependencies

```python
import re
from typing import List
```

### Variation Examples

| Make | Model | Key Variations |
|------|-------|----------------|
| Lexus | ES 350 | es350, lexus es 350 |
| BMW | 3 Series | 3series, bmw 3 series |
| Honda | CR-V | cr-v, crv, cr v, honda crv |
| Tesla | Model 3 | model3, tesla model 3 |

### Design Decisions

1. **Conservative Approach**: Avoids aggressive abbreviations
2. **Case Insensitive**: All variations in lowercase
3. **De-duplication**: Uses sets to prevent duplicates
4. **Performance**: Pre-compiled regex patterns