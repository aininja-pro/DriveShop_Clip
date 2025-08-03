import os
import json
import time
from typing import Dict, Any, Optional, Tuple, List
import re

import openai
from dotenv import load_dotenv

# Import local modules
from src.utils.logger import setup_logger
from src.utils.rate_limiter import rate_limiter
from src.utils.content_extractor import extract_article_content

logger = setup_logger(__name__)

def get_openai_key() -> Optional[str]:
    """
    Get the OpenAI API key from environment variables.
    
    Returns:
        API key or None if not set
    """
    return os.environ.get('OPENAI_API_KEY')

def clean_json_response(response_text: str) -> str:
    """
    Clean a GPT response by removing any markdown code blocks or other non-JSON elements.
    Handle multiple edge cases that cause JSON parsing failures.
    
    Args:
        response_text: Raw response from GPT
        
    Returns:
        Cleaned JSON string
    """
    
    # Remove markdown code block formatting (```json and ```)
    json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(json_pattern, response_text)
    
    if match:
        logger.info("Found JSON wrapped in markdown code block, extracting...")
        cleaned = match.group(1).strip()
    else:
        # Try to find JSON object boundaries if no markdown blocks
        json_start = response_text.find('{')
        json_end = response_text.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_end > json_start:
            logger.info("Extracting JSON from object boundaries...")
            cleaned = response_text[json_start:json_end + 1]
        else:
            logger.info("No clear JSON boundaries found, using full response")
            cleaned = response_text.strip()
    
    # Additional cleaning steps to fix common JSON issues
    # Remove any trailing commas before closing braces/brackets
    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
    
    # Remove any leading/trailing whitespace and newlines
    cleaned = cleaned.strip()
    
    # Fix any double quotes that might have been escaped incorrectly
    cleaned = cleaned.replace('\\"', '"')
    
    # Remove any control characters that might cause issues
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
    
    return cleaned

def parse_json_with_fallbacks(response_text: str) -> dict:
    """
    Parse JSON with multiple fallback strategies for robustness.
    
    Args:
        response_text: Raw response text from GPT
        
    Returns:
        Parsed JSON dictionary or None
    """
    import json
    
    # Strategy 1: Clean and parse normally
    try:
        cleaned_response = clean_json_response(response_text)
        logger.info(f"Attempting to parse cleaned JSON response (length: {len(cleaned_response)})")
        analysis_result = json.loads(cleaned_response)
        logger.info(f"✅ Successfully parsed JSON on first attempt")
        return analysis_result
    except json.JSONDecodeError as e:
        logger.warning(f"Strategy 1 failed: {e}")
    
    # Strategy 2: Try to fix trailing comma issues more aggressively
    try:
        logger.info("Trying Strategy 2: Aggressive comma fixing...")
        cleaned = clean_json_response(response_text)
        # Remove trailing commas more aggressively
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        # Fix missing commas between objects
        cleaned = re.sub(r'}\s*{', '},{', cleaned)
        cleaned = re.sub(r']\s*\[', '],[', cleaned)
        
        analysis_result = json.loads(cleaned)
        logger.info(f"✅ Successfully parsed JSON with Strategy 2")
        return analysis_result
    except json.JSONDecodeError as e:
        logger.warning(f"Strategy 2 failed: {e}")
    
    # Return None if all strategies fail
    logger.error("All JSON parsing strategies failed. Returning None.")
    return None

