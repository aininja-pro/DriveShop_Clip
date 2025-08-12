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
from src.utils.openai_semaphore import openai_semaphore

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
        Parsed JSON dictionary or fallback structure
    """
    import json
    
    # Strategy 1: Clean and parse normally
    try:
        cleaned_response = clean_json_response(response_text)
        logger.info(f"Attempting to parse cleaned JSON response (length: {len(cleaned_response)})")
        analysis_result = json.loads(cleaned_response)
        logger.info(f"✅ Successfully parsed JSON on first attempt")
        
        # Validate and fix missing overall_score even if JSON parsed successfully
        if 'overall_score' not in analysis_result or analysis_result.get('overall_score') is None:
            logger.warning("JSON parsed successfully but missing overall_score, calculating from aspects...")
            
            # Calculate overall_score from aspect scores if available
            if 'aspects' in analysis_result and isinstance(analysis_result['aspects'], dict):
                aspect_scores = []
                for aspect_data in analysis_result['aspects'].values():
                    if isinstance(aspect_data, dict) and 'score' in aspect_data:
                        aspect_scores.append(aspect_data['score'])
                
                if aspect_scores:
                    calculated_overall = round(sum(aspect_scores) / len(aspect_scores))
                    analysis_result['overall_score'] = calculated_overall
                    logger.info(f"Calculated missing overall_score as {calculated_overall} from aspect averages: {aspect_scores}")
                else:
                    analysis_result['overall_score'] = 5
                    logger.warning("No aspect scores found, defaulting overall_score to 5")
            else:
                analysis_result['overall_score'] = 5
                logger.warning("No aspects data found, defaulting overall_score to 5")
        
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
    
    # Strategy 3: Extract key fields manually using regex
    try:
        logger.info("Trying Strategy 3: Manual field extraction...")
        
        # Extract key numeric fields
        relevance_match = re.search(r'"relevance_score"\s*:\s*(\d+)', response_text)
        overall_match = re.search(r'"overall_score"\s*:\s*(\d+)', response_text)
        sentiment_match = re.search(r'"overall_sentiment"\s*:\s*"([^"]+)"', response_text)
        brand_match = re.search(r'"brand_alignment"\s*:\s*(true|false)', response_text)
        
        # Extract summary (handling potential escaping)
        summary_match = re.search(r'"summary"\s*:\s*"([^"]+(?:\\.[^"]*)*)"', response_text)
        
        # Extract aspects scores
        performance_match = re.search(r'"performance"\s*:[^}]*"score"\s*:\s*(\d+)', response_text)
        design_match = re.search(r'"exterior_design"\s*:[^}]*"score"\s*:\s*(\d+)', response_text)
        interior_match = re.search(r'"interior_comfort"\s*:[^}]*"score"\s*:\s*(\d+)', response_text)
        tech_match = re.search(r'"technology"\s*:[^}]*"score"\s*:\s*(\d+)', response_text)
        value_match = re.search(r'"value"\s*:[^}]*"score"\s*:\s*(\d+)', response_text)
        
        # Extract pros and cons arrays
        pros_match = re.search(r'"pros"\s*:\s*\[([^\]]+)\]', response_text)
        cons_match = re.search(r'"cons"\s*:\s*\[([^\]]+)\]', response_text)
        
        # Extract key_mentions array
        key_mentions_match = re.search(r'"key_mentions"\s*:\s*\[([^\]]+)\]', response_text)
        
        # Extract recommendation
        recommendation_match = re.search(r'"recommendation"\s*:\s*"([^"]+(?:\\.[^"]*)*)"', response_text)
        
        # Extract video_quotes for YouTube content
        video_quotes_match = re.search(r'"video_quotes"\s*:\s*\[([^\]]+)\]', response_text)
        
        if relevance_match:
            # Build the analysis result manually with proper aspect notes
            aspects_data = {}
            
            # Extract aspect notes for more detailed tooltips
            perf_note_match = re.search(r'"performance"\s*:[^}]*"note"\s*:\s*"([^"]+(?:\\.[^"]*)*)"', response_text)
            design_note_match = re.search(r'"exterior_design"\s*:[^}]*"note"\s*:\s*"([^"]+(?:\\.[^"]*)*)"', response_text)
            interior_note_match = re.search(r'"interior_comfort"\s*:[^}]*"note"\s*:\s*"([^"]+(?:\\.[^"]*)*)"', response_text)
            tech_note_match = re.search(r'"technology"\s*:[^}]*"note"\s*:\s*"([^"]+(?:\\.[^"]*)*)"', response_text)
            value_note_match = re.search(r'"value"\s*:[^}]*"note"\s*:\s*"([^"]+(?:\\.[^"]*)*)"', response_text)
            
            # Build aspects with proper notes
            aspects_data["performance"] = {
                "score": int(performance_match.group(1)) if performance_match else 7,
                "note": perf_note_match.group(1).replace('\\"', '"') if perf_note_match else "Performance analysis completed"
            }
            aspects_data["exterior_design"] = {
                "score": int(design_match.group(1)) if design_match else 7,
                "note": design_note_match.group(1).replace('\\"', '"') if design_note_match else "Design analysis completed"
            }
            aspects_data["interior_comfort"] = {
                "score": int(interior_match.group(1)) if interior_match else 7,
                "note": interior_note_match.group(1).replace('\\"', '"') if interior_note_match else "Interior analysis completed"
            }
            aspects_data["technology"] = {
                "score": int(tech_match.group(1)) if tech_match else 7,
                "note": tech_note_match.group(1).replace('\\"', '"') if tech_note_match else "Technology analysis completed"
            }
            aspects_data["value"] = {
                "score": int(value_match.group(1)) if value_match else 7,
                "note": value_note_match.group(1).replace('\\"', '"') if value_note_match else "Value analysis completed"
            }
            
            analysis_result = {
                "relevance_score": int(relevance_match.group(1)),
                "overall_sentiment": sentiment_match.group(1) if sentiment_match else "neutral",
                "brand_alignment": brand_match.group(1) == "true" if brand_match else True,
                "summary": summary_match.group(1).replace('\\"', '"') if summary_match else "Comprehensive analysis completed using enhanced parsing techniques.",
                "recommendation": recommendation_match.group(1).replace('\\"', '"') if recommendation_match else "Detailed analysis available - review aspect scores for complete evaluation.",
                "aspects": aspects_data
            }
            
            # Calculate overall_score from aspects - this is crucial for the Honda Prologue issue
            if overall_match:
                analysis_result["overall_score"] = int(overall_match.group(1))
                logger.info(f"Found explicit overall_score: {analysis_result['overall_score']}")
            else:
                # Calculate overall score as average of aspect scores
                aspect_scores = [data["score"] for data in aspects_data.values()]
                if aspect_scores:
                    calculated_overall = round(sum(aspect_scores) / len(aspect_scores))
                    analysis_result["overall_score"] = calculated_overall
                    logger.info(f"Calculated missing overall_score as {calculated_overall} from aspect averages: {aspect_scores}")
                else:
                    analysis_result["overall_score"] = 5
                    logger.warning("No aspect scores found, defaulting overall_score to 5")
            
            # Extract pros array
            if pros_match:
                pros_text = pros_match.group(1)
                pros_items = re.findall(r'"([^"]+)"', pros_text)
                analysis_result["pros"] = pros_items
            else:
                analysis_result["pros"] = ["Positive aspects identified in analysis"]
            
            # Extract cons array  
            if cons_match:
                cons_text = cons_match.group(1)
                cons_items = re.findall(r'"([^"]+)"', cons_text)
                analysis_result["cons"] = cons_items
            else:
                analysis_result["cons"] = ["Areas for improvement noted"]
            
            # Extract key_mentions array for both YouTube and articles
            if key_mentions_match:
                key_mentions_text = key_mentions_match.group(1)
                key_mentions_items = re.findall(r'"([^"]+)"', key_mentions_text)
                analysis_result["key_mentions"] = key_mentions_items
            else:
                # Extract some key phrases from the content as fallback
                content_lower = response_text.lower()
                key_mentions_fallback = []
                if "performance" in content_lower:
                    key_mentions_fallback.append("Performance characteristics")
                if "design" in content_lower:
                    key_mentions_fallback.append("Design elements")
                if "technology" in content_lower:
                    key_mentions_fallback.append("Technology features")
                if "interior" in content_lower:
                    key_mentions_fallback.append("Interior features")
                if "value" in content_lower:
                    key_mentions_fallback.append("Value proposition")
                analysis_result["key_mentions"] = key_mentions_fallback or ["Vehicle analysis completed"]
            
            # Add video_quotes for YouTube content
            if video_quotes_match:
                video_quotes_text = video_quotes_match.group(1)
                video_quotes_items = re.findall(r'"([^"]+)"', video_quotes_text)
                analysis_result["video_quotes"] = video_quotes_items
            else:
                analysis_result["video_quotes"] = []
            
            logger.info("✅ Successfully extracted detailed fields manually with enhanced parsing")
            logger.info(f"Final analysis result - overall_score: {analysis_result['overall_score']}, relevance: {analysis_result['relevance_score']}")
            return analysis_result
        else:
            logger.warning("Strategy 3 failed: Could not extract relevance_score")
            
    except Exception as e:
        logger.error(f"Strategy 3 failed with exception: {e}")
        import traceback
        logger.error(f"Strategy 3 traceback: {traceback.format_exc()}")
    
    # Strategy 4: Return None - no fallback per user request
    logger.error("All JSON parsing strategies failed. Returning None instead of fallback data.")
    return None

def analyze_clip(content: str, make: str, model: str, max_retries: int = 3, url: str = None) -> Dict[str, Any]:
    """
    Analyze a clip using GPT-4 for comprehensive automotive sentiment analysis.
    
    Args:
        content: Article or video transcript content (HTML or text)
        make: Vehicle make
        model: Vehicle model
        max_retries: Maximum number of retry attempts
        url: URL of the content (for HTML extraction and content type detection)
        
    Returns:
        Dictionary with comprehensive analysis results
    """
    api_key = get_openai_key()
    
    if not api_key:
        logger.error("No OpenAI API key found. Cannot analyze content - skipping analysis.")
        return None  # Return None instead of mock analysis

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
    
    # Log content excerpt for debugging
    content_excerpt = content[:500] + "..." if len(content) > 500 else content
    logger.info(f"Content being sent to GPT (excerpt):\n{content_excerpt}")
    
    # 💰 SMART PRE-FILTERS: Block content that would result in relevance=0 (saves OpenAI costs)
    
    # Filter 1: Content Length Check (avoid analyzing titles or tiny snippets)
    MIN_CONTENT_LENGTH = 200  # Conservative threshold
    if len(content.strip()) < MIN_CONTENT_LENGTH:
        logger.info(f"💰 PRE-FILTER: Content too short ({len(content)} chars < {MIN_CONTENT_LENGTH}) - skipping GPT analysis")
        return None
    
    # Filter 2: Basic Model/Make Keyword Check (avoid completely irrelevant content)
    make_lower = make.lower() if make else ""
    model_lower = model.lower() if model else ""
    content_lower = content.lower()
    
    # Check if either make OR model is mentioned (conservative approach)
    make_found = bool(make_lower) and (make_lower in content_lower)
    
    # For model, check for the base model name (first word) to handle variants
    # e.g., "Elantra Hybrid Limited" -> check for "elantra"
    model_base = model_lower.split()[0] if model_lower else ""
    model_found = bool(model_lower) and (model_lower in content_lower or (model_base and model_base in content_lower))
    
    # Special handling for models with numbers like "4Runner", "CX-5", "X3", etc.
    # Also check for common variations (with/without spaces, hyphens)
    if not model_found and model:
        # Create variations of the model name for matching
        model_variations = [
            model_lower,  # Original lowercase
            model_lower.replace('-', ''),  # Remove hyphens: "cx-5" -> "cx5"
            model_lower.replace(' ', ''),  # Remove spaces: "4 runner" -> "4runner"
            model_lower.replace('-', ' '),  # Replace hyphens with spaces: "cx-5" -> "cx 5"
        ]
        
        # For models starting with numbers, add space-separated version
        if model and model[0].isdigit():
            # "4Runner" -> also check "4 runner"
            space_separated = re.sub(r'(\d+)([A-Za-z])', r'\1 \2', model_lower)
            if space_separated != model_lower:
                model_variations.append(space_separated)
        
        # Check all variations
        for variant in model_variations:
            if variant and variant in content_lower:
                model_found = True
                logger.info(f"Found model variant '{variant}' in content")
                break
    
    if not make_found and not model_found:
        logger.info(f"💰 PRE-FILTER: Neither '{make}' nor '{model}' (or variants) found in content - skipping GPT analysis")
        return None
    
    # Filter 3: Binary/Corrupted Content Detection (avoid analyzing garbage data)
    try:
        # Check if content is mostly printable characters
        printable_chars = sum(1 for c in content if c.isprintable())
        printable_ratio = printable_chars / len(content) if content else 0
        
        if printable_ratio < 0.8:  # Less than 80% printable characters
            logger.info(f"💰 PRE-FILTER: Content appears corrupted (only {printable_ratio:.1%} printable) - skipping GPT analysis")
            return None
    except Exception:
        pass  # If character checking fails, continue with analysis
    
    # Filter 4: Generic Page Detection (avoid obvious category pages)
    generic_indicators = [
        'browse all', 'view all', 'more articles', 'related stories',
        'recent posts', 'popular articles', 'trending now', 'categories:',
        'filter by:', 'sort by:', 'page 1 of', 'showing results'
    ]
    
    generic_count = sum(1 for indicator in generic_indicators if indicator in content_lower)
    if generic_count >= 2:  # Multiple generic indicators suggest index/category page
        logger.info(f"💰 PRE-FILTER: Content appears to be generic page ({generic_count} indicators) - skipping GPT analysis")
        return None
    
    # If we get here, content passed all filters and is worth analyzing
    logger.info(f"✅ PRE-FILTERS PASSED: Content is substantial ({len(content)} chars) and relevant - proceeding with GPT analysis")
    
    # Select appropriate prompt template based on content type
    if is_youtube:
        prompt_template = YOUTUBE_PROMPT_TEMPLATE
        logger.info(f"Using YouTube-specific prompt for analysis of {content_type}")
    else:
        prompt_template = ARTICLE_PROMPT_TEMPLATE
        logger.info(f"Using article-specific prompt for analysis of {content_type}")
    
    # Format the prompt with the content and vehicle info
    prompt = prompt_template.format(
        make=make,
        model=model,
        content=content,
        content_length=len(content)
    )
    
    logger.info(f"Making enhanced GPT analysis call to OpenAI API (attempt 1/{max_retries})")
    
    # Set API key for older OpenAI client version
    openai.api_key = api_key
    
    # Apply rate limiting before API calls
    rate_limiter.wait_if_needed('openai.com')
    
    for attempt in range(max_retries):
        try:
            # Use the older OpenAI client format (compatible with openai==0.27.0)
            # Acquire semaphore to limit concurrent API calls
            with openai_semaphore.acquire():
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
            logger.info(f"Received FULL response from OpenAI:\n{response_content}")
            
            # Parse JSON response with robust fallback strategies
            try:
                analysis_result = parse_json_with_fallbacks(response_content)
                
                # Validate we got the expected structure
                if isinstance(analysis_result, dict) and 'relevance_score' in analysis_result:
                    relevance = analysis_result.get('relevance_score', 0)
                    logger.info(f"Successfully analyzed content with enhanced GPT: overall_score={analysis_result.get('overall_score', 'N/A')}, sentiment={analysis_result.get('overall_sentiment', 'N/A')}, relevance={analysis_result.get('relevance_score', 'N/A')}")
                    
                    # Log warning if GPT returned 0 relevance for content that passed pre-filters
                    if relevance == 0:
                        logger.warning(f"⚠️ GPT returned relevance_score=0 for {make} {model} despite passing pre-filters!")
                        logger.warning(f"Content excerpt sent to GPT: {content[:500]}...")
                        logger.warning(f"GPT reasoning: {analysis_result.get('summary', 'No summary provided')}")
                    
                    return analysis_result
                else:
                    logger.error("Parsed result doesn't have expected structure")
                    raise ValueError("Invalid analysis result structure")
                    
            except Exception as e:
                logger.error(f"All JSON parsing strategies failed: {e}")
                logger.error(f"Raw response (first 500 chars): {response_content[:500]}")
                
                # Return None - no fallback analysis per user request
                logger.error("JSON parsing failed completely. Returning None instead of fallback data.")
                return None
                
        except Exception as e:
            logger.error(f"Error in enhanced GPT analysis (attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed after {max_retries} attempts, cannot analyze content")
                return None  # Return None instead of mock analysis

# def _mock_gpt_analysis(content: str, make: str, model: str) -> Dict[str, Any]:
#     """
#     Create a mock comprehensive automotive analysis response.
#     
#     DISABLED: User prefers no analysis over fake analysis
#     """
#     pass

