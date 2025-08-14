#!/usr/bin/env python3
"""
Fix the CX-50 2025 features with correct data from the PDF
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

def fix_cx50_features():
    db = DatabaseManager()
    
    # Get the 2025 CX-50 record
    cx50_2025 = db.supabase.table('oem_model_messaging').select('*').eq('make', 'Mazda').eq('model', 'CX-50').eq('year', 2025).single().execute()
    
    if not cx50_2025.data:
        logger.error("CX-50 2025 not found")
        return
    
    record_id = cx50_2025.data['id']
    
    # Correct features based on the PDF content
    correct_features = [
        {
            'feature': 'Standard All-Wheel Drive',
            'category': 'performance',
            'priority': 'primary',
            'messaging': 'Standard AWD for all-weather confidence and off-road capability',
            'target_sentiment': 'positive'
        },
        {
            'feature': 'Mi-Drive Modes',
            'category': 'performance',
            'priority': 'primary',
            'messaging': 'Multiple drive modes for different terrain and conditions',
            'target_sentiment': 'positive'
        },
        {
            'feature': '3,500 LB Towing Capacity',
            'category': 'utility',
            'priority': 'primary',
            'messaging': '3,500 LB towing capacity for outdoor adventure equipment',
            'target_sentiment': 'positive'
        },
        {
            'feature': 'Panoramic Moonroof',
            'category': 'design',
            'priority': 'primary',
            'messaging': 'Available panoramic moonroof to connect with nature',
            'target_sentiment': 'positive'
        },
        {
            'feature': '2.5 Turbo Engine',
            'category': 'performance',
            'priority': 'secondary',
            'messaging': 'Available 2.5L Turbo engine with 250 HP and 320 lb-ft torque',
            'target_sentiment': 'positive'
        },
        {
            'feature': 'Hybrid Powertrain',
            'category': 'efficiency',
            'priority': 'secondary',
            'messaging': 'Available hybrid with 38 MPG for eco-conscious adventurers',
            'target_sentiment': 'positive'
        },
        {
            'feature': 'Deep Cargo Area',
            'category': 'utility',
            'priority': 'secondary',
            'messaging': 'Deep cargo area for long outdoor equipment',
            'target_sentiment': 'positive'
        },
        {
            'feature': 'Low Roof Rails',
            'category': 'utility',
            'priority': 'secondary',
            'messaging': 'Low high-strength roof for easy access and accessories',
            'target_sentiment': 'positive'
        },
        {
            'feature': 'Meridian Edition',
            'category': 'trim',
            'priority': 'secondary',
            'messaging': 'Meridian Edition with off-road tires and unique styling',
            'target_sentiment': 'positive'
        },
        {
            'feature': 'Large Rear Seat Legroom',
            'category': 'comfort',
            'priority': 'secondary',
            'messaging': 'Spacious rear seat legroom for passenger comfort',
            'target_sentiment': 'positive'
        }
    ]
    
    # Correct purchase drivers
    correct_drivers = [
        {
            'reason': 'quality',
            'priority': 1,
            'target_audience': 'value-conscious buyers',
            'messaging': 'Premium build quality and reliability'
        },
        {
            'reason': 'exterior styling',
            'priority': 2,
            'target_audience': 'design-conscious buyers',
            'messaging': 'Tough, low & wide exterior stance'
        },
        {
            'reason': 'price/deal',
            'priority': 3,
            'target_audience': 'value seekers',
            'messaging': 'Competitive pricing with premium features'
        },
        {
            'reason': 'reliability',
            'priority': 4,
            'target_audience': 'practical buyers',
            'messaging': 'Mazda reliability and durability'
        },
        {
            'reason': 'fun to drive',
            'priority': 5,
            'target_audience': 'driving enthusiasts',
            'messaging': 'Engaging driving dynamics'
        }
    ]
    
    # Update the messaging data
    correct_messaging_data = {
        'positioning_statement': 'CX-50 has appeal across all life stages, but is targeting buyers who enjoy being outside & want a vehicle that enables their active pursuits.',
        'target_audience': 'Active lifestyle enthusiasts, outdoor adventurers',
        'key_features_intended': correct_features,
        'brand_attributes_intended': [
            'Outdoor Adventure',
            'Active Lifestyle', 
            'Premium Quality',
            'Driving Enjoyment',
            'Japanese Engineering'
        ],
        'purchase_drivers_intended': correct_drivers,
        'competitive_positioning': {
            'direct_comparisons': [
                {
                    'competitor': 'Toyota RAV4',
                    'advantages': ['Styling', 'Performance', 'Interior quality'],
                    'disadvantages': ['MPG', 'Space', 'Reputation']
                },
                {
                    'competitor': 'Subaru Outback',
                    'advantages': ['Styling', 'Performance', 'Quality'],
                    'disadvantages': ['Comfort', 'Space', 'Image']
                },
                {
                    'competitor': 'Honda CR-V',
                    'advantages': ['AWD', 'Handling', 'Styling'],
                    'disadvantages': ['Space', 'MPG', 'Reputation']
                }
            ],
            'market_positioning': 'The outdoor adventure CUV with Mazda driving dynamics'
        }
    }
    
    # Update the record
    update_data = {
        'positioning_statement': correct_messaging_data['positioning_statement'],
        'target_audience': correct_messaging_data['target_audience'],
        'messaging_data_enhanced': json.dumps(correct_messaging_data)
    }
    
    result = db.supabase.table('oem_model_messaging').update(update_data).eq('id', record_id).execute()
    
    if result.data:
        logger.info("✅ Successfully updated CX-50 2025 with correct features!")
        
        # Also update the normalized tables
        # Delete old features
        db.supabase.table('oem_key_features').delete().eq('model_messaging_id', record_id).execute()
        
        # Insert correct features
        for feature in correct_features:
            db.supabase.table('oem_key_features').insert({
                'model_messaging_id': record_id,
                'feature': feature['feature'],
                'feature_category': feature['category'],
                'priority': feature['priority'],
                'messaging_points': feature['messaging'],
                'target_sentiment': 'positive'
            }).execute()
        
        # Update brand attributes
        db.supabase.table('oem_brand_attributes').delete().eq('model_messaging_id', record_id).execute()
        for attr in correct_messaging_data['brand_attributes_intended']:
            db.supabase.table('oem_brand_attributes').insert({
                'model_messaging_id': record_id,
                'attribute': attr,
                'importance': 'core'
            }).execute()
        
        # Update purchase drivers
        db.supabase.table('oem_purchase_drivers').delete().eq('model_messaging_id', record_id).execute()
        for driver in correct_drivers:
            db.supabase.table('oem_purchase_drivers').insert({
                'model_messaging_id': record_id,
                'reason': driver['reason'],
                'priority': driver['priority'],
                'target_audience': driver['target_audience']
            }).execute()
        
        print("\n✅ FIXED! CX-50 2025 now has proper features:")
        for i, feature in enumerate(correct_features, 1):
            print(f"  {i}. {feature['feature']}")
    else:
        logger.error("Failed to update")

if __name__ == "__main__":
    fix_cx50_features()