#!/usr/bin/env python3
"""
Clean up duplicate and incorrect Mazda OEM entries
"""
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.utils.database import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def cleanup_mazda_duplicates():
    db = DatabaseManager()
    
    print("\n🧹 Cleaning up Mazda OEM messaging duplicates and errors...\n")
    
    # Get all Mazda entries
    all_mazda = db.supabase.table('oem_model_messaging').select('*').eq('make', 'Mazda').execute()
    
    print(f"Found {len(all_mazda.data)} total Mazda entries")
    
    # Group by model and year
    model_groups = {}
    for entry in all_mazda.data:
        key = f"{entry['model']}_{entry['year']}"
        if key not in model_groups:
            model_groups[key] = []
        model_groups[key].append(entry)
    
    # Show duplicates
    print("\n📊 Duplicate Analysis:")
    duplicates_found = False
    for key, entries in model_groups.items():
        if len(entries) > 1:
            duplicates_found = True
            model, year = key.split('_')
            print(f"  - {model} {year}: {len(entries)} entries (IDs: {[e['id'] for e in entries]})")
    
    if not duplicates_found:
        print("  ✅ No duplicates found")
    
    # Delete ALL Mazda entries with bad data (year 2024 except MX-5)
    print("\n🗑️  Deleting incorrect entries...")
    
    # Expected correct models and years based on PDF
    correct_models = {
        'MX-5': 2024,      # Only 2024 model
        'MX-30': 2025,
        'CX-30': 2025,
        'CX-5': 2025,
        'CX-50': 2025,
        'CX-70': 2025,
        'CX-90': 2025
    }
    
    deleted_count = 0
    for entry in all_mazda.data:
        model = entry['model']
        year = entry['year']
        
        # Delete if:
        # 1. Model not in expected list
        # 2. Wrong year for the model
        # 3. Has bad features (like "500 L", "280 HP", etc.)
        
        should_delete = False
        reason = ""
        
        if model not in correct_models:
            should_delete = True
            reason = f"Unknown model: {model}"
        elif year != correct_models[model]:
            should_delete = True
            reason = f"Wrong year: {model} should be {correct_models[model]}, not {year}"
        
        if should_delete:
            # First delete from child tables due to foreign key constraints
            try:
                # Delete from oem_key_features
                db.supabase.table('oem_key_features').delete().eq('model_messaging_id', entry['id']).execute()
                # Delete from oem_brand_attributes
                db.supabase.table('oem_brand_attributes').delete().eq('model_messaging_id', entry['id']).execute()
                # Delete from oem_purchase_drivers
                db.supabase.table('oem_purchase_drivers').delete().eq('model_messaging_id', entry['id']).execute()
                
                # Now delete from main table
                result = db.supabase.table('oem_model_messaging').delete().eq('id', entry['id']).execute()
                deleted_count += 1
                print(f"  ❌ Deleted {model} {year} - {reason}")
            except Exception as e:
                print(f"  ⚠️  Failed to delete {model} {year}: {str(e)}")
    
    print(f"\n✅ Deleted {deleted_count} incorrect entries")
    
    # Show remaining entries
    remaining = db.supabase.table('oem_model_messaging').select('*').eq('make', 'Mazda').execute()
    print(f"\n📋 Remaining Mazda entries: {len(remaining.data)}")
    for entry in remaining.data:
        print(f"  - {entry['model']} {entry['year']}")
    
    print("\n💡 Next steps:")
    print("1. Fix the extraction script to use correct years")
    print("2. Re-run extraction with the fixed script")
    print("3. Apply unique constraint to prevent future duplicates")

if __name__ == "__main__":
    cleanup_mazda_duplicates()