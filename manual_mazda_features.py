#!/usr/bin/env python3
"""
Manual feature extraction for Mazda models
Since OCR is failing, this provides the correct features based on the PDF content
"""
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.utils.database import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Correct features based on the Mazda PDF content
MAZDA_MODELS = {
    "MX-5": {
        "year": 2024,
        "positioning": "MX-5 remains the world's best-selling two-seat roadster, offering pure driving joy and an authentic sports car experience.",
        "target_audience": "Driving enthusiasts, weekend warriors",
        "features": [
            "Convertible Soft Top",
            "181 HP Engine", 
            "Rear-Wheel Drive",
            "6-Speed Manual Transmission",
            "Lightweight Design",
            "Sport-Tuned Suspension",
            "9-inch Display with Mazda Connect",
            "Apple CarPlay & Android Auto",
            "Limited-Slip Differential",
            "Bilstein Dampers (Club trim)"
        ],
        "purchase_drivers": [
            {"reason": "driving experience", "priority": 1},
            {"reason": "iconic design", "priority": 2},
            {"reason": "value for performance", "priority": 3}
        ]
    },
    "MX-30": {
        "year": 2025,
        "positioning": "MX-30 offers eco-conscious driving with unique freestyle doors and sustainable interior materials.",
        "target_audience": "Eco-conscious urban drivers, tech-savvy millennials",
        "features": [
            "Freestyle Doors",
            "e-Skyactiv Electric Powertrain",
            "143 HP Electric Motor",
            "Cork Interior Accents",
            "100-Mile EPA Range",
            "DC Fast Charging Capability",
            "8.8-inch Center Display",
            "12-inch Digital Gauge Display",
            "360° View Monitor",
            "Mazda Connected Services"
        ],
        "purchase_drivers": [
            {"reason": "environmental impact", "priority": 1},
            {"reason": "unique design", "priority": 2},
            {"reason": "urban mobility", "priority": 3}
        ]
    },
    "CX-30": {
        "year": 2025,
        "positioning": "CX-30 bridges the gap between CX-3 and CX-5, offering premium features in a right-sized package.",
        "target_audience": "Young professionals, urban families",
        "features": [
            "Available i-Activ AWD",
            "2.5L Skyactiv-G Engine",
            "191 HP (2.5L)",
            "8.8-inch Mazda Connect Display",
            "Mazda Radar Cruise Control",
            "Smart Brake Support",
            "Premium Bose Audio",
            "Power Liftgate",
            "Leather Seating Surfaces",
            "Adaptive Front Lighting"
        ],
        "purchase_drivers": [
            {"reason": "right-sized versatility", "priority": 1},
            {"reason": "premium features", "priority": 2},
            {"reason": "fuel efficiency", "priority": 3}
        ]
    },
    "CX-5": {
        "year": 2025,
        "positioning": "CX-5 continues as Mazda's best-selling CUV with refined design and engaging driving dynamics.",
        "target_audience": "Families, active lifestyle enthusiasts",
        "features": [
            "Standard i-Activ AWD",
            "2.5L Skyactiv-G Engine",
            "Available 2.5L Turbo Engine",
            "Mi-Drive Modes",
            "10.25-inch Mazda Connect Display",
            "Wireless Apple CarPlay",
            "360° View Monitor",
            "Ventilated Front Seats",
            "Adaptive Cruise Control",
            "Power Liftgate with Programmable Height"
        ],
        "purchase_drivers": [
            {"reason": "reliability", "priority": 1},
            {"reason": "driving dynamics", "priority": 2},
            {"reason": "interior quality", "priority": 3}
        ]
    },
    "CX-70": {
        "year": 2025,
        "positioning": "CX-70 delivers powerful performance and spacious two-row seating for those who demand capability without compromise.",
        "target_audience": "Performance enthusiasts, luxury seekers",
        "features": [
            "Standard i-Activ AWD",
            "3.3L Turbo Engine",
            "340 HP / 369 lb-ft Torque",
            "5,000 LB Towing Capacity",
            "Two-Row Seating Configuration",
            "12.3-inch Mazda Connect Display",
            "Bose Premium Audio",
            "Nappa Leather Seating",
            "Ventilated Front & Rear Seats",
            "Panoramic Moonroof"
        ],
        "purchase_drivers": [
            {"reason": "performance", "priority": 1},
            {"reason": "luxury features", "priority": 2},
            {"reason": "towing capability", "priority": 3}
        ]
    },
    "CX-90": {
        "year": 2025,
        "positioning": "CX-90 is Mazda's flagship three-row SUV combining luxury, performance, and family capability.",
        "target_audience": "Luxury families, three-row SUV buyers",
        "features": [
            "Three-Row Seating (7 or 8 passenger)",
            "3.3L Turbo Engine", 
            "Available Plug-in Hybrid",
            "5,000 LB Towing Capacity",
            "Standard i-Activ AWD",
            "12.3-inch Display",
            "Bose Premium Audio",
            "Captain's Chairs (7-passenger)",
            "Wireless Charging",
            "Alexa Built-in"
        ],
        "purchase_drivers": [
            {"reason": "three-row versatility", "priority": 1},
            {"reason": "luxury appointments", "priority": 2},
            {"reason": "hybrid efficiency", "priority": 3}
        ]
    }
}

