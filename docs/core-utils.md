# Core Utilities Documentation

## Module: `src/utils/database.py`

### Purpose

The Database module provides a comprehensive interface to the Supabase PostgreSQL database, managing all data persistence for the clip tracking system. It implements intelligent retry logic, workflow management, and provides analytics capabilities while maintaining a singleton pattern for efficient connection management.

### Key Functions/Classes

#### Data Classes
```python
@dataclass
class ProcessingRun:
    """
    Tracks batch processing metadata.
    Attributes: id, started_at, completed_at, total_loans, 
                successful_clips, failed_clips
    """

@dataclass  
class ClipData:
    """
    Comprehensive clip data model.
    Includes: loan info, content, sentiment analysis, workflow status,
              UI display data, media outlet mapping
    """
```

#### DatabaseManager Class
```python
class DatabaseManager:
    """
    Singleton database manager for all Supabase operations.
    Groups operations by functionality: runs, clips, retry logic, analytics.
    """
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize Supabase client with credentials."""
```

#### Core Operations

##### Processing Runs
```python
def create_processing_run(self) -> str:
    """Create new processing run, returns UUID."""

def update_processing_run(self, run_id: str, total_loans: int, 
                         successful: int, failed: int):
    """Update run statistics upon completion."""
```

##### Clip Management
```python
def store_clip(self, clip_data: ClipData) -> bool:
    """Store found clip with all metadata."""

def get_pending_clips(self, filters: Dict = None) -> List[Dict]:
    """Retrieve clips awaiting review with optional filters."""

def update_clip_status(self, wo_number: str, status: str) -> bool:
    """Update clip workflow status (pending/approved/rejected)."""

def update_clip_sentiment(self, wo_number: str, sentiment_data: Dict) -> bool:
    """Store comprehensive GPT sentiment analysis."""
```

##### Smart Retry Logic
```python
def store_failed_attempt(self, loan_data: Dict, reason: str, 
                        run_id: str) -> bool:
    """Record failed search attempt with retry scheduling."""

def should_retry_wo(self, wo_number: str) -> Tuple[bool, Optional[str]]:
    """
    Intelligent retry decision based on:
    - Failure type and count
    - Time since last attempt
    - Configured retry intervals
    """

def get_smart_retry_summary(self) -> Dict:
    """Analytics on retry patterns and success rates."""
```

### Expected Inputs/Outputs

#### Inputs
1. **Environment Configuration**:
   ```bash
   SUPABASE_URL=https://xxx.supabase.co
   SUPABASE_ANON_KEY=eyJhbGc...
   ```

2. **Clip Data Structure**:
   ```python
   ClipData(
       wo_number="WO12345",
       model="Honda Accord",
       clip_url="https://...",
       content="Article text...",
       relevance_score=85,
       sentiment_data={...},
       status="pending",
       run_id="uuid-123",
       media_outlet="Car and Driver"
   )
   ```

#### Outputs
1. **Database Records**: Direct storage to Supabase tables
2. **Query Results**: Lists of dictionaries with clip data
3. **Analytics**: Aggregated statistics and summaries
4. **Retry Decisions**: Tuple of (should_retry: bool, reason: str)

### Dependencies

```python
# External
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, timedelta

# Internal
from src.utils.logger import logger
```

### Retry Strategy

#### Retry Intervals by Failure Type
- **No Content Found**: 7 days
- **Technical Issues**: 1 day  
- **Timeout**: 2 days
- **Access Denied**: 14 days
- **Default**: 3 days

#### Retry Decision Logic
1. Check last attempt timestamp
2. Apply interval based on failure reason
3. Consider failure count (max retries)
4. Return decision with explanation

### Error Handling

- All operations wrapped in try-except
- Detailed error logging with context
- Graceful degradation (returns empty/False)
- Connection testing available
- No exceptions propagated to caller

---

## Module: `src/utils/config.py`

### Purpose

The Config module centralizes all configuration constants for the web crawling system, including domain-specific strategies, content discovery patterns, and API configurations. It provides a single source of truth for all scraping-related settings.

### Key Configuration Sections

#### Domain Management
```python
API_SCRAPER_DOMAINS = [
    'motortrend.com',
    'caranddriver.com',
    'autoblog.com',
    # ... domains requiring API scraping
]

GENERIC_INDEX_PATTERNS = [
    r'/category/',
    r'/tag/',
    r'/page/\d+',
    # ... patterns indicating index pages
]
```

