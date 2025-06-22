#!/usr/bin/env python3
"""
CreatorIQ Header Extractor Tool

This tool helps you manually input your browser authentication headers
so we can access the CreatorIQ GraphQL API.
"""

import json
import os
from pathlib import Path

def collect_headers_interactively():
    """
    Interactive tool to collect authentication headers from the user
    """
    print("🔐 CreatorIQ Authentication Header Collector")
    print("=" * 50)
    print()
    print("We need to collect your browser's authentication headers to access CreatorIQ.")
    print("Please follow these steps:")
    print()
    print("1. Open your CreatorIQ report in Chrome/Firefox")
    print("2. Open DevTools (F12)")
    print("3. Go to Network tab")
    print("4. Refresh the page (Ctrl+R or Cmd+R)")
    print("5. Look for a request to 'app.creatoriq.com/api/reporting/graphql'")
    print("6. Right-click on that request → Copy → Copy as cURL")
    print("7. Paste the cURL command below")
    print()
    
    # Method 1: cURL paste
    print("METHOD 1: Paste cURL command")
    print("-" * 30)
    curl_command = input("Paste your cURL command here (or press Enter to skip): ").strip()
    
    if curl_command:
        try:
            headers = parse_curl_command(curl_command)
            if headers:
                save_headers(headers)
                print("✅ Headers extracted and saved!")
                return headers
        except Exception as e:
            print(f"❌ Error parsing cURL: {e}")
    
    # Method 2: Manual input
    print("\nMETHOD 2: Manual header input")
    print("-" * 30)
    print("If cURL didn't work, let's collect headers manually:")
    print()
    
    headers = {}
    
    # Collect essential headers
    essential_headers = [
        ("Authorization", "Look for 'Authorization: Bearer ...' in the request headers"),
        ("Cookie", "Copy the entire Cookie header value"),
        ("X-CSRF-Token", "Look for X-CSRF-Token or similar"),
        ("User-Agent", "Copy the User-Agent header"),
        ("Referer", "Should be your CreatorIQ report URL")
    ]
    
    for header_name, description in essential_headers:
        print(f"\n{header_name}:")
        print(f"  {description}")
        value = input(f"  Enter {header_name} (or press Enter to skip): ").strip()
        if value:
            headers[header_name] = value
    
    if headers:
        save_headers(headers)
        print("✅ Headers collected and saved!")
        return headers
    else:
        print("❌ No headers collected. Please try again.")
        return None

def parse_curl_command(curl_command):
    """
    Parse a cURL command to extract headers
    """
    headers = {}
    lines = curl_command.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.startswith('-H ') or line.startswith('--header '):
            # Extract header from -H 'Header: Value' format
            header_part = line.split(' ', 1)[1].strip()
            if header_part.startswith("'") and header_part.endswith("'"):
                header_part = header_part[1:-1]
            elif header_part.startswith('"') and header_part.endswith('"'):
                header_part = header_part[1:-1]
            
            if ':' in header_part:
                key, value = header_part.split(':', 1)
                headers[key.strip()] = value.strip()
    
    return headers

def save_headers(headers):
    """
    Save headers to a JSON file for use by the GraphQL client
    """
    headers_file = Path("data/creatoriq_headers.json")
    headers_file.parent.mkdir(exist_ok=True)
    
    with open(headers_file, 'w') as f:
        json.dump(headers, f, indent=2)
    
    print(f"Headers saved to: {headers_file}")

def load_saved_headers():
    """
    Load previously saved headers
    """
    headers_file = Path("data/creatoriq_headers.json")
    if headers_file.exists():
        with open(headers_file, 'r') as f:
            return json.load(f)
    return None

def main():
    """
    Main function to run the header collector
    """
    print("🚀 Starting CreatorIQ Header Extractor...")
    print()
    
    # Check if we already have saved headers
    existing_headers = load_saved_headers()
    if existing_headers:
        print("📁 Found existing headers:")
        for key in existing_headers.keys():
            print(f"  - {key}")
        print()
        
        use_existing = input("Use existing headers? (y/n): ").strip().lower()
        if use_existing == 'y':
            print("✅ Using existing headers!")
            return existing_headers
    
    # Collect new headers
    return collect_headers_interactively()

if __name__ == "__main__":
    headers = main()
    if headers:
        print("\n🎉 Ready to test CreatorIQ API access!")
        print("Run: python -m src.creatoriq.graphql_client")
    else:
        print("\n❌ No headers collected. Please try again.") 