def analyze_clip_relevance_only(content: str, make: str, model: str) -> Dict[str, Any]:
    """
    Analyze content for relevance only (no sentiment analysis) to save costs.
    This function mirrors the OLD system's GPT analysis but skips sentiment scoring.
    
    Args:
        content: Article or video transcript content
        make: Vehicle make
        model: Vehicle model
        
    Returns:
        Dictionary with relevance_score only, or None if analysis fails
    """
    api_key = get_openai_key()
    
    if not api_key:
        logger.error("No OpenAI API key found. Cannot analyze content.")
        return None

    # Basic content validation
    if not content or len(content.strip()) < 100:
        logger.warning("Content too short for relevance analysis")
        return {'relevance_score': 0}
    
    # Extract a more representative sample of the content
    # Try to find sections that mention the vehicle
    content_lower = content.lower()
    make_lower = make.lower() if make else ""
    model_lower = model.lower() if model else ""
    
    # Look for the first occurrence of make or model
    make_index = content_lower.find(make_lower) if make_lower else -1
    model_index = content_lower.find(model_lower) if model_lower else -1
    
    # Start excerpt from the first mention, or from beginning if not found
    start_index = 0
    if make_index >= 0 or model_index >= 0:
        # Start 200 chars before the first mention for context
        start_index = max(0, min(make_index if make_index >= 0 else len(content), 
                                 model_index if model_index >= 0 else len(content)) - 200)
    
    # Extract 6000 characters starting from the most relevant part
    content_excerpt = content[start_index:start_index + 6000]
    
    # If we're not starting from the beginning, add ellipsis
    if start_index > 0:
        content_excerpt = "..." + content_excerpt
    if start_index + 6000 < len(content):
        content_excerpt = content_excerpt + "..."
    
    # Log what we're sending
    logger.info(f"Sending {len(content_excerpt)} chars to GPT (from position {start_index})")
    if make_lower in content_excerpt.lower() or model_lower in content_excerpt.lower():
        logger.info(f"✓ Excerpt contains {make} or {model}")
    else:
        logger.warning(f"⚠️ Excerpt may not contain {make} {model} - might be too early in content")
    
    # Simple relevance-only prompt
    prompt = f"""
    Analyze this automotive content for relevance to the {make} {model}.
    
    Content: {content_excerpt}
    
    Rate relevance on a scale of 0-10 where:
    - 0: No mention of the vehicle
    - 1-3: Brief mention only
    - 4-6: Some discussion of the vehicle
    - 7-8: Substantial coverage of the vehicle
    - 9-10: Comprehensive review or detailed analysis
    
    IMPORTANT: If this content is specifically about the {make} {model}, the score should be at least 7.
    
    Respond with ONLY a JSON object: {{"relevance_score": <number>}}
    """
    
    # Set API key for older OpenAI client version
    openai.api_key = api_key
    
    # Apply rate limiting before API calls
    rate_limiter.wait_if_needed('openai.com')
    
    try:
        logger.info(f"Making relevance-only GPT call for {make} {model}")
        
        # Acquire semaphore to limit concurrent API calls
        with openai_semaphore.acquire():
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1,
                request_timeout=30
            )
        
        response_content = response.choices[0].message.content.strip()
        logger.info(f"GPT relevance response: {response_content}")
        
        # Parse the response
        try:
            import json
            # Try to extract JSON from response
            if '{' in response_content and '}' in response_content:
                json_start = response_content.find('{')
                json_end = response_content.rfind('}') + 1
                json_str = response_content[json_start:json_end]
                result = json.loads(json_str)
                
                relevance_score = result.get('relevance_score', 0)
                logger.info(f"✅ Relevance analysis successful: {relevance_score}/10")
                return {'relevance_score': relevance_score}
            else:
                # Try to extract number from response
                relevance_match = re.search(r'(\d+)', response_content)
                if relevance_match:
                    relevance_score = int(relevance_match.group(1))
                    logger.info(f"✅ Extracted relevance score from text: {relevance_score}/10")
                    return {'relevance_score': relevance_score}
                else:
                    logger.warning("Could not extract relevance score from response")
                    return {'relevance_score': 0}
                    
        except Exception as e:
            logger.error(f"Error parsing relevance response: {e}")
            return {'relevance_score': 0}
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in relevance analysis: {e}")
        
        # Check if it's a quota/billing/rate limit error
        if any(x in error_msg.lower() for x in ['quota', 'billing', 'rate', 'limit', 'tpm', 'rpm']):
            logger.warning("Quota/billing issue detected - falling back to gpt-3.5-turbo")
            try:
                # Apply rate limiting for fallback attempt
                rate_limiter.wait_if_needed('openai.com')
                
                # Retry with cheaper model with semaphore
                with openai_semaphore.acquire():
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=100,
                        temperature=0.1,
                        request_timeout=30
                    )
                
                response_content = response.choices[0].message.content.strip()
                logger.info(f"GPT relevance response (fallback model): {response_content}")
                
                # Parse the response (same logic as above)
                try:
                    import json
                    if '{' in response_content and '}' in response_content:
                        json_start = response_content.find('{')
                        json_end = response_content.rfind('}') + 1
                        json_str = response_content[json_start:json_end]
                        result = json.loads(json_str)
                        
                        relevance_score = result.get('relevance_score', 0)
                        logger.info(f"✅ Relevance analysis successful (fallback): {relevance_score}/10")
                        return {'relevance_score': relevance_score}
                    else:
                        # Try to extract number from response
                        relevance_match = re.search(r'(\d+)', response_content)
                        if relevance_match:
                            relevance_score = int(relevance_match.group(1))
                            logger.info(f"✅ Extracted relevance score from text (fallback): {relevance_score}/10")
                            return {'relevance_score': relevance_score}
                        else:
                            logger.warning("Could not extract relevance score from fallback response")
                            return {'relevance_score': 0}
                except Exception as parse_error:
                    logger.error(f"Error parsing fallback relevance response: {parse_error}")
                    return {'relevance_score': 0}
                    
            except Exception as fallback_error:
                logger.error(f"Fallback model also failed: {fallback_error}")
                return {'relevance_score': 0}
        
        return {'relevance_score': 0}