#### Content Discovery
```python
ARTICLE_INDICATORS = ['review', 'test', 'drive', 'first-look']

MODEL_CLEANUP_PATTERNS = {
    r'\s+hybrid$': '',
    r'\s+phev$': '',
    r'^20\d{2}\s+': '',
    # ... model name normalization
}

SEARCH_QUERY_TEMPLATES = [
    '"{journalist}" {make} {model} review',
    'site:{domain} {make} {model}',
    # ... search query formats
]
```

#### API Configurations
```python
SCRAPINGBEE_CONFIG = {
    'render_js': True,
    'premium_proxy': True,
    'country_code': 'us',
    'timeout': 30000
}

GOOGLE_SEARCH_CONFIG = {
    'max_results': 10,
    'safe_search': 'off',
    'search_type': 'web'
}

CACHE_CONFIG = {
    'enabled': True,
    'ttl_hours': 168,  # 7 days
    'max_size_mb': 500
}
```

#### Crawler Configuration
```python
CRAWLER_TIERS = {
    'tier1': {'delay': 1, 'timeout': 30},
    'tier2': {'delay': 2, 'timeout': 45},
    'tier3': {'delay': 3, 'timeout': 60},
    'tier4': {'premium_proxy': True},
    'tier5': {'js_scenario': True},
    'tier6': {'stealth_mode': True}
}

USER_AGENTS = {
    'chrome': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...',
    'firefox': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15)...',
    'mobile': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1)...'
}
```

### Expected Inputs/Outputs

#### Inputs
- No inputs (pure configuration module)
- Values are hardcoded constants

#### Outputs
- Configuration dictionaries and lists
- Used via imports: `from src.utils.config import API_SCRAPER_DOMAINS`

### Dependencies

None (pure Python module)

### Usage Patterns

```python
from src.utils.config import CRAWLER_TIERS, SCRAPINGBEE_CONFIG

# Use tier configuration
tier_config = CRAWLER_TIERS['tier3']
delay = tier_config['delay']

# Use API configuration
api_params = SCRAPINGBEE_CONFIG.copy()
api_params['url'] = target_url
```

---

## Module: `src/utils/logger.py`

### Purpose

The Logger module provides standardized logging configuration across the entire application. It ensures consistent log formatting, creates necessary directory structures, and provides both console and file output for debugging and monitoring.

### Key Functions/Classes

#### Setup Function
```python
def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """
    Create a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
```

#### Default Logger Instance
```python
# Pre-configured logger for immediate use
logger = setup_logger('clip_tracking')
```

### Expected Inputs/Outputs

#### Inputs
1. **Logger Name**: Module name or custom identifier
2. **Log Level**: `logging.DEBUG`, `logging.INFO`, `logging.WARNING`, etc.

#### Outputs
1. **Console Output**: Formatted log messages to stdout
2. **File Output**: Logs written to `logs/app.log`
3. **Logger Instance**: Configured Python logger object

### Dependencies

```python
import logging
import os
from pathlib import Path
```

### Configuration Details

#### Log Format
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

Example output:
```
2024-01-20 10:30:45 - clip_tracking - INFO - Processing started
2024-01-20 10:30:46 - database - ERROR - Connection failed: timeout
```

#### File Structure
```
project_root/
├── logs/
│   └── app.log
└── src/
    └── utils/
        └── logger.py
```

### Usage Patterns

#### Module-Specific Logger
```python
from src.utils.logger import setup_logger

# Create module-specific logger
logger = setup_logger(__name__)

# Use in module
logger.info("Starting processing")
logger.error(f"Failed to process: {error}")
logger.debug(f"Debug info: {data}")
```

#### Direct Import
```python
from src.utils.logger import logger

# Use pre-configured logger
logger.info("Quick logging without setup")
```

### Error Handling

- Creates log directory if missing
- Prevents duplicate handlers
- Handles file permission issues gracefully
- Falls back to console only if file logging fails

### Performance Considerations

- Single file handler shared across loggers
- Automatic log rotation not implemented (consider for production)
- No async logging (synchronous writes)
- Log level filtering at handler level