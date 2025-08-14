#!/usr/bin/env python3
"""
Quick script to check if processes are still running after UI logout
"""

import os
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def check_active_processes():
    """Check for recently active clip processing"""
    
    # Initialize Supabase client
    supabase: Client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    
    print("\n" + "="*60)
    print("CHECKING ACTIVE PROCESSES")
    print("="*60)
    
    # Check clips from last 2 hours
    two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()
    
    # Get recent clips
    recent_clips = supabase.table('clips') \
        .select('work_order, media, make_model, status, created_at') \
        .gte('created_at', two_hours_ago) \
        .order('created_at', desc=True) \
        .limit(10) \
        .execute()
    
    if recent_clips.data:
        print(f"\nFound {len(recent_clips.data)} clips processed in last 2 hours:")
        print("\nMost Recent Activity:")
        for clip in recent_clips.data[:5]:
            created = datetime.fromisoformat(clip['created_at'].replace('Z', '+00:00'))
            mins_ago = (datetime.now() - created).seconds // 60
            print(f"  • WO: {clip['work_order']} | {clip['make_model']} | "
                  f"{clip['status']} | {mins_ago} mins ago")
    
    # Get summary by work order
    print("\n" + "-"*60)
    print("WORK ORDER SUMMARY (Last 24 hours):")
    
    one_day_ago = (datetime.now() - timedelta(days=1)).isoformat()
    
    # Get all clips from last 24 hours
    daily_clips = supabase.table('clips') \
        .select('work_order, status') \
        .gte('created_at', one_day_ago) \
        .execute()
    
    # Group by work order
    wo_summary = {}
    for clip in daily_clips.data:
        wo = clip['work_order']
        status = clip['status']
        
        if wo not in wo_summary:
            wo_summary[wo] = {'Found': 0, 'Not Found': 0, 'Error': 0}
        
        if status in wo_summary[wo]:
            wo_summary[wo][status] += 1
        else:
            wo_summary[wo]['Error'] += 1
    
    # Display summary
    for wo, counts in sorted(wo_summary.items(), reverse=True)[:10]:
        total = sum(counts.values())
        found_pct = (counts['Found'] / total * 100) if total > 0 else 0
        print(f"\n  WO #{wo}:")
        print(f"    Total: {total} | Found: {counts['Found']} ({found_pct:.1f}%) | "
              f"Not Found: {counts['Not Found']}")
    
    # Check if anything is currently being added
    print("\n" + "-"*60)
    print("CHECKING FOR ACTIVE PROCESSING:")
    
    # Get clips from last 5 minutes
    five_mins_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
    active_clips = supabase.table('clips') \
        .select('count') \
        .gte('created_at', five_mins_ago) \
        .execute()
    
    if active_clips.count > 0:
        print(f"\n✅ ACTIVE: {active_clips.count} clips added in last 5 minutes")
        print("   → Process appears to be running!")
    else:
        print("\n⚠️  No clips added in last 5 minutes")
        print("   → Process may have completed or stopped")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    check_active_processes()