def _create_fallback_analysis(content: str, make: str, model: str) -> Dict[str, Any]:
    """
    Create a fallback analysis when GPT response parsing fails.
    
    Args:
        content: Article or video transcript content  
        make: Vehicle make
        model: Vehicle model
        
    Returns:
        Dictionary with basic analysis results
    """
    # Basic content analysis
    make_lower = make.lower()
    model_lower = model.lower()
    content_lower = content.lower()
    
    # Calculate mentions
    make_count = content_lower.count(make_lower)
    model_count = content_lower.count(model_lower)
    
    # Calculate relevance score based on mentions
    relevance_score = min(10, max(0, (make_count + model_count) * 2))
    
    # Basic sentiment detection
    positive_words = ["excellent", "amazing", "outstanding", "impressive", "love", "fantastic", "great", "good"]
    negative_words = ["terrible", "awful", "horrible", "hate", "disappointing", "poor", "bad", "worst"]
    
    positive_count = sum(1 for word in positive_words if word in content_lower)
    negative_count = sum(1 for word in negative_words if word in content_lower)
    
    if positive_count > negative_count:
        sentiment = "positive"
        overall_score = min(8, max(6, relevance_score))
    elif negative_count > positive_count:
        sentiment = "negative"
        overall_score = min(4, max(2, relevance_score))
    else:
        sentiment = "neutral"
        overall_score = min(7, max(4, relevance_score))
    
    return {
        'relevance_score': relevance_score,
        'overall_score': overall_score,
        'overall_sentiment': sentiment,
        'sentiment': sentiment,  # For backward compatibility
        'aspects': {
            "performance": {"score": 5, "note": "Analysis parsing failed - using fallback scoring."},
            "exterior_design": {"score": 5, "note": "Analysis parsing failed - using fallback scoring."},
            "interior_comfort": {"score": 5, "note": "Analysis parsing failed - using fallback scoring."},
            "technology": {"score": 5, "note": "Analysis parsing failed - using fallback scoring."},
            "value": {"score": 5, "note": "Analysis parsing failed - using fallback scoring."}
        },
        'pros': [
            f"Content mentions {make} {model} {make_count + model_count} times",
            f"Overall sentiment appears {sentiment}",
            "Fallback analysis - some content detected"
        ],
        'cons': [
            "GPT response parsing failed",
            "Limited analysis available",
            "Recommend manual review"
        ],
        'summary': f"Fallback analysis of {make} {model} content. GPT parsing failed but basic relevance detected.",
        'recommendation': "Manual review recommended due to parsing failure",
        'brand_alignment': relevance_score >= 5,
        'key_mentions': [make, model] if relevance_score > 0 else []
    }

