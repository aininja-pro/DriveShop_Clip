"""
Configuration constants for the enhanced crawling system.
"""

# Domains that should use ScrapingBee API instead of basic HTTP requests
# These are sites known to be hostile to basic scraping
API_SCRAPER_DOMAINS = [
    "motortrend.com",
    "caranddriver.com", 
    "roadandtrack.com",
    "jalopnik.com",
    "thedrive.com"
]

# URL path patterns that indicate generic index pages
# These trigger Google Search to find specific articles instead of scraping the index
GENERIC_INDEX_PATTERNS = [
    "/car-reviews",
    "/reviews",
    "/road-tests", 
    "/first-drives",
    "/test-drives",
    "/resources/vehicle-reviews",  # For carpro.com
    "/category/news/reviews/"      # For carfanaticsblog.com (already working but for completeness)
]

# Additional patterns for content discovery
ARTICLE_INDICATORS = [
    "review", "first-drive", "test-drive", "road-test",
    "drive", "test", "preview", "comparison", "hands-on"
]

# Vehicle model cleanup patterns for search optimization
MODEL_CLEANUP_PATTERNS = [
    " Prestige", " Premium", " Plus", " Base", " S-Line",
    " Quattro", " AWD", " FWD", " Hybrid", " Electric"
]

# Search query templates for Google Custom Search
SEARCH_QUERY_TEMPLATES = {
    'site_specific_with_year': 'site:{domain} "{year} {make} {model}" {term}',
    'site_specific': 'site:{domain} "{make} {model}" {term}',
    'global_with_year': '"{year} {make} {model}" {term}',
    'global': '"{make} {model}" {term}'
}

# Search terms to try in order of preference
SEARCH_TERMS = [
    "review",
    "first drive", 
    "test drive",
    "road test",
    "preview"
]

# ScrapingBee API configuration
SCRAPINGBEE_CONFIG = {
    'render_js': True,
    'premium_proxy': False,
    'country_code': 'us',
    'wait': 3000,  # milliseconds
    'wait_for': '#main, article, .content',
    'block_ads': True,
    'block_resources': False,
    'timeout': 30  # seconds
}

# Google Custom Search configuration
GOOGLE_SEARCH_CONFIG = {
    'num_results': 5,
    'timeout': 10,  # seconds
    'rate_limit_delay': 0.5  # seconds between requests
}

# Cache configuration
CACHE_CONFIG = {
    'ttl_hours': 24,
    'cleanup_interval_hours': 6,
    'max_entries_per_domain': 1000
}

# Tier priorities for the 5-tier escalation system
CRAWLER_TIERS = {
    1: "Google Search",
    2: "ScrapingBee API", 
    3: "Basic HTTP",
    4: "RSS Feed",
    5: "Playwright Headless",
    6: "Manual Review Flag"
}

# User agents for different crawling methods
USER_AGENTS = {
    'basic': 'DriveShopMediaMonitorBot/1.0',
    'enhanced': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'mobile': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1'
}

# YouTube ScrapFly configuration
# Can be overridden by environment variables YOUTUBE_SCRAPFLY_MAX_VIDEOS, etc.
import os

YOUTUBE_SCRAPFLY_CONFIG = {
    'max_videos': int(os.getenv('YOUTUBE_SCRAPFLY_MAX_VIDEOS', 100)),  # Maximum number of videos to try to fetch from a channel
    'scroll_actions': int(os.getenv('YOUTUBE_SCRAPFLY_SCROLL_ACTIONS', 5)),  # Number of scroll actions to perform (each loads ~10-15 more videos)
    'scroll_wait_ms': int(os.getenv('YOUTUBE_SCRAPFLY_SCROLL_WAIT_MS', 2000))  # Milliseconds to wait after each scroll
} 