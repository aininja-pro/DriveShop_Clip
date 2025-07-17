# Ingest Module Documentation

## Module: `src/ingest/ingest.py`

### Purpose

The CSV-based ingest module processes loan data from CSV/Excel files to find and analyze media clips (articles and videos) about loaned vehicles. It implements concurrent processing for efficiency and outputs results to CSV files for dashboard consumption. This module maintains a guaranteed contract for the core `process_loan()` function to ensure consistent processing.

### Key Functions/Classes

#### Data Loading Functions
```python
def load_loans_data(file_path: str) -> List[Dict]:
    """
    Loads loan data from CSV or Excel file.
    Returns: List of dictionaries containing loan information
    """

def load_loans_data_from_url(url: str) -> List[Dict]:
    """
    Loads loan data from a URL endpoint.
    Handles authentication and CSV parsing.
    Returns: List of loan dictionaries
    """
```

#### Core Processing Functions
```python
def process_loan(loan: dict) -> Optional[dict]:
    """
    PROTECTED CONTRACT: Processes a single loan to find media clips.
    Must return dictionary with specific structure or None.
    
    Contract Requirements:
    - Must handle both YouTube and web URLs
    - Must validate content dates
    - Must return only the best clip per loan
    - Must include all required fields in output
    """

async def process_loan_async(loan: dict, semaphore: asyncio.Semaphore) -> Optional[dict]:
    """
    Async wrapper for process_loan with semaphore control.
    Enables concurrent processing with rate limiting.
    """
```

#### Content Extraction Functions
```python
def process_youtube_url(url: str, model: str, journalist_name: str, 
                       start_date: datetime, end_date: datetime) -> Optional[dict]:
    """
    Extracts content from YouTube videos.
    Attempts transcript extraction, falls back to metadata.
    Applies flexible model matching for video titles.
    """

def process_web_url(url: str, model: str, journalist_name: str,
                   start_date: datetime, end_date: datetime) -> Optional[dict]:
    """
    Crawls web articles and extracts content.
    Uses multi-tier escalation strategy for difficult sites.
    """
```

#### Analysis Functions
```python
def analyze_clip(content: str, model: str, journalist_name: str, 
                source_url: str) -> dict:
    """
    Analyzes clip content using GPT-4.
    Returns relevance score, sentiment, and AI insights.
    """

def flexible_model_match(title: str, model: str) -> bool:
    """
    Intelligent matching for vehicle models in content.
    Handles variations like "X5" matching "BMW X5", "2024 X5", etc.
    """
```

#### Main Entry Points
```python
def run_ingest_concurrent(loans_data: List[dict], max_workers: int = 10) -> tuple:
    """
    Main entry point for concurrent processing.
    Returns: (successful_results, rejected_loans)
    """

def run_ingest_test(file_path: str):
    """
    Test entry point for development.
    Processes first 5 loans from a file.
    """
```

### Expected Inputs/Outputs

#### Inputs
1. **Loan Data Structure**:
   ```python
   {
       'Work Order Number': 'WO12345',
       'First Name': 'John',
       'Last Name': 'Doe',
       'Media Outlet': 'Car Magazine',
       'Model': 'BMW X5',
       'Start Date': '2024-01-15',
       'End Date': '2024-01-22',
       'URL 1': 'https://youtube.com/watch?v=...',
       'URL 2': 'https://carmagazine.com/review/...'
   }
   ```

2. **Configuration**:
   - Date range fallback: 90 days → 180 days
   - Concurrent workers: 10 (configurable)
   - Content length limits for GPT analysis

#### Outputs
1. **loan_results.csv**:
   ```csv
   Work Order Number,Model,Clip Link,AI Relevance Score,AI Insights,Sentiment Score,...
   WO12345,BMW X5,https://...,85,"Comprehensive review focusing on...",0.8,...
   ```

2. **rejected_clips.csv**:
   ```csv
   Work Order Number,First Name,Last Name,Rejection Reason
   WO12346,Jane,Smith,"No valid clips found within date range"
   ```

### Dependencies

```python
# External Libraries
import pandas as pd
import asyncio
import aiohttp
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from typing import List, Dict, Optional

# Internal Modules
from src.utils.logger import get_logger
from src.utils.youtube_handler import extract_youtube_content
from src.utils.crawler_manager import EnhancedCrawlerManager
from src.utils.date_extractor import extract_published_date
from src.analysis.gpt_analysis import analyze_content_gpt
```

### Processing Pipeline

1. **Load Data** → Parse CSV/Excel into loan dictionaries
2. **Concurrent Processing** → Process multiple loans simultaneously
3. **For Each Loan**:
   - Extract URLs from loan data
   - Process each URL based on type (YouTube/Web)
   - Validate content publication date
   - Analyze content with GPT
   - Select best clip (highest relevance)
4. **Output Results** → Save to CSV files

### Error Handling