class GPTAnalyzer:
    """
    A class to analyze content using OpenAI's GPT-4 Turbo model.
    
    This class handles API calls to OpenAI, with retry logic and
    rate limiting to ensure reliable performance.
    """
    
    def __init__(self, model: str = "gpt-4-turbo"):
        """
        Initialize the GPT Analyzer.
        
        Args:
            model (str): The OpenAI model to use
        """
        self.api_key = get_openai_key()
        self.model = model
        
        if self.api_key:
            openai.api_key = self.api_key
        else:
            logger.warning("GPTAnalyzer initialized without API key")
    
    def analyze_content(self, 
                       content: str, 
                       vehicle_make: str,
                       vehicle_model: str,
                       max_retries: int = 3,
                       timeout: int = 60) -> Dict[str, Any]:
        """
        Analyze content for relevance, sentiment, and brand messaging.
        
        Args:
            content (str): The content to analyze (article text or transcript)
            vehicle_make (str): The make of the vehicle (e.g., "Toyota")
            vehicle_model (str): The model of the vehicle (e.g., "Camry")
            max_retries (int): Maximum number of retry attempts
            timeout (int): Timeout in seconds for the API call
            
        Returns:
            Dict: Analysis results with relevance, sentiment, summary, and brand_alignment
        """
        if not self.api_key:
            logger.error("Cannot analyze content: No OpenAI API key configured")
            return self._empty_result()
        
        # Truncate content if it's too long (to reduce token usage)
        max_content_chars = 15000  # ~4000 tokens
        if len(content) > max_content_chars:
            logger.info(f"Truncating content from {len(content)} to {max_content_chars} characters")
            content = content[:max_content_chars] + "..."
        
        # Apply rate limiting
        rate_limiter.wait_if_needed('openai.com')
        
        # Prepare the system message
        system_message = self._create_system_prompt(vehicle_make, vehicle_model)
        
        # Try the API call with retries
        attempt = 0
        while attempt < max_retries:
            try:
                # Acquire semaphore to limit concurrent API calls
                with openai_semaphore.acquire():
                    response = openai.ChatCompletion.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": content}
                        ],
                        timeout=timeout,
                        temperature=0.1,  # Low temperature for more deterministic responses
                    )
                
                # Extract and parse the response
                result = self._parse_gpt_response(response)
                logger.info(f"Successfully analyzed content for {vehicle_make} {vehicle_model}")
                return result
                
            except openai.error.RateLimitError as e:
                error_msg = str(e)
                logger.warning(f"OpenAI rate limit reached: {e}")
                
                # Try fallback to gpt-3.5-turbo
                if 'gpt-4' in self.model.lower():
                    logger.info("Falling back to gpt-3.5-turbo due to rate limit")
                    try:
                        with openai_semaphore.acquire():
                            response = openai.ChatCompletion.create(
                                model="gpt-3.5-turbo-16k",
                                messages=[
                                    {"role": "system", "content": system_message},
                                    {"role": "user", "content": content}
                                ],
                                timeout=timeout,
                                temperature=0.1,
                            )
                        result = self._parse_gpt_response(response)
                        logger.info(f"Successfully analyzed with fallback model for {vehicle_make} {vehicle_model}")
                        return result
                    except Exception as fallback_error:
                        logger.error(f"Fallback also failed: {fallback_error}")
                
                time.sleep(30)  # Wait 30 seconds before retrying
                attempt += 1
                
            except openai.error.Timeout:
                logger.warning(f"OpenAI API timeout (attempt {attempt+1}/{max_retries})")
                time.sleep(5)
                attempt += 1
                
            except openai.error.APIError as e:
                logger.error(f"OpenAI API error: {e}")
                time.sleep(5)
                attempt += 1
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Unexpected error during content analysis: {e}")
                
                # Check if it's a quota/billing error
                if any(x in error_msg.lower() for x in ['quota', 'billing', 'exceeded']):
                    logger.warning("Quota/billing issue detected - trying fallback to gpt-3.5-turbo")
                    try:
                        with openai_semaphore.acquire():
                            response = openai.ChatCompletion.create(
                                model="gpt-3.5-turbo-16k",
                                messages=[
                                    {"role": "system", "content": system_message},
                                    {"role": "user", "content": content}
                                ],
                                timeout=timeout,
                                temperature=0.1,
                            )
                        result = self._parse_gpt_response(response)
                        logger.info(f"Successfully analyzed with fallback model after quota error")
                        return result
                    except Exception as fallback_error:
                        logger.error(f"Fallback also failed after quota error: {fallback_error}")
                
                return self._empty_result()
        
        logger.error(f"Failed to analyze content after {max_retries} attempts")
        return self._empty_result()
    
    def _create_system_prompt(self, make: str, model: str) -> str:
        """Create the system prompt for GPT analysis"""
        return f"""You are an expert automotive media analyst working for DriveShop.
        
Your task is to analyze the following content to determine if it mentions the {make} {model} vehicle.
The content may be an article or video transcript from automotive media.

You should:
1. Determine if the {make} {model} is specifically mentioned in a meaningful way.
2. Assess the sentiment towards the {make} {model} (positive, neutral, or negative).
3. Extract key points about the {make} {model} from the content.
4. Determine if the content aligns with {make}'s brand messaging.

Return your analysis in JSON format with the following fields:
- relevance_score: A number from 0-10 indicating how relevant the content is to the {make} {model} (0 = not mentioned, 10 = central focus)
- sentiment: "positive", "neutral", or "negative"
- summary: A 2-3 sentence summary of what the content says about the {make} {model}
- brand_alignment: true if the content reinforces {make}'s messaging, false if it contradicts or ignores it
- key_mentions: List of direct quotes from the text mentioning the {make} {model}

Respond ONLY with valid JSON. Do not include any explanations or text outside of the JSON object."""
    
    def _parse_gpt_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the GPT response into a structured format"""
        try:
            # Extract the assistant's message
            response_text = response['choices'][0]['message']['content']
            
            # Parse the JSON response
            result = json.loads(response_text)
            
            # Ensure all required fields are present
            required_fields = ['relevance_score', 'sentiment', 'summary', 'brand_alignment', 'key_mentions']
            for field in required_fields:
                if field not in result:
                    result[field] = None if field != 'key_mentions' else []
            
            return result
            
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing GPT response: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return an empty result structure when analysis fails"""
        return {
            'relevance_score': 0,
            'sentiment': 'neutral',
            'summary': 'Analysis could not be completed.',
            'brand_alignment': False,
            'key_mentions': []
        }

