#!/usr/bin/env python3

import os
import sys
sys.path.append('.')

# Set environment variables
os.environ['GOOGLE_SEARCH_API_KEY'] = 'AIzaSyDqTqgxoCS6cMgYiQ4BV0M_UPbY1KSDEo8'
os.environ['GOOGLE_SEARCH_ENGINE_ID'] = 'e4388368728b74eb5'

import requests
import json

print("🎯 Finding the REAL VW Jetta Article")
print("=" * 50)

# Try more specific searches to find the actual article
search_queries = [
    'site:thegentlemanracer.com "2025 Volkswagen Jetta GLI Review"',
    'site:thegentlemanracer.com "Volkswagen Jetta GLI" -"Related Posts"',
    'site:thegentlemanracer.com "Jetta GLI" "Manual-Shifted" title',
    'site:thegentlemanracer.com "Jetta GLI" "Anthony Fongaro" inurl:jetta',
    'site:thegentlemanracer.com "2025 Jetta" review',
]

api_key = os.environ.get('GOOGLE_SEARCH_API_KEY')
search_engine_id = os.environ.get('GOOGLE_SEARCH_ENGINE_ID')

for i, query in enumerate(search_queries, 1):
    print(f"\n🔍 Search #{i}: {query}")
    
    try:
        params = {
            'key': api_key,
            'cx': search_engine_id,
            'q': query,
            'num': 5
        }
        
        response = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'items' in data:
                print(f"✅ Found {len(data['items'])} results:")
                
                for j, item in enumerate(data['items'], 1):
                    url = item.get('link', '')
                    title = item.get('title', '')
                    snippet = item.get('snippet', '')
                    
                    print(f"  Result #{j}:")
                    print(f"    📄 Title: {title}")
                    print(f"    🔗 URL: {url}")
                    print(f"    📝 Snippet: {snippet[:150]}...")
                    
                    # Check if this is the real Jetta article (not sidebar content)
                    title_lower = title.lower()
                    is_jetta_article = (
                        ('jetta' in title_lower or 'volkswagen' in title_lower or 'vw' in title_lower) and
                        ('review' in title_lower or 'test' in title_lower or 'drive' in title_lower) and
                        'dodge' not in title_lower and 'charger' not in title_lower
                    )
                    
                    if is_jetta_article:
                        print(f"    ✅ THIS LOOKS LIKE THE REAL JETTA ARTICLE!")
                    else:
                        print(f"    ❌ Probably another false positive")
                    print()
            else:
                print("❌ No results found")
        else:
            print(f"❌ API Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n💡 NEXT STEP:")
print("If we can't find the actual VW Jetta article title in search,")
print("we may need to try a different approach like RSS feeds or")
print("crawling the homepage to find recent articles by Anthony Fongaro.")
print("=" * 50) 