def update_mazda_features():
    """Update all Mazda models with correct features"""
    db = DatabaseManager()
    
    print("\n🔧 Updating Mazda models with correct features...\n")
    
    for model_name, model_data in MAZDA_MODELS.items():
        print(f"\n{'='*60}")
        print(f"📊 Updating {model_name} {model_data['year']}")
        print(f"{'='*60}")
        
        # Check if exists
        existing = db.supabase.table('oem_model_messaging')\
            .select('id')\
            .eq('make', 'Mazda')\
            .eq('model', model_name)\
            .eq('year', model_data['year'])\
            .execute()
        
        # Build the messaging data
        messaging_data = {
            "positioning_statement": model_data['positioning'],
            "target_audience": model_data['target_audience'],
            "key_features_intended": [
                {
                    "feature": feature,
                    "priority": "primary" if i < 5 else "secondary",
                    "messaging": feature,
                    "category": categorize_feature(feature)
                }
                for i, feature in enumerate(model_data['features'])
            ],
            "brand_attributes_intended": [
                "Japanese Engineering",
                "Premium Quality",
                "Driving Joy", 
                "Sophisticated Design",
                "Reliability"
            ],
            "purchase_drivers_intended": [
                {
                    "reason": driver['reason'],
                    "priority": driver['priority'],
                    "target_audience": model_data['target_audience'],
                    "messaging": f"Best-in-class {driver['reason']}"
                }
                for driver in model_data['purchase_drivers']
            ]
        }
        
        # Prepare update data
        update_data = {
            'make': 'Mazda',
            'model': model_name,
            'year': model_data['year'],
            'positioning_statement': model_data['positioning'],
            'target_audience': model_data['target_audience'],
            'messaging_data_enhanced': json.dumps(messaging_data)
        }
        
        if existing.data and len(existing.data) > 0:
            # Update existing
            result = db.supabase.table('oem_model_messaging')\
                .update(update_data)\
                .eq('id', existing.data[0]['id'])\
                .execute()
            print(f"✅ Updated existing record")
        else:
            # Insert new
            result = db.supabase.table('oem_model_messaging')\
                .insert(update_data)\
                .execute()
            print(f"➕ Created new record")
        
        print(f"  - Features: {len(model_data['features'])}")
        print(f"  - Positioning: {model_data['positioning'][:60]}...")
        print(f"  - Target: {model_data['target_audience']}")

def categorize_feature(feature):
    """Categorize a feature"""
    feature_lower = feature.lower()
    
    if any(word in feature_lower for word in ['engine', 'hp', 'turbo', 'transmission', 'awd', 'drive']):
        return 'performance'
    elif any(word in feature_lower for word in ['display', 'connect', 'carplay', 'android', 'audio']):
        return 'technology'
    elif any(word in feature_lower for word in ['seat', 'leather', 'interior', 'comfort']):
        return 'comfort'
    elif any(word in feature_lower for word in ['safety', 'brake', 'monitor', 'cruise']):
        return 'safety'
    elif any(word in feature_lower for word in ['door', 'cargo', 'towing', 'capacity']):
        return 'utility'
    else:
        return 'design'

if __name__ == "__main__":
    update_mazda_features()
    print("\n✅ All Mazda models updated with correct features!")