def analyze_clip_enhanced(content: str, make: str, model: str, year: str = None, trim: str = None, max_retries: int = 3, url: str = None) -> Dict[str, Any]:
    """
    Analyze a clip using the enhanced Message Pull-Through Analysis prompt.
    
    Args:
        content: Article or video transcript content (HTML or text)
        make: Vehicle make
        model: Vehicle model
        year: Vehicle year (optional)
        trim: Vehicle trim level (optional)
        max_retries: Maximum number of retry attempts
        url: URL of the content (for HTML extraction and content type detection)
        
    Returns:
        Dictionary with enhanced analysis results for Message Pull-Through
    """
    api_key = get_openai_key()
    
    if not api_key:
        logger.error("No OpenAI API key found. Cannot analyze content - skipping analysis.")
        return None

    # Detect content type based on URL or content characteristics
    is_youtube = url and ('youtube.com' in url or 'youtu.be' in url)
    content_type = "YouTube Video Transcript" if is_youtube else "Web Article"
    
    # Check if content is HTML and extract article text if so (for web articles only)
    if not is_youtube:
        is_html = bool(re.search(r'<html|<body|<div|<p>', content))
        if is_html and url:
            logger.info("Content appears to be HTML. Extracting article text...")
            
            # Create expected topic from vehicle make and model for quality checking
            expected_topic = f"{make} {model}"
            extracted_content = extract_article_content(content, url, expected_topic)
            
            # Check if extraction was successful
            if extracted_content:
                logger.info(f"Successfully extracted article text: {len(extracted_content)} characters")
                content = extracted_content
            else:
                logger.warning("Failed to extract article text from HTML. Using raw content.")
    
    # Truncate content if it's too long
    max_content_length = 12000  # Increased for more comprehensive analysis
    if len(content) > max_content_length:
        logger.info(f"Truncating content from {len(content)} to {max_content_length} characters")
        content = content[:max_content_length] + "..."
    
    # Pre-filters to save OpenAI costs (same as original)
    # Filter 1: Content Length Check
    MIN_CONTENT_LENGTH = 200
    if len(content.strip()) < MIN_CONTENT_LENGTH:
        logger.info(f"💰 PRE-FILTER: Content too short ({len(content)} chars < {MIN_CONTENT_LENGTH}) - skipping GPT analysis")
        return None
    
    # Enhanced Content Quality Check
    # Check if content is still HTML (extraction failed)
    if content.strip().startswith('<!DOCTYPE') or content.strip().startswith('<html'):
        logger.warning(f"⚠️ CONTENT QUALITY: Content appears to be raw HTML - extraction may have failed")
        # Try to extract some text from HTML as fallback
        text_only = re.sub('<[^<]+?>', '', content)  # Strip HTML tags
        text_only = ' '.join(text_only.split())  # Clean whitespace
        if len(text_only) > MIN_CONTENT_LENGTH:
            logger.info(f"Attempting analysis with HTML-stripped content ({len(text_only)} chars)")
            content = text_only
        else:
            logger.error(f"💰 PRE-FILTER: Even after HTML stripping, content too short ({len(text_only)} chars)")
            return None
    
    # Check content richness (sentence count)
    sentences = [s.strip() for s in re.split(r'[.!?]+', content) if len(s.strip()) > 20]
    if len(sentences) < 3:
        logger.warning(f"⚠️ CONTENT QUALITY: Very brief content ({len(sentences)} sentences) - results may be limited")
    
    # Log content quality metrics
    logger.info(f"📊 Content quality: {len(content)} chars, ~{len(sentences)} sentences")
    
    # Filter 2: Basic Model/Make Keyword Check
    make_lower = make.lower() if make else ""
    model_lower = model.lower() if model else ""
    content_lower = content.lower()
    
    # Check if either make OR model is mentioned
    make_found = bool(make_lower) and (make_lower in content_lower)
    model_base = model_lower.split()[0] if model_lower else ""
    model_found = bool(model_lower) and (model_lower in content_lower or (model_base and model_base in content_lower))
    
    if not make_found and not model_found:
        logger.info(f"💰 PRE-FILTER: Neither '{make}' nor '{model}' found in content - skipping GPT analysis")
        return None
    
    # Build vehicle identifier string
    vehicle_parts = [make, model]
    if year:
        vehicle_parts.insert(0, str(year))
    if trim:
        vehicle_parts.append(trim)
    vehicle_identifier = " ".join(filter(None, vehicle_parts))
    
    # Format the enhanced prompt
    prompt = ENHANCED_SENTIMENT_PROMPT.format(
        make=make,
        model=model,
        year=year or "",
        trim=trim or "",
        content=content
    )
    
    logger.info(f"Making enhanced Message Pull-Through analysis call to OpenAI API (attempt 1/{max_retries})")
    
    # Set API key for older OpenAI client version
    openai.api_key = api_key
    
    for attempt in range(max_retries):
        try:
            # Use the older OpenAI client format (compatible with openai==0.27.0)
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.3,
                request_timeout=120
            )
            
            # Extract response content
            response_content = response.choices[0].message.content.strip()
            logger.info(f"Received enhanced analysis response from OpenAI")
            
            # Parse JSON response
            analysis_result = parse_json_with_fallbacks(response_content)
            
            if analysis_result:
                logger.info(f"Successfully analyzed content with enhanced prompt: sentiment={analysis_result.get('sentiment_classification', {}).get('overall', 'N/A')}")
                
                # Add backward compatibility fields for existing system
                analysis_result['vehicle_identifier'] = vehicle_identifier
                analysis_result['content_type'] = content_type
                
                # Map new sentiment to old format for compatibility
                sentiment_map = {
                    'very_positive': 'positive',
                    'positive': 'positive',
                    'neutral': 'neutral',
                    'negative': 'negative',
                    'very_negative': 'negative'
                }
                
                overall_sentiment = analysis_result.get('sentiment_classification', {}).get('overall', 'neutral')
                analysis_result['overall_sentiment'] = sentiment_map.get(overall_sentiment, 'neutral')
                
                # Calculate relevance score based on content depth
                features_count = len(analysis_result.get('key_features_mentioned', []))
                attributes_count = len(analysis_result.get('brand_attributes_captured', []))
                drivers_count = len(analysis_result.get('purchase_drivers', []))
                
                # Relevance scoring: more extracted elements = higher relevance
                relevance_score = min(10, max(1, 
                    3 + # Base score for mentioning the vehicle
                    min(4, features_count) + # Up to 4 points for features
                    min(2, attributes_count) + # Up to 2 points for brand attributes
                    min(1, drivers_count) # Up to 1 point for purchase drivers
                ))
                
                analysis_result['relevance_score'] = relevance_score
                
                # Add summary for backward compatibility
                sentiment_summary = analysis_result.get('sentiment_classification', {}).get('rationale', '')
                analysis_result['summary'] = sentiment_summary
                
                # Brand alignment based on sentiment of brand attributes
                brand_sentiments = [attr.get('sentiment', 'neutral') for attr in analysis_result.get('brand_attributes_captured', [])]
                positive_brand = sum(1 for s in brand_sentiments if s == 'reinforced')
                negative_brand = sum(1 for s in brand_sentiments if s == 'challenged')
                analysis_result['brand_alignment'] = positive_brand > negative_brand
                
                return analysis_result
            else:
                logger.error("Failed to parse enhanced analysis response")
                return None
                
        except Exception as e:
            logger.error(f"Error in enhanced analysis (attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed after {max_retries} attempts, cannot analyze content")
                return None

