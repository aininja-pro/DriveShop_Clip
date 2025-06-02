#!/usr/bin/env python3
"""
Analyze the batching potential of the current loan data.
This script shows how much efficiency we can gain by batching by media personality.
"""

import pandas as pd
import sys
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.append('.')
from src.ingest.ingest import load_loans_data
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def analyze_batching_potential(input_file: str):
    """
    Analyze the current loan data to show batching potential.
    
    Args:
        input_file: Path to the loans CSV/Excel file
    """
    print("🔍 Analyzing Batching Potential for Media Personality Optimization")
    print("=" * 70)
    
    # Load the current data
    loans = load_loans_data(input_file)
    
    if not loans:
        print(f"❌ No loans data loaded from {input_file}")
        return
    
    print(f"📊 Current Processing: {len(loans)} individual loans")
    print(f"📊 Total URLs to process: {sum(len(loan['urls']) for loan in loans)}")
    print()
    
    # Group by media personality (To field)
    media_groups = defaultdict(list)
    media_urls = defaultdict(set)
    media_vehicles = defaultdict(set)
    
    for loan in loans:
        media_person = loan.get('to', 'Unknown')
        media_groups[media_person].append(loan)
        
        # Track unique URLs per media person
        for url in loan.get('urls', []):
            media_urls[media_person].add(url)
        
        # Track vehicles per media person
        vehicle = f"{loan.get('make', '')} {loan.get('model', '')}".strip()
        if vehicle:
            media_vehicles[media_person].add(vehicle)
    
    print(f"🎯 Batching Optimization: {len(media_groups)} media personalities")
    print()
    
    # Show the biggest batching opportunities
    print("📈 Top Batching Opportunities:")
    print("-" * 50)
    
    # Sort by number of vehicles per media person
    sorted_media = sorted(media_groups.items(), 
                         key=lambda x: len(media_vehicles[x[0]]), 
                         reverse=True)
    
    total_current_requests = 0
    total_batched_requests = 0
    
    for media_person, loans_list in sorted_media[:10]:  # Top 10
        num_loans = len(loans_list)
        num_vehicles = len(media_vehicles[media_person])
        num_urls = len(media_urls[media_person])
        
        # Current: Each loan processed separately
        current_requests = sum(len(loan['urls']) for loan in loans_list)
        
        # Batched: One request per unique URL, then check all vehicles
        batched_requests = num_urls
        
        savings = current_requests - batched_requests
        savings_pct = (savings / current_requests * 100) if current_requests > 0 else 0
        
        total_current_requests += current_requests
        total_batched_requests += batched_requests
        
        print(f"👤 {media_person}")
        print(f"   📋 {num_loans} loans → {num_vehicles} unique vehicles")
        print(f"   🔗 {num_urls} unique URLs")
        print(f"   ⚡ Requests: {current_requests} → {batched_requests} ({savings_pct:.1f}% reduction)")
        print()
    
    # Calculate total savings
    total_savings = total_current_requests - total_batched_requests
    total_savings_pct = (total_savings / total_current_requests * 100) if total_current_requests > 0 else 0
    
    print("🎉 Overall Optimization Potential:")
    print("-" * 40)
    print(f"📊 Current approach: {total_current_requests} individual URL requests")
    print(f"🚀 Batched approach: {total_batched_requests} batched requests")
    print(f"💰 Potential savings: {total_savings} requests ({total_savings_pct:.1f}% reduction)")
    print()
    
    # Show media personality distribution
    print("📊 Media Personality Distribution:")
    print("-" * 40)
    
    vehicle_counts = [len(media_vehicles[media]) for media in media_groups.keys()]
    
    print(f"📈 Media personalities with 1 vehicle: {sum(1 for c in vehicle_counts if c == 1)}")
    print(f"📈 Media personalities with 2-5 vehicles: {sum(1 for c in vehicle_counts if 2 <= c <= 5)}")
    print(f"📈 Media personalities with 6+ vehicles: {sum(1 for c in vehicle_counts if c >= 6)}")
    print()
    
    # Show URL type distribution
    youtube_urls = 0
    web_urls = 0
    
    for loans_list in media_groups.values():
        for loan in loans_list:
            for url in loan.get('urls', []):
                if 'youtube.com' in url or 'youtu.be' in url:
                    youtube_urls += 1
                else:
                    web_urls += 1
    
    print("🔗 URL Type Distribution:")
    print("-" * 30)
    print(f"📺 YouTube URLs: {youtube_urls}")
    print(f"🌐 Web URLs: {web_urls}")
    print()
    
    print("💡 Batching Benefits:")
    print("-" * 20)
    print("✅ YouTube channels: Scrape once, check all vehicles")
    print("✅ Website domains: Batch requests to same domain")
    print("✅ Caching: Media-level caching more efficient")
    print("✅ Rate limiting: Natural batching reduces API pressure")
    print("✅ Dashboard: Media-centric view matches workflow")

if __name__ == "__main__":
    # Use the test fixture or command line argument
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        project_root = Path(__file__).parent
        input_file = project_root / "data" / "fixtures" / "Loans_without_Clips.csv"
    
    analyze_batching_potential(str(input_file)) 