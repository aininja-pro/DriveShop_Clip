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
        return match.group(1).strip()
    
    # If no code block found, just return the original text
    return response_text.strip()

def analyze_clip(content: str, make: str, model: str, max_retries: int = 3, url: str = None) -> Dict[str, Any]:
    """
    Analyze a clip using GPT-4 for comprehensive automotive sentiment analysis.
    
    Args:
        content: Article or video transcript content (HTML or text)
        make: Vehicle make
        model: Vehicle model
        max_retries: Maximum number of retry attempts
        url: URL of the content (for HTML extraction)
        
    Returns:
        Dictionary with comprehensive analysis results
    """
    api_key = get_openai_key()
    
    if not api_key:
        logger.warning("No OpenAI API key found. Using mock GPT analysis.")
        return _mock_gpt_analysis(content, make, model)
    
    # Check if content is HTML and extract article text if so
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
    
    # Enhanced system prompt for comprehensive automotive analysis
    system_prompt = """You are an expert automotive journalist and sentiment analyst with deep knowledge of vehicle reviews and industry standards. 

You will analyze vehicle review content and provide comprehensive sentiment analysis including overall scores, aspect breakdowns, pros/cons, and professional recommendations.

Return your analysis in JSON format exactly as shown below - no markdown formatting, no explanations, just valid JSON:

{
  "overall_score": 8,
  "overall_sentiment": "positive",
  "aspects": {
    "performance": { "score": 9, "note": "Strong acceleration and handling impress testers." },
    "exterior_design": { "score": 7, "note": "Sharp styling appeals to most but may be polarizing." },
    "interior_comfort": { "score": 8, "note": "Cabin materials and seating quality exceed expectations." },
    "technology": { "score": 6, "note": "Feature-rich but interface can be slow to respond." },
    "value": { "score": 7, "note": "Competitive pricing though options add up quickly." }
  },
  "pros": [
    "Responsive electric powertrain delivers impressive performance",
    "Premium interior materials and build quality",
    "Advanced driver assistance features work seamlessly"
  ],
  "cons": [
    "Touch-only climate controls frustrate daily use",
    "Price climbs quickly with popular option packages",
    "Infotainment system occasionally lags during startup"
  ],
  "summary": "The reviewer praises the vehicle's performance and interior quality while noting some technology quirks and pricing concerns.",
  "recommendation": "I would recommend this vehicle",
  "relevance_score": 9,
  "brand_alignment": true,
  "key_mentions": ["acceleration", "luxury interior", "driver assistance"]
}"""

    # User prompt with the content
    user_prompt = f"""Analyze this review content about the {make} {model}:

```
{content}
```

Provide comprehensive sentiment analysis following the JSON format specified in the system message. Focus on:

1. Overall Sentiment Score (1-10, where 1=very negative, 10=very positive)
2. Overall Sentiment Classification (negative/neutral/positive)
3. Aspect Analysis (performance, exterior_design, interior_comfort, technology, value) with scores 1-10 and brief notes
4. Top 3 Pros and Top 3 Cons from the review
5. 2-3 sentence Executive Summary of the review's tone
6. Professional Recommendation (recommend or not recommend)
7. Relevance Score (0-10) for how much this review focuses on the {make} {model}
8. Brand Alignment (true/false) for luxury automotive positioning
9. Key Mentions of important vehicle features discussed

Return only the JSON object with no additional text."""
    
    # Try making the API call with exponential backoff
    for attempt in range(max_retries):
        try:
            logger.info(f"Making enhanced GPT analysis call to OpenAI API (attempt {attempt + 1}/{max_retries})")
            
            # Configure OpenAI API
            openai.api_key = api_key
            
            # Make the actual API call using GPT-4 for better analysis
            response = openai.ChatCompletion.create(
                model="gpt-4",  # Upgraded to GPT-4 for better automotive analysis
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # Low temperature for consistent analysis
                max_tokens=1000   # Increased for comprehensive response
            )
            
            # Extract the response content
            response_text = response.choices[0].message.content
            logger.info(f"Received FULL response from OpenAI:\n{response_text}")
            
            # Clean the response to handle markdown code blocks
            cleaned_response = clean_json_response(response_text)
            if cleaned_response != response_text:
                logger.info(f"Cleaned JSON response from markdown formatting")
            
            try:
                # Parse the JSON response
                result = json.loads(cleaned_response)
                
                # Ensure all required fields are present with defaults
                if 'overall_score' not in result:
                    result['overall_score'] = 5
                if 'overall_sentiment' not in result:
                    result['overall_sentiment'] = 'neutral'
                if 'aspects' not in result:
                    result['aspects'] = {
                        "performance": {"score": 5, "note": "Performance not specifically discussed."},
                        "exterior_design": {"score": 5, "note": "Design not specifically discussed."},
                        "interior_comfort": {"score": 5, "note": "Interior not specifically discussed."},
                        "technology": {"score": 5, "note": "Technology not specifically discussed."},
                        "value": {"score": 5, "note": "Value proposition not specifically discussed."}
                    }
                if 'pros' not in result:
                    result['pros'] = []
                if 'cons' not in result:
                    result['cons'] = []
                if 'summary' not in result:
                    result['summary'] = f"Analysis of {make} {model} review content."
                if 'recommendation' not in result:
                    result['recommendation'] = "Insufficient information for recommendation"
                if 'relevance_score' not in result:
                    result['relevance_score'] = 0
                if 'brand_alignment' not in result:
                    result['brand_alignment'] = False
                if 'key_mentions' not in result:
                    result['key_mentions'] = []
                
                # For backward compatibility, also set the legacy 'sentiment' field
                result['sentiment'] = result['overall_sentiment']
                
                logger.info(f"Successfully analyzed content with enhanced GPT: overall_score={result.get('overall_score', 0)}, sentiment={result.get('overall_sentiment', 'neutral')}, relevance={result.get('relevance_score', 0)}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from OpenAI response: {e}")
                logger.error(f"Response was: {cleaned_response}")
                # If we can't parse the JSON, fall back to the mock for this attempt
                if attempt == max_retries - 1:
                    logger.warning("Falling back to mock GPT analysis after JSON parsing failure")
                    return _mock_gpt_analysis(content, make, model)
                # Otherwise, retry
            
        except Exception as e:
            logger.error(f"Error in enhanced GPT analysis (attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed after {max_retries} attempts, falling back to mock analysis")
                return _mock_gpt_analysis(content, make, model)

