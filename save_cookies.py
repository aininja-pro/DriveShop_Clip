#!/usr/bin/env python3
"""
Simple script to save CreatorIQ cookies for authentication
"""

import json
import os
from pathlib import Path

# Paste your cookie string from the browser console here
# Replace the empty string below with your actual cookie data
COOKIE_STRING = ""

def save_cookies_to_file(cookie_string):
    """
    Save the cookie string to a file for use by our CreatorIQ client
    """
    if not cookie_string.strip():
        print("❌ No cookie string provided. Please edit this file and add your cookies.")
        print("   Look for the line: COOKIE_STRING = \"\"")
        print("   Replace the empty quotes with your cookie data from the browser console.")
        return False
    
    # Create data directory if it doesn't exist
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Save cookies as headers format
    headers = {
        "Cookie": cookie_string.strip(),
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://report.driveshop.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site"
    }
    
    # Save to JSON file
    headers_file = data_dir / "creatoriq_headers.json"
    with open(headers_file, 'w') as f:
        json.dump(headers, f, indent=2)
    
    print(f"✅ Cookies saved to: {headers_file}")
    print("🎉 Ready to test CreatorIQ API access!")
    return True

if __name__ == "__main__":
    print("🍪 CreatorIQ Cookie Saver")
    print("=" * 30)
    
    if save_cookies_to_file(COOKIE_STRING):
        print("\nNext steps:")
        print("1. Run: python -m src.creatoriq.graphql_client")
        print("2. This will test if we can access the CreatorIQ API with your cookies")
    else:
        print("\nTo use this script:")
        print("1. Edit this file (save_cookies.py)")
        print("2. Find the line: COOKIE_STRING = \"\"")
        print("3. Paste your cookie data between the quotes")
        print("4. Run this script again: python save_cookies.py") 