- **Date Range Fallback**: Extends from 90 to 180 days if no content found
- **YouTube Fallback**: Transcript → Metadata only
- **Web Crawling Escalation**: Basic → Enhanced → Headless browser
- **Graceful Failures**: Logs errors and continues processing
- **Rejection Tracking**: Detailed reasons for failed loans

---

## Module: `src/ingest/ingest_database.py`

### Purpose

The database-integrated ingest module provides similar functionality to the CSV version but stores results directly in Supabase. It implements smart retry logic to avoid reprocessing recent attempts and defers full GPT analysis to save costs. This module is designed for production use with real-time dashboard integration.

### Key Functions/Classes

#### Database Processing Functions
```python
def process_loan_for_database(loan: dict, db: DatabaseManager, 
                            outlets_mapping: dict, run_id: str) -> tuple:
    """
    Processes a loan and stores results in database.
    Returns: (success_count, failure_count)
    """

async def process_loan_database_async(loan: dict, db: DatabaseManager,
                                    outlets_mapping: dict, run_id: str,
                                    semaphore: asyncio.Semaphore,
                                    progress_callback=None) -> tuple:
    """
    Async version with progress callback support.
    Enables real-time UI updates during processing.
    """
```

#### Validation Functions
```python
def is_url_from_authorized_outlet(url: str, journalist_name: str, 
                                 outlets_mapping: dict) -> bool:
    """
    Validates if URL belongs to journalist's authorized outlets.
    Prevents processing unauthorized media sources.
    """

def load_person_outlets_mapping() -> dict:
    """
    Loads person-to-outlet authorization mapping.
    Returns: Dict mapping person names to authorized outlets
    """
```

#### Scoring Functions
```python
def calculate_relevance_score(content: str, model: str, 
                            use_gpt: bool = False) -> float:
    """
    Calculates content relevance score.
    Can use GPT or fallback to keyword matching.
    """
```

#### Main Entry Points
```python
def run_ingest_database(data_source: str):
    """
    Main entry point for database ingestion.
    Processes loans from file or URL.
    """

def run_ingest_database_with_filters(loans_data: List[dict], 
                                   progress_callback=None) -> dict:
    """
    Processes pre-filtered loans from dashboard.
    Supports real-time progress updates.
    Returns: Processing statistics
    """
```

### Expected Inputs/Outputs

#### Inputs
- Same loan data structure as CSV version
- **Additional Requirements**:
  - Person-to-outlet mapping JSON
  - Database connection credentials
  - Processing run ID for tracking

#### Outputs
1. **Database Records** (clips table):
   ```sql
   INSERT INTO clips (
       wo_number, first_name, last_name, media_outlet,
       model, start_date, end_date, url, content,
       published_date, relevance_score, sentiment,
       ai_insights, status, run_id, created_at
   )
   ```

2. **Failed Attempts** (clips table with status='failed'):
   - Stored with rejection reasons
   - Used for smart retry logic

3. **Processing Run Statistics**:
   ```python
   {
       'processed': 50,
       'successful': 45,
       'failed': 5,
       'duration': 120.5
   }
   ```

### Dependencies

```python
# Database Integration
from src.utils.database import DatabaseManager

# Reused from CSV Version
from src.ingest.ingest import (
    process_youtube_url,
    process_web_url,
    flexible_model_match,
    is_content_within_date_range
)

# Additional Utilities
from src.utils.content_extractor import ContentExtractor
from src.utils.sentiment_analysis import calculate_relevance_score_gpt
```

### Smart Retry Logic

1. **Check Recent Attempts**: Skip if processed in last 24 hours
2. **Track Failed URLs**: Store failure reasons in database
3. **Homepage Detection**: Filter out index/homepage URLs
4. **Outlet Authorization**: Only process authorized outlets

### Database Schema Integration

```sql
-- Processing Runs Table
CREATE TABLE processing_runs (
    id UUID PRIMARY KEY,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_loans INTEGER,
    successful_clips INTEGER,
    failed_clips INTEGER
);

-- Clips Table
CREATE TABLE clips (
    id SERIAL PRIMARY KEY,
    wo_number VARCHAR,
    url VARCHAR,
    content TEXT,
    relevance_score FLOAT,
    status VARCHAR, -- 'pending', 'approved', 'rejected', 'failed'
    run_id UUID REFERENCES processing_runs(id),
    rejection_reason TEXT,
    created_at TIMESTAMP
);
```

### Performance Optimizations

- **Concurrent Processing**: Default 5 workers (configurable)
- **Smart Retry**: Avoids redundant API calls
- **Deferred Analysis**: Only relevance scoring, full GPT on demand
- **Batch Operations**: Efficient database inserts
- **Progress Callbacks**: Real-time UI updates without polling

### Error Handling

- **Database Failures**: Automatic reconnection with exponential backoff
- **Duplicate Detection**: Checks existing clips before processing
- **Transaction Safety**: Rollback on errors
- **Comprehensive Logging**: All failures tracked in database
- **Graceful Degradation**: Continues processing on individual failures