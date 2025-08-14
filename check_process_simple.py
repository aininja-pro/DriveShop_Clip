#!/usr/bin/env python3
"""
Simple process checker - no imports needed, just direct SQL
Run this from project root: python3 check_process_simple.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

# Now we can import your existing modules
from src.utils.database import get_database
from datetime import datetime, timedelta

def check_processes():
    """Check for active processes using your existing database connection"""
    
    print("\n" + "="*60)
    print("CHECKING FOR ACTIVE PROCESSES")
    print("="*60)
    
    try:
        # Use your existing database connection
        db = get_database()
        
        # Check recent activity (last 10 minutes)
        print("\n1. RECENT ACTIVITY (Last 10 minutes):")
        ten_mins_ago = (datetime.now() - timedelta(minutes=10)).isoformat()
        
        recent = db.supabase.table('clips') \
            .select('wo_number, make, model, status, processed_date') \
            .gte('processed_date', ten_mins_ago) \
            .order('processed_date', desc=True) \
            .limit(10) \
            .execute()
        
        if recent.data:
            print(f"   ✅ Found {len(recent.data)} clips in last 10 minutes")
            for clip in recent.data[:3]:
                make_model = f"{clip.get('make', '')} {clip.get('model', '')}".strip()
                print(f"      • WO: {clip['wo_number']} - {make_model} - {clip['status']}")
            if len(recent.data) > 3:
                print(f"      • ... and {len(recent.data) - 3} more")
        else:
            print("   ⚠️  No clips added in last 10 minutes")
        
        # Check last hour summary
        print("\n2. LAST HOUR SUMMARY:")
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        
        hourly = db.supabase.table('clips') \
            .select('wo_number, status') \
            .gte('processed_date', one_hour_ago) \
            .execute()
        
        if hourly.data:
            # Count by status
            status_counts = {}
            wo_set = set()
            for clip in hourly.data:
                status = clip['status']
                wo_set.add(clip['wo_number'])
                status_counts[status] = status_counts.get(status, 0) + 1
            
            print(f"   • Total clips: {len(hourly.data)}")
            print(f"   • Unique work orders: {len(wo_set)}")
            print(f"   • Found: {status_counts.get('Found', 0)}")
            print(f"   • Not Found: {status_counts.get('Not Found', 0)}")
            
        # Check most recent clip time
        print("\n3. LAST CLIP PROCESSED:")
        last_clip = db.supabase.table('clips') \
            .select('processed_date, wo_number, make, model') \
            .order('processed_date', desc=True) \
            .limit(1) \
            .execute()
        
        if last_clip.data:
            last_time = datetime.fromisoformat(last_clip.data[0]['processed_date'].replace('Z', '+00:00'))
            time_diff = datetime.now() - last_time
            mins_ago = int(time_diff.total_seconds() / 60)
            
            make_model = f"{last_clip.data[0].get('make', '')} {last_clip.data[0].get('model', '')}".strip()
            print(f"   • {mins_ago} minutes ago")
            print(f"   • WO: {last_clip.data[0]['wo_number']} - {make_model}")
            
            if mins_ago < 5:
                print("\n🟢 PROCESS APPEARS TO BE RUNNING")
            elif mins_ago < 15:
                print("\n🟡 PROCESS MAY BE RUNNING (check Render logs)")
            else:
                print("\n🔴 NO RECENT ACTIVITY (process likely finished)")
        
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you're running from the project root directory")
        print("and have your .env file with SUPABASE_URL and SUPABASE_KEY")

if __name__ == "__main__":
    check_processes()