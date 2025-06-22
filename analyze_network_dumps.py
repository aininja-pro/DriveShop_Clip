#!/usr/bin/env python3
"""
Analyze captured network dumps to identify CreatorIQ post data endpoints.
"""

import json
import os
import sys
from pathlib import Path

def analyze_json_file(filepath):
    """Analyze a single JSON file and return metadata."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Calculate size
        size = len(json.dumps(data))
        
        # Try to identify structure
        data_type = type(data).__name__
        
        # Look for common post/content indicators
        content_indicators = []
        if isinstance(data, dict):
            keys = list(data.keys())
            content_indicators.extend([k for k in keys if any(term in k.lower() for term in ['post', 'content', 'media', 'publication', 'activity', 'influencer'])])
            
            # Check for arrays that might contain posts
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 10:  # Large arrays
                    content_indicators.append(f"{key}[{len(value)} items]")
        
        elif isinstance(data, list) and len(data) > 10:
            content_indicators.append(f"Array with {len(data)} items")
            
            # Sample first item to see structure
            if data and isinstance(data[0], dict):
                sample_keys = list(data[0].keys())[:5]  # First 5 keys
                content_indicators.append(f"Sample keys: {sample_keys}")
        
        return {
            'filepath': filepath,
            'size': size,
            'data_type': data_type,
            'content_indicators': content_indicators,
            'is_large': size > 10000,  # 10KB+
            'potential_posts': any(term in str(content_indicators).lower() for term in ['post', 'content', 'media', 'publication', 'activity'])
        }
        
    except Exception as e:
        return {
            'filepath': filepath,
            'size': 0,
            'data_type': 'error',
            'content_indicators': [f"Error: {e}"],
            'is_large': False,
            'potential_posts': False
        }

def main():
    """Analyze all JSON files in network dumps directories."""
    
    # Check both possible directories
    dump_dirs = [
        "data/network_dumps",
        "data/network_dumps_debug"
    ]
    
    all_files = []
    for dump_dir in dump_dirs:
        if os.path.exists(dump_dir):
            json_files = list(Path(dump_dir).glob("*.json"))
            all_files.extend(json_files)
            print(f"📁 Found {len(json_files)} JSON files in {dump_dir}")
    
    if not all_files:
        print("❌ No JSON files found in network dumps directories.")
        print("   Run test_network_capture.py first to capture network data.")
        return 1
    
    print(f"\n🔍 Analyzing {len(all_files)} JSON files...")
    print("=" * 60)
    
    # Analyze each file
    analyses = []
    for filepath in all_files:
        analysis = analyze_json_file(filepath)
        analyses.append(analysis)
    
    # Sort by size (largest first)
    analyses.sort(key=lambda x: x['size'], reverse=True)
    
    # Display results
    print("\n📊 ANALYSIS RESULTS (sorted by size):")
    print("-" * 60)
    
    large_files = []
    potential_post_files = []
    
    for i, analysis in enumerate(analyses, 1):
        filename = os.path.basename(analysis['filepath'])
        size_mb = analysis['size'] / 1024 / 1024
        size_kb = analysis['size'] / 1024
        
        # Size indicator
        if analysis['size'] > 1000000:  # 1MB+
            size_str = f"{size_mb:.2f}MB"
            size_icon = "🔥"
        elif analysis['size'] > 10000:  # 10KB+
            size_str = f"{size_kb:.1f}KB"
            size_icon = "🎯"
        else:
            size_str = f"{analysis['size']}B"
            size_icon = "📄"
        
        # Potential indicator
        potential_icon = "⭐" if analysis['potential_posts'] else "  "
        
        print(f"{i:2d}. {size_icon} {potential_icon} {filename}")
        print(f"     Size: {size_str} | Type: {analysis['data_type']}")
        
        if analysis['content_indicators']:
            indicators_str = ", ".join(analysis['content_indicators'][:3])  # First 3
            if len(analysis['content_indicators']) > 3:
                indicators_str += f" (+{len(analysis['content_indicators'])-3} more)"
            print(f"     Content: {indicators_str}")
        
        print()
        
        # Track interesting files
        if analysis['is_large']:
            large_files.append(analysis)
        if analysis['potential_posts']:
            potential_post_files.append(analysis)
    
    # Summary
    print("🎯 SUMMARY:")
    print("-" * 30)
    print(f"Total files analyzed: {len(analyses)}")
    print(f"Large files (>10KB): {len(large_files)}")
    print(f"Potential post data files: {len(potential_post_files)}")
    
    if large_files:
        print(f"\n🔥 LARGE FILES TO INVESTIGATE:")
        for analysis in large_files[:5]:  # Top 5
            filename = os.path.basename(analysis['filepath'])
            size_kb = analysis['size'] / 1024
            print(f"   • {filename} ({size_kb:.1f}KB)")
            print(f"     Path: {analysis['filepath']}")
    
    if potential_post_files:
        print(f"\n⭐ POTENTIAL POST DATA FILES:")
        for analysis in potential_post_files[:5]:  # Top 5
            filename = os.path.basename(analysis['filepath'])
            size_kb = analysis['size'] / 1024
            print(f"   • {filename} ({size_kb:.1f}KB)")
            print(f"     Path: {analysis['filepath']}")
    
    print(f"\n📋 NEXT STEPS:")
    print("1. Examine the largest JSON files manually")
    print("2. Look for files with 'post', 'content', or 'media' in their structure")
    print("3. Check if any files contain arrays with ~643 items (expected post count)")
    print("4. Once identified, note the URL pattern for that endpoint")
    
    return 0

if __name__ == "__main__":
    exit(main()) 