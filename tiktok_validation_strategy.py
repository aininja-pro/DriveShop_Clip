# Enhanced validation for TikTok clips
# This shows how to determine if a clip is worth returning

from typing import Dict, Any, Optional
from datetime import datetime

def validate_tiktok_clip(video_data: Dict[str, Any], make: str, model: str) -> Dict[str, Any]:
    """
    Validate if a TikTok video is a legitimate vehicle review worth processing.
    
    Returns validation result with confidence score and reasons.
    """
    validation = {
        'is_valid': False,
        'confidence': 0.0,
        'reasons': [],
        'flags': []
    }
    
    transcript = video_data.get('transcript', '').lower()
    title = video_data.get('title', '').lower()
    description = video_data.get('description', '').lower()
    duration = video_data.get('duration', 0)
    
    # 1. DURATION CHECK - Reviews need substance
    if duration < 15:
        validation['flags'].append('TOO_SHORT')
        validation['reasons'].append(f'Video only {duration}s - likely not a review')
    elif duration > 30:
        validation['confidence'] += 0.2
        validation['reasons'].append(f'Good duration: {duration}s')
    
    # 2. TRANSCRIPT QUALITY - Must have actual content
    word_count = len(transcript.split()) if transcript else 0
    if word_count < 50:
        validation['flags'].append('MINIMAL_CONTENT')
        validation['reasons'].append(f'Only {word_count} words - insufficient for review')
    elif word_count > 100:
        validation['confidence'] += 0.2
        validation['reasons'].append(f'Substantial content: {word_count} words')
    
    # 3. VEHICLE MENTION DENSITY - Should mention car multiple times
    make_mentions = transcript.count(make.lower()) + title.count(make.lower())
    model_mentions = sum(transcript.count(word) for word in model.lower().split())
    
    total_mentions = make_mentions + model_mentions
    if total_mentions == 0:
        validation['flags'].append('NO_VEHICLE_MENTIONS')
        validation['reasons'].append('Vehicle not mentioned in content')
        return validation  # Early exit - definitely not valid
    elif total_mentions == 1:
        validation['confidence'] += 0.1
        validation['reasons'].append('Vehicle mentioned once - possible passing reference')
    elif total_mentions >= 3:
        validation['confidence'] += 0.3
        validation['reasons'].append(f'Vehicle mentioned {total_mentions} times - likely focused review')
    
    # 4. REVIEW INDICATORS - Keywords that suggest it's a review
    review_keywords = [
        'review', 'test', 'drive', 'drove', 'driving', 'tested',
        'worth', 'price', 'cost', 'msrp', 'lease', 'buy',
        'pros', 'cons', 'like', 'dislike', 'love', 'hate',
        'interior', 'exterior', 'engine', 'performance', 'mpg',
        'features', 'technology', 'space', 'comfort', 'quality'
    ]
    
    keyword_matches = sum(1 for keyword in review_keywords if keyword in transcript)
    if keyword_matches >= 5:
        validation['confidence'] += 0.3
        validation['reasons'].append(f'Contains {keyword_matches} review keywords')
    elif keyword_matches >= 3:
        validation['confidence'] += 0.2
        validation['reasons'].append(f'Some review keywords found ({keyword_matches})')
    
    # 5. PROMOTIONAL CONTENT CHECK - Avoid dealership ads
    promo_keywords = [
        'sale', 'offer', 'discount', 'finance', 'apr', 'lease special',
        'call now', 'visit us', 'dealership', 'inventory', 'stock'
    ]
    
    promo_matches = sum(1 for keyword in promo_keywords if keyword in transcript)
    if promo_matches >= 3:
        validation['flags'].append('LIKELY_PROMOTIONAL')
        validation['confidence'] -= 0.2
        validation['reasons'].append('Appears to be dealership promotional content')
    
    # 6. COMPARISON CONTENT - High value for marketing
    comparison_keywords = ['versus', 'vs', 'compared to', 'better than', 'worse than']
    if any(keyword in transcript for keyword in comparison_keywords):
        validation['confidence'] += 0.1
        validation['reasons'].append('Contains vehicle comparisons')
    
    # 7. SENTIMENT INDICATORS - Shows opinion
    opinion_phrases = [
        'i think', 'i feel', 'i believe', 'in my opinion',
        'honestly', 'personally', 'actually', 'really'
    ]
    if any(phrase in transcript for phrase in opinion_phrases):
        validation['confidence'] += 0.1
        validation['reasons'].append('Contains personal opinions')
    
    # 8. ENGAGEMENT QUALITY - High engagement suggests valuable content
    engagement_rate = video_data.get('engagement_rate', 0)
    if engagement_rate > 0.10:  # 10%+ is exceptional
        validation['confidence'] += 0.1
        validation['reasons'].append(f'High engagement rate: {engagement_rate:.1%}')
    
    # FINAL VALIDATION
    validation['is_valid'] = validation['confidence'] >= 0.5 and len(validation['flags']) == 0
    
    # Provide recommendation
    if validation['is_valid']:
        validation['recommendation'] = 'PROCESS - High confidence vehicle review'
    elif validation['confidence'] >= 0.3:
        validation['recommendation'] = 'MANUAL_REVIEW - Possible vehicle content'
    else:
        validation['recommendation'] = 'SKIP - Low confidence or problematic content'
    
    return validation

