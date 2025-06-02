#!/usr/bin/env python3
"""
Simple batching analysis that reads CSV directly without complex dependencies.
"""

import pandas as pd
import sys
from pathlib import Path
from collections import defaultdict

def analyze_batching_potential(input_file: str):
    """
    Analyze the current loan data to show batching potential.
    """
    print("🔍 Analyzing Batching Potential for Media Personality Optimization")
    print("=" * 70)
    
    try:
        # Try to read the CSV directly
        if input_file.endswith('.xlsx'):
            df = pd.read_excel(input_file)
        else:
            df = pd.read_csv(input_file)
        
        print(f"📊 Loaded {len(df)} rows from {input_file}")
        print(f"📊 Columns: {list(df.columns)}")
        print()
        
        # Check if we have the required columns
        if 'To' not in df.columns:
            print("❌ 'To' column not found - cannot analyze media personality batching")
            return
        
        # Group by media personality (To field)
        media_groups = df.groupby('To')
        
        print(f"🎯 Found {len(media_groups)} unique media personalities")
        print()
        
        # Analyze each media personality
        print("📈 Media Personality Analysis:")
        print("-" * 50)
        
        total_loans = 0
        total_unique_vehicles = 0
        
        for media_person, group in media_groups:
            num_loans = len(group)
            
            # Count unique vehicles
            if 'Model' in df.columns:
                unique_vehicles = group['Model'].nunique()
            else:
                unique_vehicles = num_loans  # Assume each loan is a different vehicle
            
            total_loans += num_loans
            total_unique_vehicles += unique_vehicles
            
            # Calculate potential savings
            current_requests = num_loans  # Current: process each loan separately
            batched_requests = 1  # Batched: one request per media personality
            
            savings = current_requests - batched_requests
            savings_pct = (savings / current_requests * 100) if current_requests > 0 else 0
            
            print(f"👤 {media_person}")
            print(f"   📋 {num_loans} loans → {unique_vehicles} unique vehicles")
            print(f"   ⚡ Requests: {current_requests} → {batched_requests} ({savings_pct:.1f}% reduction)")
            
            # Show some example vehicles
            if 'Model' in df.columns:
                example_vehicles = group['Model'].unique()[:3]
                print(f"   🚗 Examples: {', '.join(example_vehicles)}")
            print()
        
        # Calculate overall savings
        total_current_requests = total_loans
        total_batched_requests = len(media_groups)
        total_savings = total_current_requests - total_batched_requests
        total_savings_pct = (total_savings / total_current_requests * 100) if total_current_requests > 0 else 0
        
        print("🎉 Overall Optimization Potential:")
        print("-" * 40)
        print(f"📊 Current approach: {total_current_requests} individual loan requests")
        print(f"🚀 Batched approach: {total_batched_requests} media personality batches")
        print(f"💰 Potential savings: {total_savings} requests ({total_savings_pct:.1f}% reduction)")
        print()
        
        # Show distribution
        loan_counts = [len(group) for _, group in media_groups]
        
        print("📊 Media Personality Distribution:")
        print("-" * 40)
        print(f"📈 Media personalities with 1 loan: {sum(1 for c in loan_counts if c == 1)}")
        print(f"📈 Media personalities with 2-5 loans: {sum(1 for c in loan_counts if 2 <= c <= 5)}")
        print(f"📈 Media personalities with 6+ loans: {sum(1 for c in loan_counts if c >= 6)}")
        print()
        
        # Show URL analysis if Links column exists
        if 'Links' in df.columns:
            youtube_count = 0
            web_count = 0
            
            for _, row in df.iterrows():
                links = str(row['Links']) if pd.notna(row['Links']) else ''
                if 'youtube.com' in links or 'youtu.be' in links:
                    youtube_count += 1
                elif links and links != 'nan':
                    web_count += 1
            
            print("🔗 URL Type Distribution:")
            print("-" * 30)
            print(f"📺 YouTube URLs: {youtube_count}")
            print(f"🌐 Web URLs: {web_count}")
            print()
        
        print("💡 Batching Benefits:")
        print("-" * 20)
        print("✅ YouTube channels: Scrape once, check all vehicles")
        print("✅ Website domains: Batch requests to same domain")
        print("✅ Caching: Media-level caching more efficient")
        print("✅ Rate limiting: Natural batching reduces API pressure")
        print("✅ Dashboard: Media-centric view matches workflow")
        
    except Exception as e:
        print(f"❌ Error analyzing file: {e}")

if __name__ == "__main__":
    # Use command line argument or look for test data
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        # Look for test data
        possible_files = [
            "data/fixtures/Loans_without_Clips.csv",
            "tests/fixtures/Loans_without_Clips.csv",
            "Loans_without_Clips.csv"
        ]
        
        input_file = None
        for file_path in possible_files:
            if Path(file_path).exists():
                input_file = file_path
                break
        
        if not input_file:
            print("❌ No input file found. Please provide a CSV file as argument.")
            print("Usage: python simple_batching_analysis.py <path_to_csv>")
            sys.exit(1)
    
    analyze_batching_potential(input_file) 