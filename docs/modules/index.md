# DriveShop Clip Tracking - Module Documentation Index

This directory contains comprehensive documentation for all modules in the DriveShop Clip Tracking system. Each module is documented with its purpose, key functions, expected inputs/outputs, and dependencies.

## Core Application Modules

### 1. [Dashboard Module](./dashboard.md)
**Location**: `src/dashboard/app.py`  
**Purpose**: Streamlit-based web interface for reviewing and managing media clips  
**Key Features**: File upload, AgGrid tables, approval workflow, Excel export

### 2. [Ingest Modules](./ingest.md)
**Location**: `src/ingest/`  
**Purpose**: Data processing pipeline for finding and analyzing media clips  
**Components**:
- `ingest.py` - CSV-based processing
- `ingest_database.py` - Database-integrated processing with smart retry

### 3. [Analysis Module](./analysis.md)
**Location**: `src/analysis/gpt_analysis.py`  
**Purpose**: AI-powered content analysis using GPT-4  
**Key Features**: Marketing insights, sentiment analysis, cost optimization

### 4. [Crawler Module](./crawler.md)
**Location**: `src/crawler/crawler/spiders/loan_spider.py`  
**Purpose**: Scrapy spider for web content discovery  
**Key Features**: Multi-level crawling, smart discovery, content extraction

### 5. [CreatorIQ Module](./creatoriq.md)
**Location**: `src/creatoriq/`  
**Purpose**: Integration with CreatorIQ influencer platform  
**Key Features**: Multiple auth methods, GraphQL client, CSV export

## Utility Modules

### Core Utilities

#### [Core Utils](./core-utils.md)
- **Database** (`database.py`) - Supabase integration with retry logic
- **Config** (`config.py`) - Centralized configuration constants
- **Logger** (`logger.py`) - Standardized logging setup

### Web Crawling Utilities

#### [Crawler Utils](./crawler-utils.md)
- **Enhanced Crawler Manager** (`enhanced_crawler_manager.py`) - 6-tier escalation system
- **Content Extractor** (`content_extractor.py`) - Intelligent HTML extraction
- **Browser Crawler** (`browser_crawler.py`) - Playwright automation
- **Date Extractor** (`date_extractor.py`) - Publication date detection
- **Escalation** (`escalation.py`) - Domain-specific strategies

### API Integration Utilities

#### [API Utils](./api-utils.md)
- **YouTube API** (`youtube_api.py`) - YouTube Data API v3 client
- **YouTube Handler** (`youtube_handler.py`) - Multi-method YouTube extraction
- **Google Search** (`google_search.py`) - Search with Bing fallback
- **ScrapingBee** (`scraping_bee.py`) - Premium scraping service
- **ScrapFly** (`scrapfly_client.py`) - Advanced scraping with circuit breaker

### Other Utilities

#### [Other Utils](./other-utils.md)
- **Sentiment Analysis** (`sentiment_analysis.py`) - Batch GPT analysis
- **Notifications** (`notifications.py`) - Slack webhook integration
- **Rate Limiter** (`rate_limiter.py`) - Token bucket rate limiting
- **Cache Manager** (`cache_manager.py`) - SQLite caching (currently disabled)
- **Model Variations** (`model_variations.py`) - Vehicle name variations

## Module Categories by Function

### Data Flow
1. **Input**: Dashboard → Ingest
2. **Processing**: Crawler Utils → API Utils
3. **Analysis**: GPT Analysis → Sentiment Analysis
4. **Storage**: Database Utils
5. **Output**: Dashboard → Excel Export

### External Service Integration
- **AI**: OpenAI GPT-4 (Analysis module)
- **Search**: Google, Bing (Search utils)
- **Scraping**: ScrapingBee, ScrapFly (API utils)
- **Social**: YouTube, CreatorIQ (Specialized modules)
- **Notifications**: Slack (Notifications util)

### System Infrastructure
- **Caching**: Cache Manager (disabled)
- **Rate Limiting**: Token bucket implementation
- **Logging**: Centralized logger
- **Configuration**: Environment-based config
- **Database**: Supabase PostgreSQL

## Key Design Patterns

1. **Singleton Pattern**: Database manager, Cache manager
2. **Factory Pattern**: Logger setup
3. **Circuit Breaker**: ScrapFly client
4. **Token Bucket**: Rate limiter
5. **Strategy Pattern**: Tiered crawler escalation
6. **Observer Pattern**: Progress callbacks

## Integration Guidelines

### Adding New Modules
1. Follow existing module structure
2. Use centralized logger
3. Implement error handling
4. Add rate limiting for external APIs
5. Document inputs/outputs clearly

### Module Dependencies
- All modules use `logger.py`
- API modules use `rate_limiter.py`
- Crawlers use `content_extractor.py`
- Database operations use `database.py`

### Testing Modules
- Mock external services
- Use test databases
- Implement progress callbacks
- Handle async/sync patterns

## Performance Considerations

### Bottlenecks
- GPT API calls (cost + latency)
- Premium scraping services
- Database queries for large datasets

### Optimizations
- Batch processing for GPT
- Caching (when enabled)
- Concurrent processing
- Smart retry logic

## Security Considerations

- API keys in environment variables
- No hardcoded credentials
- SQL injection prevention
- XSS protection in dashboard
- Rate limiting for all external calls