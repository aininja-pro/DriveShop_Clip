#!/usr/bin/env python3
"""
Import the extracted OEM data into the database
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

def import_oem_data():
    """Import extracted OEM data into database"""
    
    # Read the extracted data
    with open('extracted_oem_data/mazda_oem_messages.json', 'r') as f:
        all_models = json.load(f)
    
    print(f"📥 Importing {len(all_models)} models into database...")
    
    db = DatabaseManager()
    
    # Create one source record for all models
    source_data = {
        'make': 'Mazda',
        'document_title': '2025 Model One Pagers w Pricing FINAL',
        'document_type': 'media_guide',
        'model_year': 2025,
        'source_file_path': '/Users/richardrierson/Downloads/2025 Model One Pagers w Pricing FINAL.pdf',
        'raw_content': 'Extracted via OCR'
    }
    
    source_result = db.supabase.table('oem_messaging_sources').insert(source_data).execute()
    source_id = source_result.data[0]['id']
    print(f"✅ Created source document: {source_id}")
    
    # Import each model
    for model_data in all_models:
        try:
            # Clean up the data
            model_name = model_data['model']
            
            # Fix model names (OCR errors)
            model_name = model_name.replace('CX-7', 'CX-70').replace('CX-3', 'CX-30')
            
            print(f"\n🚗 Importing {model_name}...")
            
            # Create model messaging record
            messaging_record = {
                'source_id': source_id,
                'make': 'Mazda',
                'model': model_name,
                'year': 2025,
                'positioning_statement': model_data.get('positioning_statement', '').strip(),
                'target_audience': model_data.get('target_audience', ''),
                'messaging_data_enhanced': json.dumps({
                    'positioning_statement': model_data.get('positioning_statement', ''),
                    'target_audience': model_data.get('target_audience', ''),
                    'key_features_intended': model_data.get('key_features_intended', []),
                    'brand_attributes_intended': model_data.get('brand_attributes_intended', []),
                    'purchase_drivers_intended': model_data.get('purchase_drivers_intended', []),
                    'competitive_positioning': model_data.get('competitive_positioning', {})
                })
            }
            
            result = db.supabase.table('oem_model_messaging').insert(messaging_record).execute()
            model_id = result.data[0]['id']
            
            # Import key features
            for feature in model_data.get('key_features_intended', []):
                db.supabase.table('oem_key_features').insert({
                    'model_messaging_id': model_id,
                    'feature': feature['feature'],
                    'feature_category': feature.get('category', 'other'),
                    'priority': feature.get('priority', 'secondary'),
                    'messaging_points': feature.get('messaging', ''),
                    'target_sentiment': 'positive'
                }).execute()
            
            print(f"  ✅ Imported with {len(model_data.get('key_features_intended', []))} features")
            
        except Exception as e:
            print(f"  ❌ Error importing {model_data['model']}: {e}")
    
    print("\n✅ Import complete!")
    print("\n🎯 Next steps:")
    print("1. Review the imported data in your dashboard")
    print("2. Run Message Pull-Through Analysis")
    print("3. Compare OEM messages vs actual reviews")

if __name__ == "__main__":
    print("🚀 OEM Data Import Tool")
    print("=" * 60)
    import_oem_data()