def _mock_gpt_analysis(content: str, make: str, model: str) -> Dict[str, Any]:
    """
    Create a mock comprehensive automotive analysis response.
    
    Args:
        content: Article or video transcript content
        make: Vehicle make
        model: Vehicle model
        
    Returns:
        Dictionary with comprehensive analysis results matching enhanced format
    """
    # Check if content actually mentions the make and model
    make_lower = make.lower()
    model_lower = model.lower()
    content_lower = content.lower()
    
    # Add debugging
    logger.info(f"Mock GPT analysis checking for make '{make_lower}' and model '{model_lower}' in content")
    
    # Calculate mentions
    make_count = content_lower.count(make_lower)
    model_count = content_lower.count(model_lower)
    
    logger.info(f"Found make {make_count} times and model {model_count} times")
    
    if not make_count and not model_count:
        # No mentions at all - return minimal analysis
        logger.warning("Neither make nor model found in content")
        return {
            "overall_score": 1,
            "overall_sentiment": "neutral",
            "aspects": {
                "performance": {"score": 1, "note": "Vehicle not discussed in content."},
                "exterior_design": {"score": 1, "note": "Design not mentioned in content."},
                "interior_comfort": {"score": 1, "note": "Interior not covered in content."},
                "technology": {"score": 1, "note": "Technology features not discussed."},
                "value": {"score": 1, "note": "Value proposition not addressed."}
            },
            "pros": [],
            "cons": [],
            "summary": f"This content does not appear to focus on the {make} {model}.",
            "recommendation": "Cannot provide recommendation - vehicle not adequately covered",
            "relevance_score": 0,
            "sentiment": "neutral",  # Legacy field
            "brand_alignment": False,
            "key_mentions": []
        }
    
    # Calculate relevance and overall scores
    relevance_score = min(10, max(1, (make_count + model_count * 2)))
    overall_score = min(10, max(3, relevance_score + 1))  # Slightly higher than relevance
    
    # Determine sentiment based on positive/negative keywords
    positive_keywords = ["excellent", "impressive", "outstanding", "luxurious", "premium", "refined", 
                        "comfortable", "quality", "advanced", "smooth", "responsive", "elegant", "sporty"]
    negative_keywords = ["disappointing", "subpar", "mediocre", "uncomfortable", "dated", "overpriced", 
                        "unreliable", "poor", "sluggish", "cramped", "noisy", "harsh"]
    
    positive_count = sum(1 for word in positive_keywords if word in content_lower)
    negative_count = sum(1 for word in negative_keywords if word in content_lower)
    
    if positive_count > negative_count * 1.5:
        sentiment = "positive"
        overall_score = min(10, overall_score + 2)
    elif negative_count > positive_count:
        sentiment = "negative"
        overall_score = max(1, overall_score - 2)
    else:
        sentiment = "neutral"
    
    # Generate aspect scores based on content analysis
    performance_score = 7 if any(word in content_lower for word in ["performance", "acceleration", "horsepower", "handling"]) else 5
    design_score = 6 if any(word in content_lower for word in ["design", "styling", "appearance", "looks"]) else 5
    interior_score = 8 if any(word in content_lower for word in ["interior", "cabin", "comfort", "luxury"]) else 5
    tech_score = 6 if any(word in content_lower for word in ["technology", "infotainment", "features", "tech"]) else 5
    value_score = 6 if any(word in content_lower for word in ["price", "value", "cost", "affordable"]) else 5
    
    # Adjust scores based on overall sentiment
    if sentiment == "positive":
        performance_score = min(10, performance_score + 1)
        design_score = min(10, design_score + 1)
        interior_score = min(10, interior_score + 1)
        tech_score = min(10, tech_score + 1)
        value_score = min(10, value_score + 1)
    elif sentiment == "negative":
        performance_score = max(1, performance_score - 1)
        design_score = max(1, design_score - 1)
        interior_score = max(1, interior_score - 1)
        tech_score = max(1, tech_score - 1)
        value_score = max(1, value_score - 1)
    
    # Generate pros and cons based on content
    pros = []
    cons = []
    
    if "performance" in content_lower or "acceleration" in content_lower:
        pros.append("Strong performance characteristics noted by reviewer")
    if "luxury" in content_lower or "premium" in content_lower:
        pros.append("Premium materials and luxury appointments")
    if "comfort" in content_lower:
        pros.append("Comfortable ride quality and seating")
    if "technology" in content_lower or "features" in content_lower:
        pros.append("Advanced technology and feature set")
    
    if "price" in content_lower and ("high" in content_lower or "expensive" in content_lower):
        cons.append("Higher price point than some competitors")
    if "fuel" in content_lower and any(word in content_lower for word in ["poor", "low", "bad"]):
        cons.append("Fuel economy could be improved")
    if any(word in content_lower for word in ["noise", "loud", "harsh"]):
        cons.append("Some noise or harshness issues noted")
    
    # Default pros/cons if none found
    if not pros:
        pros = [
            f"Competitive positioning in luxury {model.split()[0] if model else 'vehicle'} segment",
            "Brand reputation and build quality",
            "Comprehensive feature availability"
        ]
    
    if not cons:
        cons = [
            "Premium pricing reflects luxury positioning",
            "Some features may require option packages",
            "Market competition is increasingly strong"
        ]
    
    # Generate summary based on content type
    if "motortrend" in content_lower or "first drive" in content_lower:
        summary = f"MotorTrend's review highlights the {make} {model}'s competitive strengths in performance and luxury, while noting typical premium vehicle considerations around pricing and features."
    elif "caranddriver" in content_lower:
        summary = f"Car and Driver's analysis emphasizes the {make} {model}'s technical capabilities and market positioning within the luxury segment."
    else:
        summary = f"The review provides {sentiment} coverage of the {make} {model}, focusing on its key attributes and market position."
    
    # Determine recommendation
    if overall_score >= 7:
        recommendation = "I would recommend this vehicle"
    elif overall_score <= 4:
        recommendation = "I would not recommend this vehicle"
    else:
        recommendation = "This vehicle merits consideration based on individual priorities"
    
    # Determine brand alignment
    brand_alignment = (overall_score >= 6 and sentiment != "negative" and 
                      any(word in content_lower for word in ["luxury", "premium", "quality", "refined"]))
    
    # Extract key mentions
    key_mentions = []
    automotive_features = ["performance", "acceleration", "handling", "comfort", "luxury", "technology", 
                          "design", "interior", "safety", "efficiency", "value"]
    key_mentions = [feature for feature in automotive_features if feature in content_lower]
    
    logger.info(f"Mock comprehensive analysis: overall_score={overall_score}, sentiment={sentiment}, relevance={relevance_score}")
    
    return {
        "overall_score": overall_score,
        "overall_sentiment": sentiment,
        "aspects": {
            "performance": {"score": performance_score, "note": f"Performance characteristics {'' if performance_score > 5 else 'not '}adequately covered in review."},
            "exterior_design": {"score": design_score, "note": f"Exterior styling {'' if design_score > 5 else 'not '}discussed in detail."},
            "interior_comfort": {"score": interior_score, "note": f"Interior comfort and luxury {'' if interior_score > 5 else 'not '}emphasized by reviewer."},
            "technology": {"score": tech_score, "note": f"Technology features {'' if tech_score > 5 else 'not '}highlighted in coverage."},
            "value": {"score": value_score, "note": f"Value proposition {'' if value_score > 5 else 'not '}addressed comprehensively."}
        },
        "pros": pros[:3],  # Limit to top 3
        "cons": cons[:3],  # Limit to top 3
        "summary": summary,
        "recommendation": recommendation,
        "relevance_score": relevance_score,
        "sentiment": sentiment,  # Legacy field for backward compatibility
        "brand_alignment": brand_alignment,
        "key_mentions": key_mentions[:5]  # Limit to top 5
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
                
            except openai.error.RateLimitError:
                logger.warning("OpenAI rate limit reached, waiting before retry")
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
                logger.error(f"Unexpected error during content analysis: {e}")
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