# Example usage with the VW ID.Buzz video
def demonstrate_validation():
    """Show how validation would work on real content"""
    
    # Simulate the VW ID.Buzz video data (with full transcript)
    vw_video = {
        'title': 'Worth $67K as tested?',
        'description': '#vw #volkswagen #idbuzz #ev #familycar',
        'transcript': '''Behind me is a Volkswagen ID.Buzz, and this is almost the perfect family car. Because the doors open like a minivan, that means your kids won't ding the cars next to you, and it makes it easier to get in and out. You get a ton of space here in the second row. Even with the car seat installed, I can move the seat forward to access the third row. And once I'm back here, I get a ton of leg space, and that's with this second seat all the way back. I have overhead vents, cup holders, storage space, this cute little bus I can recline, and... That's with a car seat in the back. And if I need to shut the tailgate, but I'm too short, all I do is pull this tab. If I pull down the third row, I get a good amount of space. If I lift this up, I get storage cubbies that actually come with the car. But what if I need more space? I can remove the third row for bigger items. And putting it back in is as easy as one, two, three. You also get this gigantic glass roof that can let light in, or you can keep it out. My seats are heated and ventilated. I get a built-in leg rest, a built-in arm rest, and these seats can massage you. I get storage space down here, a touchscreen with Apple CarPlay and Android Auto. I have hidden cup holders. This center console has storage space here in the front, more in the back, and some in the middle, with removable dividers that can get ice off my windshield or open bottles. If I want an easy way to get to the third row, I can just remove the center console. I also get these adorable-looking pedals. I have a wireless charging pad. This driving display can go up and down with my steering wheel. But my favorite part is this cute little window. I have another charging port in my door. I have an area to plug in a laptop. That way I can work off the car's built-in Wi-Fi. And if I need a spot to put a dash cam, I get a USB port right up there. And if you need a place to put loose cards, I can just stick them under there. So why is it almost perfect? It's because it gets 231 miles of range.''',
        'duration': 100,
        'engagement_rate': 0.098
    }
    
    result = validate_tiktok_clip(vw_video, 'Volkswagen', 'ID.Buzz')
    
    print("VALIDATION RESULT:")
    print(f"Valid: {result['is_valid']}")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Recommendation: {result['recommendation']}")
    print("\nReasons:")
    for reason in result['reasons']:
        print(f"  ✓ {reason}")
    if result['flags']:
        print("\nFlags:")
        for flag in result['flags']:
            print(f"  ⚠️ {flag}")
    
    # Also test a bad example
    print("\n" + "="*60)
    print("Testing with a BAD example (dealership promo):")
    print("="*60)
    
    bad_video = {
        'title': 'Best deals on VW',
        'description': '#vw #sale #deals',
        'transcript': '''Come to Bob's VW for the best deals! We have ID.Buzz in stock now. 
        Special financing available, 0% APR for qualified buyers. Call now for our special 
        lease offers. Visit us today! Limited time offer on all Volkswagen models.''',
        'duration': 20,
        'engagement_rate': 0.02
    }
    
    bad_result = validate_tiktok_clip(bad_video, 'Volkswagen', 'ID.Buzz')
    print(f"\nValid: {bad_result['is_valid']}")
    print(f"Confidence: {bad_result['confidence']:.1%}")
    print(f"Recommendation: {bad_result['recommendation']}")
    print("\nFlags:")
    for flag in bad_result['flags']:
        print(f"  ⚠️ {flag}")

# Integration with existing code
def enhanced_search_channel_for_vehicle(channel_url: str, make: str, model: str, 
                                       start_date: Optional[datetime] = None, 
                                       min_confidence: float = 0.5) -> Optional[Dict[str, Any]]:
    """
    Enhanced version that validates clips before returning them.
    """
    # ... existing channel scanning code ...
    
    # After finding potential matches and extracting content:
    for video in relevant_videos:
        full_video_data = process_tiktok_video(video['url'])
        
        if full_video_data and full_video_data.get('transcript'):
            # Validate the clip
            validation = validate_tiktok_clip(full_video_data, make, model)
            
            if validation['is_valid'] and validation['confidence'] >= min_confidence:
                logger.info(f"✅ VALIDATED: {validation['recommendation']}")
                # Add validation data to response
                full_video_data['validation'] = validation
                return full_video_data
            else:
                logger.info(f"❌ REJECTED: {validation['recommendation']}")
                logger.info(f"   Confidence: {validation['confidence']:.1%}")
                continue
    
    return None