# Analysis Module Documentation

## Module: `src/analysis/gpt_analysis.py`

### Purpose

The Analysis module provides AI-powered content analysis using OpenAI's GPT-4 Turbo model to evaluate media clips for relevance, sentiment, and brand alignment. It implements sophisticated parsing strategies, cost-optimization through pre-filtering, and specialized prompts for different content types (YouTube videos vs. web articles). The module is designed to extract strategic marketing insights from automotive media content while maintaining cost efficiency.

### Key Functions/Classes

#### Core Analysis Functions
```python
def analyze_clip(content: str, make: str, model: str, 
                max_retries: int = 3, url: str = None) -> Dict[str, Any]:
    """
    Comprehensive automotive sentiment analysis using GPT-4.
    Implements pre-filters to save API costs and specialized prompts.
    Returns detailed analysis with marketing insights or None if fails.
    """

def analyze_clip_relevance_only(content: str, make: str, model: str) -> Dict[str, Any]:
    """
    Cost-optimized analysis for relevance scoring only.
    Skips detailed sentiment analysis to reduce API costs.
    Used in database ingestion pipeline.
    """
```

#### JSON Parsing Functions
```python
def parse_json_with_fallbacks(response_text: str) -> dict:
    """
    Robust JSON parsing with 4 escalating strategies:
    1. Clean and parse normally
    2. Aggressive comma fixing
    3. Manual field extraction with regex
    4. Return None (no fallback data)
    """

def clean_json_response(response_text: str) -> str:
    """
    Cleans GPT responses by removing markdown blocks and fixing JSON issues.
    Handles edge cases that commonly cause parsing failures.
    """
```

#### Helper Functions
```python
def get_openai_key() -> Optional[str]:
    """
    Retrieves OpenAI API key from environment variables.
    Returns None if not configured.
    """

def flexible_model_match(title: str, model: str) -> bool:
    """
    Intelligent vehicle model matching in content.
    Handles variations like "X5" matching "BMW X5", "2024 X5", etc.
    """
```

#### GPTAnalyzer Class
```python
class GPTAnalyzer:
    """
    Class-based analyzer for content using OpenAI's GPT-4 Turbo.
    Handles API calls with retry logic and rate limiting.
    """
    
    def analyze_content(self, content: str, vehicle_make: str, 
                       vehicle_model: str, max_retries: int = 3,
                       timeout: int = 60) -> Dict[str, Any]:
        """
        Analyzes content for relevance, sentiment, and brand messaging.
        Includes retry logic and rate limiting.
        """
```

### Expected Inputs/Outputs

#### Inputs
1. **Content Analysis**:
   - `content`: Article text or YouTube transcript (HTML or plain text)
   - `make`: Vehicle manufacturer (e.g., "Honda")
   - `model`: Vehicle model (e.g., "Accord")
   - `url`: Optional URL for content type detection
   - `max_retries`: Number of retry attempts (default: 3)

2. **Pre-Filter Thresholds**:
   - Minimum content length: 200 characters
   - Printable character ratio: >80%
   - Generic page indicators: <2 matches

#### Outputs
1. **Comprehensive Analysis** (analyze_clip):
   ```json
   {
     "relevance_score": 0-10,
     "overall_score": 0-10,
     "overall_sentiment": "positive/neutral/negative",
     "brand_alignment": true/false,
     "summary": "Executive summary for CMO briefing",
     "recommendation": "Strategic marketing recommendation",
     "aspects": {
       "performance": {"score": 0-10, "note": "..."},
       "exterior_design": {"score": 0-10, "note": "..."},
       "interior_comfort": {"score": 0-10, "note": "..."},
       "technology": {"score": 0-10, "note": "..."},
       "value": {"score": 0-10, "note": "..."}
     },
     "pros": ["key positive 1", "key positive 2"],
     "cons": ["key concern 1", "key concern 2"],
     "key_mentions": ["topic 1", "topic 2"],
     "video_quotes": ["memorable quote 1", "memorable quote 2"]
   }
   ```

2. **Relevance-Only Analysis**:
   ```json
   {
     "relevance_score": 0-10
   }
   ```

3. **Failure Response**: `None` (no mock data)

### Dependencies

```python
# External Libraries
import openai  # Version 0.27.0 (older client format)
from dotenv import load_dotenv

# Internal Modules
from src.utils.logger import setup_logger
from src.utils.rate_limiter import rate_limiter
from src.utils.content_extractor import extract_article_content
```

### Cost Optimization Features

#### Pre-Filters (Save API Costs)
1. **Content Length Check**: Skip if <200 characters
2. **Keyword Validation**: Must mention make OR model
3. **Content Quality Check**: >80% printable characters
4. **Generic Page Detection**: Avoid category/index pages

#### Processing Optimizations
- Content truncation at 12,000 characters
- Relevance-only mode for batch processing
- Caching in upstream modules
- Smart retry with exponential backoff

### Prompt Templates

#### YouTube Video Analysis
- Strategic marketing focus
- Creator intelligence (influence tier, audience archetype)
- Competitive intelligence
- Purchase intent signals
- Viral potential assessment
- Action items for marketing team

#### Web Article Analysis
- Publication credibility assessment
- SEO/Digital influence factor
- Editorial stance detection
- Media relationship strategy
- Brand narrative impact
- Shareable quote extraction

### Error Handling

1. **API Key Missing**: Returns `None` instead of mock data
2. **JSON Parsing Failures**: 
   - 4 escalating strategies
   - Manual field extraction fallback
   - No fake data on complete failure
3. **API Errors**:
   - Rate limit handling with 30s wait
   - Timeout retry with 5s wait
   - Exponential backoff (2^attempt seconds)
4. **Content Issues**:
   - HTML extraction for web articles
   - Truncation for oversized content
   - Graceful handling of corrupted data

### Strategic Analysis Features

#### Marketing Intelligence
- **Impact Scoring**: 1-10 scale for CMO attention
- **Brand Perception**: Ascending/Stable/Declining trajectory
- **Messaging Opportunities**: Extracted from content
- **Risk Identification**: Brand vulnerabilities

#### Competitive Analysis
- Positioning vs. competitors
- Market advantages highlighted
- Vulnerabilities exposed
- Differentiation opportunities

#### Creator/Publication Analysis
- **YouTube**: Influence tier, audience archetype, credibility
- **Articles**: Publication credibility, reach, editorial stance
- Relationship recommendations (Engage/Monitor/Ignore)

### Performance Considerations

- **Token Usage**: ~4,000 tokens per analysis
- **API Costs**: $0.01-$0.03 per call
- **Response Time**: 2-10 seconds typical
- **Retry Strategy**: Max 3 attempts with backoff
- **Rate Limiting**: Integrated with global limiter

### Security Considerations

- API key stored in environment variables
- No sensitive data logged
- Content sanitization before processing
- Secure API communication
- No data persistence in module