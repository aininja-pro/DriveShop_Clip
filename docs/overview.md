# DriveShop Clip Tracking System

## Project Purpose

The DriveShop Clip Tracking System is a comprehensive media monitoring and analysis platform designed to track automotive journalist coverage of vehicle loans for DriveShop's Fleet Management System (FMS). It automates the discovery, analysis, and tracking of media content across web platforms and YouTube, providing a streamlined workflow for campaign managers to review and approve clips. The system is engineered to process approximately 60 loans daily, finding the first media mention for each loan within a 2-hour nightly processing window, ensuring comprehensive coverage tracking for automotive PR campaigns while maintaining cost-effective AI usage.

## Key Features

- **Automated Media Discovery**: Multi-tier web scraping system with intelligent escalation (Scrapy → Enhanced Headers → Headless Rendering)
- **Smart Discovery Mode**: Automatic navigation through "reviews", "blog", or "news" sections for unknown media sites
- **YouTube Integration**: Specialized handling including RSS feed monitoring and transcript extraction
- **AI-Powered Analysis**: GPT-4 integration for content relevance scoring, sentiment analysis, and brand message alignment
- **One Clip Per Loan**: Intelligent deduplication to find only the first media mention
- **Person-Outlet Mapping**: Automatic association of journalists with their media outlets
- **Streamlit Dashboard**: Password-protected web interface for reviewing and approving clips
- **FMS Integration**: Export functionality with `approved_clips.csv` formatted for DriveShop's system
- **RSS Optimization**: Direct RSS feed support for faster processing when available
- **Slack Notifications**: Real-time alerts for approvals, flags, and system status
- **Cost-Optimized**: Designed to maintain ~$1-3 daily AI costs with efficient caching

## Architecture Overview

The system follows a modular architecture optimized for reliability and cost-effectiveness:

### Core Components

1. **Data Ingestion Pipeline** (`src/ingest/`)
   - Processes daily loan files from FMS
   - Implements smart URL discovery for unknown media outlets
   - Manages one-clip-per-loan logic

2. **Tiered Web Crawling Framework** (`src/crawler/`, `src/utils/`)
   - **Level 1**: Basic Scrapy with 2s delay, 1 concurrent request
   - **Level 2**: Enhanced headers and cookie management
   - **Level 3**: Headless browser rendering for JavaScript-heavy sites
   - RSS feed shortcuts for supported outlets

3. **AI Analysis Module** (`src/analysis/`)
   - OpenAI GPT-4 Turbo for cost-effective analysis
   - Evaluates relevance, sentiment, and brand message alignment
   - ~$0.01-$0.03 per analysis call

4. **Dashboard Application** (`src/dashboard/`)
   - Streamlit-based interface (no custom theming in MVP)
   - AgGrid for efficient data manipulation
   - Password authentication (single shared password)

5. **Data Storage Layer**
   - Supabase (PostgreSQL) for persistent storage
   - Local SQLite cache for scraping results
   - CSV export for FMS integration

### Data Flow

1. **Input**: Daily loan CSV from FMS or manual upload
2. **Discovery**: Automated search with smart navigation for unknown sites
3. **Processing**: Content extraction with tiered escalation
4. **Analysis**: GPT-4 evaluates content (first mention only)
5. **Review**: Manual approval via Streamlit dashboard
6. **Output**: `approved_clips.csv` for FMS import

## Setup Instructions

### Prerequisites

- Python 3.11.4 (specific version required)
- Docker and Docker Compose
- AWS EC2 t3.small instance (for production)
- API keys for required services

### Environment Variables

Create a `.env` file based on `.env.template`:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Supabase Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
DATABASE_PASSWORD=your_database_password

# Google Search API
GOOGLE_API_KEY=your_google_api_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id

# Web Scraping Services
SCRAPING_BEE_API_KEY=your_scraping_bee_key
SCRAPFLY_API_KEY=your_scrapfly_key

# YouTube API
YOUTUBE_API_KEY=your_youtube_api_key

# Slack Notifications
SLACK_WEBHOOK_URL=your_slack_webhook_url

# Streamlit Security
STREAMLIT_PASSWORD=your_dashboard_password

# Application Settings
API_BASE_URL=http://localhost:8000
LOG_LEVEL=INFO
```

### Local Development Setup

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd DriveShop_Clip
   ```

2. Create Python 3.11.4 virtual environment:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Playwright for Level 3 scraping:
   ```bash
   playwright install chromium
   ```

5. Run the Streamlit dashboard:
   ```bash
   streamlit run src/dashboard/app.py
   ```

### Production Deployment (AWS EC2)

1. Launch EC2 t3.small instance in us-east-1
2. Configure security group:
   - Port 22 (SSH)
   - Port 8501 (Streamlit)
3. SSH into instance and clone repository
4. Create `.env` file with production credentials
5. Build and run with Docker:
   ```bash
   docker-compose up -d
   ```
6. Access dashboard at `http://<ec2-public-ip>:8501`

## Usage Guide

