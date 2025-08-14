#!/usr/bin/env python3
"""
Example: Instagram Reels Integration for DriveShop Clip Tracking

This demonstrates how to use the Instagram handler to find automotive content
from journalists and influencers on Instagram.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.instagram_handler import (
    process_instagram_post,
    search_profile_for_vehicle
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def example_process_single_reel():
    """Example: Process a single Instagram Reel"""
    print("\n=== Example 1: Process Single Reel ===")
    
    # Example Reel URL (replace with actual automotive Reel)
    reel_url = "https://www.instagram.com/reel/C1234567890/"
    
    print(f"Processing Reel: {reel_url}")
    
    result = process_instagram_post(reel_url)
    
    if result:
        print("\n✅ Successfully extracted Reel data:")
        print(f"Creator: @{result['creator_handle']} ({result['creator']})")
        print(f"Caption: {result['caption'][:200]}...")
        print(f"Hashtags: {', '.join(result['hashtags'])}")
        print(f"Engagement: {result['likes']:,} likes, {result['comments']:,} comments")
        
        if result.get('transcript'):
            print(f"\nTranscript ({result['transcript_source']}):")
            print(result['transcript'][:300] + "...")
    else:
        print("❌ Failed to process Reel")

def example_search_for_vehicle():
    """Example: Search Instagram profile for specific vehicle"""
    print("\n=== Example 2: Search Profile for Vehicle ===")
    
    # Search parameters
    profile_url = "https://www.instagram.com/carwow/"
    make = "Toyota"
    model = "GR Corolla"
    loan_start_date = datetime(2024, 1, 1)
    
    print(f"Searching {profile_url} for {make} {model}")
    print(f"Loan start date: {loan_start_date.strftime('%Y-%m-%d')}")
    
    result = search_profile_for_vehicle(
        profile_url,
        make,
        model,
        loan_start_date,
        days_forward=180
    )
    
    if result:
        print(f"\n✅ Found matching content!")
        print(f"URL: {result['url']}")
        print(f"Published: {result['published_date'].strftime('%Y-%m-%d')}")
        print(f"Caption: {result['caption'][:200]}...")
        
        # Show relevance scoring
        if 'relevance_score' in result:
            score = result['relevance_score']
            print(f"\nRelevance Score: {score['total_score']}/100")
            print(f"  Hashtags: {score['hashtag_score']}/40")
            print(f"  Caption: {score['title_score']}/30")
            print(f"  Content: {score['transcript_score']}/10")
            print(f"Recommendation: {score['recommendation']}")
    else:
        print("❌ No matching content found")

def example_batch_processing():
    """Example: Process multiple journalists' Instagram profiles"""
    print("\n=== Example 3: Batch Process Multiple Profiles ===")
    
    # Example loan data
    loans = [
        {
            'work_order': 'WO-12345',
            'make': 'Porsche',
            'model': '911 Turbo',
            'journalist': '@supercarblondie',
            'loan_date': datetime(2024, 6, 1)
        },
        {
            'work_order': 'WO-12346',
            'make': 'BMW',
            'model': 'M4',
            'journalist': '@carwow',
            'loan_date': datetime(2024, 7, 15)
        }
    ]
    
    results = []
    
    for loan in loans:
        print(f"\nProcessing loan {loan['work_order']}")
        print(f"Vehicle: {loan['make']} {loan['model']}")
        print(f"Journalist: {loan['journalist']}")
        
        # Convert handle to profile URL
        profile_url = f"https://www.instagram.com/{loan['journalist'].lstrip('@')}/"
        
        # Search for the vehicle
        result = search_profile_for_vehicle(
            profile_url,
            loan['make'],
            loan['model'],
            loan['loan_date'],
            days_forward=90
        )
        
        if result:
            print("✅ Found coverage!")
            results.append({
                'loan': loan,
                'coverage': result
            })
        else:
            print("❌ No coverage found")
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Total loans processed: {len(loans)}")
    print(f"Coverage found: {len(results)}")
    print(f"Coverage rate: {len(results)/len(loans)*100:.1f}%")

def setup_authentication():
    """Guide for setting up Instagram authentication"""
    print("\n=== Instagram Authentication Setup ===")
    
    print("\nTo use Instagram integration, set these environment variables:")
    print("1. INSTAGRAM_USERNAME - Your Instagram username")
    print("2. INSTAGRAM_PASSWORD - Your Instagram password")
    print("3. INSTAGRAM_SESSION_FILE - Path to save session (optional)")
    
    print("\nExample:")
    print("export INSTAGRAM_USERNAME='your_username'")
    print("export INSTAGRAM_PASSWORD='your_password'")
    
    print("\n⚠️  Tips:")
    print("- Use a dedicated account for scraping")
    print("- Instagram has strict rate limits")
    print("- Session is saved to avoid repeated logins")

def main():
    """Run examples"""
    print("Instagram Integration Examples for DriveShop")
    print("=" * 60)
    
    # Check authentication
    if not os.getenv('INSTAGRAM_USERNAME'):
        setup_authentication()
        print("\n❌ Please set up authentication before running examples")
        return
    
    # Run examples
    try:
        example_process_single_reel()
        example_search_for_vehicle()
        example_batch_processing()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure you have proper authentication set up")

if __name__ == "__main__":
    main()