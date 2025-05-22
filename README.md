# DriveShop Clip Tracking

An AI-enhanced media monitoring system that tracks earned media coverage for vehicle loans by analyzing web articles and YouTube videos.

## Project Overview

The DriveShop Clip Tracking system processes daily CSV feeds of vehicle loans, crawls specified URLs to find relevant media mentions, extracts meaningful content, and uses OpenAI's GPT models to analyze relevance, sentiment, and brand alignment.

### Key Features

- **Smart Multi-Level Web Crawling**: Escalates from basic requests through enhanced headers to headless browsing
- **Intelligent Content Extraction**: Filters HTML noise and extracts clean article text
- **AI-Powered Analysis**: Leverages OpenAI GPT to score and summarize media mentions
- **User-Friendly Dashboard**: Streamlit interface for reviewing and approving clips
- **Automated Processing**: Scheduled nightly jobs with Slack notifications

## Architecture

- **Crawler Module**: Handles web page retrieval with multi-level escalation
- **Content Extractor**: Cleans HTML and extracts meaningful text
- **Analysis Module**: Processes content with GPT to extract insights
- **Dashboard**: Streamlit UI for human review and approval

## Technology Stack

- **Python 3.x**: Core language
- **Scrapy/Requests/Playwright**: Web crawling at different levels
- **Beautiful Soup**: HTML parsing and content extraction
- **OpenAI API**: GPT analysis for relevance and sentiment
- **Streamlit**: User interface for review
- **Docker**: Containerization for consistent deployment

## Getting Started

### Prerequisites

- Python 3.9+
- Docker (recommended for deployment)
- OpenAI API key
- Slack webhook URL (optional)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/your-org/driveshop-clip.git
cd driveshop-clip
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. Run the Streamlit dashboard:
```bash
python -m src.dashboard.app
```

### Docker Deployment

```bash
docker build -t driveshop-clip .
docker run -p 8501:8501 -v $(pwd)/data:/app/data -v $(pwd)/.env:/app/.env driveshop-clip
```

## Usage

1. Upload the daily `Loans_without_Clips.csv` file via the Streamlit UI
2. System will process each loan, crawl URLs, and analyze content
3. Review matching clips and their AI-generated scores
4. Approve or flag clips for further review
5. Export approved clips for downstream processing

## Project Structure

```
├── src/
│   ├── ingest/             # CSV parsing and pipeline orchestration
│   ├── crawler/            # Web crawling with multi-level strategies
│   ├── utils/              # Shared utilities and helpers
│   │   └── content_extractor.py  # HTML cleaning and text extraction
│   ├── analysis/           # GPT integration for content analysis
│   └── dashboard/          # Streamlit UI components
├── data/
│   └── fixtures/           # Sample data for testing
├── Dockerfile              # Container definition
└── requirements.txt        # Python dependencies
```

## License

Proprietary - Copyright © 2025 DriveShop 