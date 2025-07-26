"""
Smart content scoring for TikTok videos.
Prioritizes reliable signals (hashtags, title) over error-prone transcripts.
"""

from typing import Dict, Any, List
import re

def score_tiktok_relevance(video_data: Dict[str, Any], make: str, model: str) -> Dict[str, Any]:
    """
    Score a TikTok video's relevance to a specific vehicle.
    Hashtags and metadata are weighted higher than transcripts due to accuracy.
    
    Returns:
        Dictionary with score, confidence, and reasoning
    """
    score_breakdown = {
        'hashtag_score': 0,
        'title_score': 0,
        'description_score': 0,
        'transcript_score': 0,
        'total_score': 0,
        'confidence': 'low',
        'reasons': []
    }
    
    make_lower = make.lower()
    model_lower = model.lower()
    
    # Get all the content
    hashtags = [tag.lower() for tag in video_data.get('hashtags', [])]
    title = video_data.get('title', '').lower()
    description = video_data.get('description', '').lower()
    transcript = video_data.get('transcript', '').lower()
    
    # 1. HASHTAG SCORING (Most reliable - 40 points max)
    hashtag_text = ' '.join(hashtags)
    
    # Check for make in hashtags
    if make_lower in hashtag_text or any(synonym in hashtag_text for synonym in get_make_synonyms(make)):
        score_breakdown['hashtag_score'] += 20
        score_breakdown['reasons'].append(f"Make '{make}' in hashtags")
    
    # Check for model in hashtags (exact or close match)
    if model_lower.replace(' ', '') in hashtag_text.replace(' ', ''):
        score_breakdown['hashtag_score'] += 20
        score_breakdown['reasons'].append(f"Model '{model}' in hashtags (exact)")
    elif any(word in hashtag_text for word in model_lower.split() if len(word) > 3):
        score_breakdown['hashtag_score'] += 15
        score_breakdown['reasons'].append(f"Model '{model}' partially in hashtags")
    
    # 2. TITLE SCORING (Reliable - 30 points max)
    if make_lower in title:
        score_breakdown['title_score'] += 15
        score_breakdown['reasons'].append("Make in title")
    
    if model_lower in title or fuzzy_model_match(title, model):
        score_breakdown['title_score'] += 15
        score_breakdown['reasons'].append("Model in title")
    
    # 3. DESCRIPTION SCORING (Semi-reliable - 20 points max)
    # Note: Description often includes hashtags, so check non-hashtag portion
    desc_without_hashtags = re.sub(r'#\w+', '', description)
    
    if make_lower in desc_without_hashtags:
        score_breakdown['description_score'] += 10
        score_breakdown['reasons'].append("Make in description")
    
    if model_lower in desc_without_hashtags:
        score_breakdown['description_score'] += 10
        score_breakdown['reasons'].append("Model in description")
    
    # 4. TRANSCRIPT SCORING (Least reliable due to errors - 10 points max)
    if transcript:
        # Check if transcript mentions the vehicle
        make_found = make_lower in transcript or any(syn in transcript for syn in get_make_synonyms(make))
        model_found = fuzzy_model_match(transcript, model)
        
        if make_found and model_found:
            score_breakdown['transcript_score'] += 10
            score_breakdown['reasons'].append("Make and model in transcript")
        elif make_found or model_found:
            score_breakdown['transcript_score'] += 5
            score_breakdown['reasons'].append("Partial match in transcript")
    
    # Calculate total score
    total = sum([
        score_breakdown['hashtag_score'],
        score_breakdown['title_score'],
        score_breakdown['description_score'],
        score_breakdown['transcript_score']
    ])
    score_breakdown['total_score'] = total
    
    # Determine confidence level
    if total >= 60:
        score_breakdown['confidence'] = 'high'
        score_breakdown['recommendation'] = 'PROCESS - High confidence match'
    elif total >= 40:
        score_breakdown['confidence'] = 'medium'
        score_breakdown['recommendation'] = 'PROCESS - Good match'
    elif total >= 25:
        score_breakdown['confidence'] = 'low'
        score_breakdown['recommendation'] = 'REVIEW - Possible match'
    else:
        score_breakdown['confidence'] = 'none'
        score_breakdown['recommendation'] = 'SKIP - Low relevance'
    
    # Special case: If hashtags are strong but transcript is weak, still process
    if score_breakdown['hashtag_score'] >= 35 and total >= 35:
        score_breakdown['confidence'] = 'medium'
        score_breakdown['recommendation'] = 'PROCESS - Strong hashtag match'
        score_breakdown['reasons'].append("Hashtags override weak transcript")
    
    return score_breakdown

def get_make_synonyms(make: str) -> List[str]:
    """Get common synonyms for a make (simplified version)"""
    synonyms = {
        'volkswagen': ['vw'],
        'chevrolet': ['chevy'],
        'mercedes': ['mercedes-benz', 'benz', 'mb'],
    }
    return synonyms.get(make.lower(), [])

def fuzzy_model_match(text: str, model: str) -> bool:
    """Simplified fuzzy match for demonstration"""
    model_lower = model.lower()
    
    # Direct match
    if model_lower in text:
        return True
    
    # Check with spaces/hyphens removed
    model_compressed = model_lower.replace(' ', '').replace('-', '')
    text_compressed = text.replace(' ', '').replace('-', '')
    if model_compressed in text_compressed:
        return True
    
    # Check each significant word
    words = [w for w in model_lower.split() if len(w) > 3]
    if words and all(word in text for word in words):
        return True
    
    return False

# Example usage
if __name__ == "__main__":
    # The Lotus Emira example
    lotus_video = {
        'title': 'Those turbo sounds alone have me sold! 😂',
        'description': '#lotus #emira #sportscar #cars',
        'hashtags': ['lotus', 'emira', 'sportscar', 'cars'],
        'transcript': 'Behind me is a Lotus Amir, a four-cylinder...'  # Whisper error
    }
    
    print("Lotus Emira Scoring:")
    print("="*50)
    result = score_tiktok_relevance(lotus_video, 'Lotus', 'Emira')
    
    print(f"Total Score: {result['total_score']}/100")
    print(f"Confidence: {result['confidence']}")
    print(f"Recommendation: {result['recommendation']}")
    print("\nBreakdown:")
    print(f"  Hashtags: {result['hashtag_score']}/40")
    print(f"  Title: {result['title_score']}/30")
    print(f"  Description: {result['description_score']}/20")
    print(f"  Transcript: {result['transcript_score']}/10")
    print("\nReasons:")
    for reason in result['reasons']:
        print(f"  ✓ {reason}")
    
    # Example where transcript is wrong but hashtags save it
    print("\n" + "="*50)
    print("Example: Good hashtags, bad transcript")
    print("="*50)
    
    bad_transcript = {
        'title': 'Check out this car',
        'description': 'Amazing car review #mazda #cx50 #suv',
        'hashtags': ['mazda', 'cx50', 'suv', 'carreview'],
        'transcript': 'This Mazda CX15 is great...'  # Wrong model in transcript
    }
    
    result2 = score_tiktok_relevance(bad_transcript, 'Mazda', 'CX-50')
    print(f"Total Score: {result2['total_score']}/100")
    print(f"Recommendation: {result2['recommendation']}")
    print("Key insight: Hashtags had correct model, transcript had wrong model")