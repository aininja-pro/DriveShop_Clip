#!/usr/bin/env python3
"""
Check for Mazda models with bad feature extractions
"""
import os
import sys
import json
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.utils.database import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def check_bad_extractions():
    db = DatabaseManager()
    
    # Models to check
    models_to_check = [
        ('Mazda', 'CX-70', 2025),
        ('Mazda', 'CX-5', 2025),
        ('Mazda', 'CX-30', 2025),
        ('Mazda', 'CX-90', 2025)
    ]
    
    print("\n🔍 Checking Mazda models for bad feature extractions...\n")
    
    for make, model, year in models_to_check:
        result = db.supabase.table('oem_model_messaging').select('*').eq('make', make).eq('model', model).eq('year', year).single().execute()
        
        if result.data:
            print(f"\n{'='*60}")
            print(f"📊 {make} {model} {year}")
            print(f"{'='*60}")
            
            try:
                messaging = json.loads(result.data['messaging_data_enhanced'])
                features = messaging.get('key_features_intended', [])
                
                print(f"Total features: {len(features)}")
                print("\nFeatures extracted:")
                
                # Check for bad patterns
                bad_features = []
                for i, f in enumerate(features, 1):
                    feature_name = f.get('feature', '')
                    print(f"  {i}. {feature_name}")
                    
                    # Common bad OCR patterns
                    if (len(feature_name) < 5 or  # Too short
                        feature_name.replace(' ', '').isdigit() or  # Just numbers
                        any(char in feature_name for char in ['°', '©', '®']) or  # Special chars
                        feature_name.endswith(' L') or  # Common OCR error
                        feature_name.endswith(' HP') or  # Just specs
                        'MPG' in feature_name and len(feature_name) < 10):  # Just MPG number
                        bad_features.append(feature_name)
                
                if bad_features:
                    print(f"\n⚠️  BAD FEATURES DETECTED: {bad_features}")
                    print("   This model needs manual correction!")
                else:
                    print("\n✅ Features look reasonable")
                    
            except Exception as e:
                print(f"❌ Error parsing data: {e}")
        else:
            print(f"\n❌ {make} {model} {year} - NOT FOUND in database")
    
    print("\n" + "="*60)
    print("\n💡 Next steps:")
    print("1. For models with bad features, use the OEM Messaging UI to manually update")
    print("2. Or create a fix script similar to fix_cx50_features.py")
    print("3. Apply the unique constraint after fixing any issues")

if __name__ == "__main__":
    check_bad_extractions()