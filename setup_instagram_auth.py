#!/usr/bin/env python3
"""
Setup Instagram authentication for scraping
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Instagram Authentication Setup")
print("=" * 50)

print("\n⚠️  Instagram requires authentication to access most content")
print("Without authentication, Instagram blocks most requests.\n")

print("To set up authentication, you need to:")
print("\n1. Create or use an Instagram account (preferably dedicated for scraping)")
print("2. Set environment variables:\n")

print("On macOS/Linux:")
print('export INSTAGRAM_USERNAME="your_username"')
print('export INSTAGRAM_PASSWORD="your_password"')
print('export INSTAGRAM_SESSION_FILE=".instaloader_session"\n')

print("On Windows:")
print('set INSTAGRAM_USERNAME=your_username')
print('set INSTAGRAM_PASSWORD=your_password')
print('set INSTAGRAM_SESSION_FILE=.instaloader_session\n')

print("Current status:")
print(f"INSTAGRAM_USERNAME: {'✅ Set' if os.getenv('INSTAGRAM_USERNAME') else '❌ Not set'}")
print(f"INSTAGRAM_PASSWORD: {'✅ Set' if os.getenv('INSTAGRAM_PASSWORD') else '❌ Not set'}")

print("\n💡 Tips:")
print("- Use a dedicated account to avoid issues with your personal account")
print("- Instagram may require 2FA or challenge questions on first login")
print("- The session file saves your login to avoid repeated authentication")
print("- Be careful with rate limits - Instagram is very strict")

print("\n🔧 Testing Direct Reel Access (works better without auth):")
print("If you have a direct Reel URL, we can try that instead.")
print("Direct URLs sometimes work without authentication.\n")

# Example of testing with a direct URL
example_url = input("Enter a direct Instagram Reel URL (or press Enter to skip): ").strip()

if example_url and ('instagram.com/reel/' in example_url or 'instagram.com/p/' in example_url):
    print(f"\n🔍 Testing direct URL: {example_url}")
    
    from src.utils.instagram_handler import process_instagram_post
    
    try:
        result = process_instagram_post(example_url)
        
        if result:
            print("\n✅ Successfully extracted data!")
            print(f"Creator: @{result.get('creator_handle')}")
            print(f"Caption: {result.get('caption', '')[:200]}...")
            if result.get('hashtags'):
                print(f"Hashtags: {', '.join(result['hashtags'][:10])}")
        else:
            print("\n❌ Failed to extract data (likely needs authentication)")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
else:
    print("\nTo test profile scanning, please set up authentication first.")