# Enhanced Message Pull-Through Analysis Prompt
ENHANCED_SENTIMENT_PROMPT = """# Automotive Review Sentiment Analysis

You are an automotive marketing intelligence analyst extracting standardized insights from vehicle reviews. Your analysis will be compared against manufacturer (OEM) marketing messages to identify alignment and gaps.

**Context:** OEMs promote specific features, brand attributes, and purchase reasons. Your job is to identify what reviewers ACTUALLY discuss and how they frame it.

**Input:**
- Vehicle: {make} {model} {year} {trim}
- Content: {content}

**Your Task:** Extract structured data focusing on three core areas that enable comparison with OEM messaging.

**Output Format (JSON):**
```json
{{
  "sentiment_classification": {{
    "overall": "very_positive|positive|neutral|negative|very_negative",
    "confidence": 0.0-1.0,
    "rationale": "<2-3 sentences explaining classification>"
  }},
  
  "key_features_mentioned": [
    {{
      "feature": "<specific feature name>",
      "sentiment": "positive|neutral|negative",
      "quote": "<exact quote from review>"
    }}
    // Extract ALL tangible features discussed (aim for 10, include minor mentions)
    // Include: engine specs, interior features, technology, safety, comfort, cargo, design elements, etc.
  ],
  
  "brand_attributes_captured": [
    {{
      "attribute": "<brand quality/perception>",
      "sentiment": "reinforced|neutral|challenged",
      "evidence": "<exact quote demonstrating this>"
    }}
    // Extract 3-5 brand-level perceptions (include implied attributes)
    // Consider: reliability, luxury, value, innovation, sportiness, practicality, status, etc.
  ],
  
  "purchase_drivers": [
    {{
      "reason": "<specific reason to buy or not buy>",
      "sentiment": "positive|negative",
      "strength": "primary|secondary|mentioned",
      "quote": "<exact quote>"
    }}
    // Extract ALL purchase decision factors (aim for at least 3)
  ],
  
  "competitive_context": {{
    "direct_comparisons": ["<vehicle>: <brief context>"],
    "market_positioning": "<how reviewer positions this vs. segment>"
  }}
}}
```

**Examples to Guide Extraction:**

KEY FEATURES (Tangible):
- "The 2.0L turbo engine delivers surprising power" → feature: "2.0L turbo engine", sentiment: "positive"
- "Infotainment system feels dated" → feature: "infotainment system", sentiment: "negative"
- "Excellent cargo space at 38 cubic feet" → feature: "cargo space", sentiment: "positive"

BRAND ATTRIBUTES (Intangible):
- "Typical Toyota reliability" → attribute: "reliability", sentiment: "reinforced"
- "Not the sporty Mazda we expected" → attribute: "sportiness", sentiment: "challenged"
- "Feels premium for the price" → attribute: "value luxury", sentiment: "reinforced"

PURCHASE DRIVERS:
- "At this price point, it's hard to beat" → reason: "value for money", sentiment: "positive", strength: "primary"
- "If you need three rows, look elsewhere" → reason: "lacks third row", sentiment: "negative", strength: "primary"
- "Great for families" → reason: "family-friendly", sentiment: "positive", strength: "secondary"

**Classification Rules:**
- VERY POSITIVE: Explicit strong recommendation to buy with minimal criticisms
- POSITIVE: More pros than cons, favorable tone, would recommend
- NEUTRAL: Balanced or purely factual, no clear recommendation
- NEGATIVE: More cons than pros, critical tone, hesitant about recommending
- VERY NEGATIVE: Explicit recommendation against buying or to buy competitors instead

**Extraction Guidelines:**
1. Only extract what's explicitly stated in the review - no inference
2. Use exact quotes from the review, not paraphrased
3. AIM FOR MAXIMUM EXTRACTION: Try to find 10 features, 3-5 attributes, 3+ drivers
4. Include even briefly mentioned features (e.g., "comfortable seats" counts as a feature)
5. Features = tangible (what the car HAS) - be granular (e.g., "leather seats" and "heated seats" are separate)
6. Attributes = intangible (what the brand IS) - can be implied from context
7. Drivers = decision factors (why to BUY or NOT BUY) - include all mentioned reasons
8. If the review is brief, extract everything possible rather than leaving arrays empty

Return ONLY valid JSON matching the specified format."""

# Keep the original analyze_clip function for backward compatibility
analyze_clip = analyze_clip_enhanced  # Alias for easy migration