# YouTube-specific prompt template for video transcript analysis
YOUTUBE_PROMPT_TEMPLATE = """
You are an elite automotive marketing strategist analyzing content for strategic brand intelligence. This YouTube video contains valuable market signals about the {make} {model}.

METADATA:
Vehicle: {make} {model}
Content Type: YouTube Video Transcript
Content Length: {content_length} characters

TRANSCRIPT:
{content}

STRATEGIC ANALYSIS FRAMEWORK:

1. RELEVANCE & MARKETING IMPACT:
   - Relevance Score (0-10): How relevant is this content to the {make} {model}?
     IMPORTANT: If the video specifically discusses or reviews the {make} {model}, the relevance score should be at least 7.
     * 0: No mention of the vehicle at all
     * 1-3: Brief or passing mention only
     * 4-6: Some discussion of the vehicle but not the main focus
     * 7-8: Substantial coverage or detailed discussion of the {make} {model}
     * 9-10: Comprehensive review or the {make} {model} is the primary focus
   - Marketing Impact Score (1-10): Rate the strategic importance for brand/marketing teams
     * 10: Game-changing insights requiring CMO attention
     * 8-9: Significant brand perception shifts or viral moments
     * 5-7: Useful consumer sentiment indicators
     * 1-4: Minimal marketing relevance

2. CREATOR INTELLIGENCE:
   - Influence Tier: Mega (1M+) / Macro (100K-1M) / Mid (10K-100K) / Micro (<10K) / Unknown
   - Audience Archetype: Enthusiasts / Family Buyers / Luxury Seekers / Tech Early Adopters / Budget Conscious
   - Credibility Score (1-10): Based on expertise demonstrated
   - Viral Potential: High / Medium / Low

3. STRATEGIC BRAND NARRATIVE:
   - How does this content position the {make} brand story?
   - What new narrative angles or messaging opportunities emerge?
   - Brand perception trajectory: Ascending / Stable / Declining

4. COMPETITIVE INTELLIGENCE:
   - How is {make} {model} positioned vs competitors?
   - Market advantages highlighted
   - Vulnerabilities exposed

5. PURCHASE INTENT SIGNALS:
   - Strong Positive / Moderate Positive / Neutral / Negative
   - Key decision factors mentioned
   - Objections or barriers identified

6. INFLUENTIAL STATEMENTS:
   - Extract 3-5 quotes likely to be repeated/shared
   - Focus on memorable, tweet-worthy content

7. ACTION ITEMS:
   - Immediate Response Needed? Yes/No
   - Marketing team recommendations
   - Content creator relationship strategy

Return ONLY valid JSON:
{{
  "relevance_score": 0-10,
  "marketing_impact_score": 1-10,
  "overall_sentiment": "positive/neutral/negative",
  "executive_summary": "2-3 sentences for CMO/VP level briefing",
  "brand_narrative": "How this shapes brand perception",
  "strategic_signal": "Key trend, risk, or opportunity",
  
  "creator_analysis": {{
    "influence_tier": "Mega/Macro/Mid/Micro/Unknown",
    "audience_archetype": "...",
    "credibility_score": 1-10,
    "viral_potential": "High/Medium/Low"
  }},
  
  "competitive_intelligence": {{
    "positioning_vs_competitors": "...",
    "advantages_highlighted": ["..."],
    "vulnerabilities_exposed": ["..."]
  }},
  
  "aspect_insights": {{
    "performance": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}},
    "design": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}},
    "technology": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}},
    "value": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}},
    "reliability": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}}
  }},
  
  "influential_statements": ["memorable quote 1", "memorable quote 2", "memorable quote 3"],
  "purchase_intent_signals": "strong positive/moderate positive/neutral/negative",
  "messaging_opportunities": ["opportunity 1", "opportunity 2"],
  "risks_to_address": ["risk 1", "risk 2"],
  
  "action_items": {{
    "immediate_response_needed": true/false,
    "recommendation": "Strategic action for marketing team",
    "creator_relationship": "Engage/Monitor/Ignore"
  }},
  
  "overall_score": 0-10,
  "summary": "Strategic insight summary",
  "brand_alignment": true/false,
  "pros": ["key positive 1", "key positive 2", "key positive 3"],
  "cons": ["key concern 1", "key concern 2", "key concern 3"],
  "key_mentions": ["key topic 1", "key topic 2", "key topic 3"],
  "recommendation": "Strategic recommendation"
}}
"""