### 1. Input File Format

Create CSV/Excel files with these required columns:
- `Work Order Number` (WO): Unique FMS identifier
- `Loan ID`: Unique loan identifier
- `First Name`: Journalist's first name
- `Last Name`: Journalist's last name
- `Media Outlet`: Known outlet or "Unknown"
- `Model`: Vehicle model (e.g., "X5", "Accord")
- `Start Date`: Loan start date
- `End Date`: Loan end date
- `URL` (optional): Direct link or RSS feed

### 2. Dashboard Workflow

1. **Access**: Navigate to Streamlit URL, enter password
2. **Upload**: Use file uploader for loan CSV/Excel
3. **Process**: Click "Process Loans Without Clips"
   - System finds first mention only
   - Uses RSS feeds when available
   - Follows discovery logic for unknown sites
4. **Review**: AgGrid displays found clips with:
   - Relevance score (0-100)
   - Sentiment analysis
   - Brand message alignment
   - Full content preview
5. **Actions**:
   - Approve/Reject individual clips
   - Update media outlet assignments
   - Trigger re-analysis if needed
6. **Export**: Download `approved_clips.csv` for FMS

### 3. Automated Processing

Nightly cron job runs at 2 AM:
- Processes all pending loans
- Sends Slack notifications for new clips
- Completes within 2-hour window
- Maintains one-clip-per-loan rule

### 4. Special Features

- **RSS Shortcuts**: Add RSS feed URLs to bypass crawling
- **YouTube RSS**: Use `https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID`
- **Discovery Mode**: Automatically navigates review/blog sections
- **Model Variations**: "X5" matches "BMW X5", "2024 X5", etc.

## Performance & Limitations

### Expected Performance
- **Daily Volume**: ~60 loans with 2-4 URLs each
- **Processing Time**: <2 hours for nightly batch
- **Success Rate**: >90% content extraction
- **AI Costs**: $1-3 per day (~100 GPT-4 calls)

### Current Limitations (MVP)
- English content only
- No direct FMS API integration
- Single password authentication
- No mobile interface
- Manual deployment process
- One clip per loan maximum

## File Structure

```
DriveShop_Clip/
├── src/
│   ├── dashboard/
│   │   └── app.py              # Streamlit dashboard
│   ├── ingest/
│   │   ├── ingest.py           # Core processing pipeline
│   │   └── ingest_database.py  # Database processing
│   ├── analysis/
│   │   └── gpt_analysis.py     # AI analysis (GPT-4)
│   ├── crawler/
│   │   └── crawler/spiders/    # Scrapy configurations
│   ├── creatoriq/              # Future integration
│   └── utils/
│       ├── database.py         # Supabase client
│       ├── crawler_manager.py  # Tiered escalation
│       ├── youtube_api.py      # YouTube integration
│       └── model_variations.py # Vehicle matching
├── data/
│   ├── person_outlets_mapping.csv  # Journalist mappings
│   └── media_sources.csv           # JS-heavy site flags
├── documentation/              # Project documentation
├── docker-compose.yml         # Container orchestration
├── Dockerfile                 # Container definition
├── requirements.txt           # Python 3.11.4 deps
└── .env.template             # Environment template
```

## Deployment Notes

### Production Checklist

1. **Infrastructure**:
   - AWS EC2 t3.small in us-east-1
   - Security groups configured
   - Elastic IP recommended

2. **Environment**:
   - Production `.env` file secured
   - Secrets never in Git
   - API keys rotated quarterly

3. **Monitoring**:
   - Slack webhook configured
   - CloudWatch for EC2 metrics
   - Daily cost monitoring for APIs

4. **Cron Schedule**:
   ```bash
   # Nightly processing at 2 AM
   0 2 * * * cd /app && docker-compose run app python src/ingest/ingest_database.py
   ```

### API Quotas & Limits

- **YouTube API**: 10,000 units/day quota
- **OpenAI**: Monitor token usage (~$1-3/day target)
- **ScrapingBee/ScrapFly**: Check monthly limits
- **Google Search**: 100 queries/day free tier

### Maintenance Tasks

- **Weekly**: Clear SQLite cache if >1GB
- **Monthly**: Review API usage and costs
- **Quarterly**: Update dependencies, rotate API keys
- **As Needed**: Update `person_outlets_mapping.csv`

## Future Enhancements (Post-MVP)

- Direct FMS API integration
- Multi-user authentication with roles
- Airtable or advanced database storage
- Email notification system
- Mobile-responsive interface
- Multi-language content support
- Advanced analytics dashboard
- Automated model training for relevance

## Support & Troubleshooting

- **Logs**: Check `app.log` for detailed debugging
- **Common Issues**:
  - 403 errors: Site needs Level 3 escalation
  - No clips found: Check discovery keywords
  - Slow processing: Review concurrent limits
- **Documentation**: See `/documentation` folder
- **Slack Channel**: Real-time system notifications

For technical support, reference the implementation plan and technical documentation, or contact the development team.