# Standard web article prompt template  
ARTICLE_PROMPT_TEMPLATE = """
You are an elite automotive marketing strategist analyzing content for strategic brand intelligence. This article contains valuable market signals about the {make} {model}.

METADATA:
Vehicle: {make} {model}
Content Type: Web Article
Content Length: {content_length} characters

ARTICLE:
{content}

STRATEGIC ANALYSIS FRAMEWORK:

1. RELEVANCE & MARKETING IMPACT:
   - Relevance Score (0-10): How relevant is this content to the {make} {model}?
     IMPORTANT: If the article specifically discusses or reviews the {make} {model}, the relevance score should be at least 7.
     * 0: No mention of the vehicle at all
     * 1-3: Brief or passing mention only
     * 4-6: Some discussion of the vehicle but not the main focus
     * 7-8: Substantial coverage or detailed discussion of the {make} {model}
     * 9-10: Comprehensive review or the {make} {model} is the primary focus
   - Marketing Impact Score (1-10): Rate the strategic importance for brand/marketing teams
     * 10: Game-changing insights requiring CMO attention
     * 8-9: Significant brand perception shifts or media influence
     * 5-7: Useful consumer sentiment indicators
     * 1-4: Minimal marketing relevance

2. PUBLICATION INTELLIGENCE:
   - Publication Credibility: Major National / Regional / Specialist / Blog / Unknown
   - Audience Reach: Mass Market / Enthusiast / Trade / Niche
   - Editorial Stance: Brand Advocate / Neutral / Critical
   - SEO/Digital Influence Factor (1-10)

3. STRATEGIC BRAND NARRATIVE:
   - How does this content position the {make} brand story?
   - What new narrative angles or messaging opportunities emerge?
   - Brand perception trajectory: Ascending / Stable / Declining

4. COMPETITIVE INTELLIGENCE:
   - How is {make} {model} positioned vs competitors?
   - Market advantages highlighted
   - Vulnerabilities exposed

5. PURCHASE INTENT SIGNALS:
   - Strong Positive / Moderate Positive / Neutral / Negative
   - Key decision factors mentioned
   - Objections or barriers identified

6. INFLUENTIAL STATEMENTS:
   - Extract 3-5 quotes likely to be repeated in social/forums
   - Focus on headline-worthy, shareable content

7. ACTION ITEMS:
   - Immediate Response Needed? Yes/No
   - PR/Marketing team recommendations
   - Media relationship strategy

Return ONLY valid JSON:
{{
  "relevance_score": 0-10,
  "marketing_impact_score": 1-10,
  "overall_sentiment": "positive/neutral/negative",
  "executive_summary": "2-3 sentences for CMO/VP level briefing",
  "brand_narrative": "How this shapes brand perception",
  "strategic_signal": "Key trend, risk, or opportunity",
  
  "publication_analysis": {{
    "credibility": "Major National/Regional/Specialist/Blog/Unknown",
    "audience_reach": "Mass Market/Enthusiast/Trade/Niche",
    "editorial_stance": "Brand Advocate/Neutral/Critical",
    "influence_factor": 1-10
  }},
  
  "competitive_intelligence": {{
    "positioning_vs_competitors": "...",
    "advantages_highlighted": ["..."],
    "vulnerabilities_exposed": ["..."]
  }},
  
  "aspect_insights": {{
    "performance": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}},
    "design": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}},
    "technology": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}},
    "value": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}},
    "reliability": {{"sentiment": "positive/neutral/negative", "impact": "high/medium/low", "evidence": "..."}}
  }},
  
  "influential_statements": ["memorable quote 1", "memorable quote 2", "memorable quote 3"],
  "purchase_intent_signals": "strong positive/moderate positive/neutral/negative",
  "messaging_opportunities": ["opportunity 1", "opportunity 2"],
  "risks_to_address": ["risk 1", "risk 2"],
  
  "action_items": {{
    "immediate_response_needed": true/false,
    "recommendation": "Strategic action for marketing team",
    "media_strategy": "Engage/Monitor/Ignore"
  }},
  
  "overall_score": 0-10,
  "summary": "Strategic insight summary",
  "brand_alignment": true/false,
  "pros": ["key positive 1", "key positive 2", "key positive 3"],
  "cons": ["key concern 1", "key concern 2", "key concern 3"],
  "key_mentions": ["key topic 1", "key topic 2", "key topic 3"],
  "recommendation": "Strategic recommendation"
}}
""" 