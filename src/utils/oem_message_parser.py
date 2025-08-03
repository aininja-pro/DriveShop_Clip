"""
OEM Message Parser - Extracts structured messaging data from OEM materials
Designed to mirror our enhanced sentiment analysis structure
"""
import json
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
import re

from src.utils.logger import setup_logger
from src.utils.database import DatabaseManager

logger = setup_logger(__name__)

@dataclass
class OEMMessage:
    """Structure matching our enhanced sentiment data"""
    make: str
    model: str
    year: int
    trim_level: str = None
    positioning_statement: str = None
    target_audience: str = None
    key_features_intended: List[Dict] = None
    brand_attributes_intended: List[str] = None
    purchase_drivers_intended: List[Dict] = None
    competitive_positioning: Dict = None

class OEMMessageParser:
    """Parse OEM materials to extract messaging that mirrors sentiment structure"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def parse_mazda_one_pager(self, text_content: str, model_info: Dict) -> OEMMessage:
        """
        Parse Mazda one-pager format
        Example for MX-5:
        - Positioning: "MX-5 is the pinnacle of Mazda brand values"
        - Purchase Reasons: Listed in order
        - Key Features: Highlighted in various sections
        """
        
        # Extract positioning statement (usually at top)
        positioning_match = re.search(
            r"(MX-5|CX-\d+) (?:is|serves as) ([^.]+)\.", 
            text_content
        )
        positioning = positioning_match.group(0) if positioning_match else None
        
        # Extract target audience from customer profile
        audience_indicators = {
            'SINGLE/COUPLE': 'single/couple',
            'FAMILY': 'family-oriented',
            'EMPTY-NESTER': 'empty-nester',
            'HALO': 'enthusiast'
        }
        
        target_audience = None
        for indicator, audience in audience_indicators.items():
            if indicator in text_content.upper():
                target_audience = audience
                break
        
        # Extract purchase reasons (these become purchase drivers)
        purchase_drivers = []
        reasons_section = re.search(
            r"PURCHASE REASONS\s*\n(.*?)(?=KEY|$)", 
            text_content, 
            re.DOTALL
        )
        
        if reasons_section:
            reasons_text = reasons_section.group(1)
            # Parse numbered reasons
            reason_matches = re.findall(
                r"(\d+)\.\s*([^\n]+)", 
                reasons_text
            )
            
            for priority, reason in reason_matches:
                purchase_drivers.append({
                    'reason': reason.strip().lower(),
                    'priority': int(priority),
                    'target_audience': target_audience,
                    'messaging': None  # Would need more context
                })
        
        # Extract key features from various sections
        key_features = []
        
        # Look for highlighted features
        if "KEY VALUES & FEATURE HIGHLIGHTS" in text_content:
            # Extract exterior design features
            if "Retractable Fastback" in text_content:
                key_features.append({
                    'feature': 'Retractable Fastback Roof',
                    'category': 'design',
                    'priority': 'primary',
                    'target_sentiment': 'positive'
                })
            
            # Performance features
            if "Manual Transmission" in text_content:
                key_features.append({
                    'feature': 'Manual Transmission',
                    'category': 'performance',
                    'priority': 'primary',
                    'target_sentiment': 'positive',
                    'messaging': 'Available manual transmission for driving enthusiasts'
                })
        
        # Extract technology features
        tech_matches = re.findall(
            r"([\w\s]+(?:Display|System|Control|Screen))", 
            text_content
        )
        for tech in tech_matches[:3]:  # Top 3 tech features
            key_features.append({
                'feature': tech.strip(),
                'category': 'technology',
                'priority': 'secondary',
                'target_sentiment': 'positive'
            })
        
        # Extract brand attributes from positioning and descriptions
        brand_attributes = []
        
        # Common Mazda brand attributes to look for
        attribute_keywords = {
            'fun to drive': 'driving enjoyment',
            'driving dynamics': 'dynamic performance',
            'style': 'stylish design',
            'quality': 'premium quality',
            'craftsmanship': 'Japanese craftsmanship',
            'value': 'exceptional value'
        }
        
        text_lower = text_content.lower()
        for keyword, attribute in attribute_keywords.items():
            if keyword in text_lower:
                brand_attributes.append(attribute)
        
        # Extract competitive positioning
        competitive_data = {'direct_comparisons': [], 'advantages': []}
        
        # Look for comparison table data
        comp_section = re.search(
            r"KEY COMPETITORS.*?COMPARISON(.*?)(?=LINE-UP|$)", 
            text_content, 
            re.DOTALL
        )
        
        if comp_section:
            # Extract competitor mentions and advantages
            comp_matches = re.findall(
                r"([\w\s]+)\s+([\w\s,]+)(?:\s+|$)", 
                comp_section.group(1)
            )
            
            for comp_model, advantages in comp_matches:
                if any(brand in comp_model for brand in ['TOYOTA', 'HONDA', 'SUBARU', 'BMW']):
                    competitive_data['direct_comparisons'].append({
                        'competitor': comp_model.strip(),
                        'mazda_advantages': advantages.strip()
                    })
        
        return OEMMessage(
            make=model_info['make'],
            model=model_info['model'],
            year=model_info['year'],
            trim_level=model_info.get('trim'),
            positioning_statement=positioning,
            target_audience=target_audience,
            key_features_intended=key_features,
            brand_attributes_intended=brand_attributes,
            purchase_drivers_intended=purchase_drivers,
            competitive_positioning=competitive_data
        )
    
    def save_to_database(self, oem_message: OEMMessage, source_info: Dict):
        """Save parsed OEM messaging to database"""
        
        try:
            # 1. Create source record
            source_result = self.db.supabase.table('oem_messaging_sources').insert({
                'make': oem_message.make,
                'document_title': source_info.get('title'),
                'document_type': source_info.get('type', 'media_guide'),
                'source_file_path': source_info.get('file_path'),
                'model_year': oem_message.year,
                'raw_content': source_info.get('raw_content', '')
            }).execute()
            
            source_id = source_result.data[0]['id']
            
            # 2. Create model messaging record
            messaging_data = {
                'positioning_statement': oem_message.positioning_statement,
                'target_audience': oem_message.target_audience,
                'key_features_intended': oem_message.key_features_intended,
                'brand_attributes_intended': oem_message.brand_attributes_intended,
                'purchase_drivers_intended': oem_message.purchase_drivers_intended,
                'competitive_positioning': oem_message.competitive_positioning
            }
            
            model_result = self.db.supabase.table('oem_model_messaging').insert({
                'source_id': source_id,
                'make': oem_message.make,
                'model': oem_message.model,
                'year': oem_message.year,
                'trim_level': oem_message.trim_level,
                'positioning_statement': oem_message.positioning_statement,
                'target_audience': oem_message.target_audience,
                'messaging_data_enhanced': json.dumps(messaging_data)
            }).execute()
            
            model_id = model_result.data[0]['id']
            
            # 3. Save individual features
            if oem_message.key_features_intended:
                for feature in oem_message.key_features_intended:
                    self.db.supabase.table('oem_key_features').insert({
                        'model_messaging_id': model_id,
                        'feature': feature['feature'],
                        'feature_category': feature.get('category'),
                        'priority': feature.get('priority'),
                        'messaging_points': feature.get('messaging'),
                        'target_sentiment': feature.get('target_sentiment', 'positive')
                    }).execute()
            
            # 4. Save brand attributes
            if oem_message.brand_attributes_intended:
                for attribute in oem_message.brand_attributes_intended:
                    self.db.supabase.table('oem_brand_attributes').insert({
                        'model_messaging_id': model_id,
                        'attribute': attribute,
                        'importance': 'core'  # Would need more logic to determine
                    }).execute()
            
            # 5. Save purchase drivers
            if oem_message.purchase_drivers_intended:
                for driver in oem_message.purchase_drivers_intended:
                    self.db.supabase.table('oem_purchase_drivers').insert({
                        'model_messaging_id': model_id,
                        'reason': driver['reason'],
                        'target_audience': driver.get('target_audience'),
                        'priority': driver.get('priority'),
                        'messaging_points': driver.get('messaging')
                    }).execute()
            
            # 6. Save competitive positioning
            if oem_message.competitive_positioning and oem_message.competitive_positioning.get('direct_comparisons'):
                for comp in oem_message.competitive_positioning['direct_comparisons']:
                    # Parse competitor make/model
                    comp_parts = comp['competitor'].split()
                    comp_make = comp_parts[0] if comp_parts else ''
                    comp_model = ' '.join(comp_parts[1:]) if len(comp_parts) > 1 else ''
                    
                    self.db.supabase.table('oem_competitive_positioning').insert({
                        'model_messaging_id': model_id,
                        'competitor_make': comp_make,
                        'competitor_model': comp_model,
                        'comparison_type': 'direct',
                        'advantages': json.dumps([comp.get('mazda_advantages', '')]),
                        'positioning_strategy': None
                    }).execute()
            
            logger.info(f"✅ Successfully saved OEM messaging for {oem_message.make} {oem_message.model} {oem_message.year}")
            return model_id
            
        except Exception as e:
            logger.error(f"❌ Error saving OEM messaging: {e}")
            raise


# Example usage:
if __name__ == "__main__":
    parser = OEMMessageParser()
    
    # Example: Parse MX-5 from the PDF
    mx5_text = """
    MX-5 is the pinnacle of Mazda brand values.
    MX-5 is the reward purchase for most buyers.
    
    PURCHASE REASONS
    1. Fun to Drive
    2. Exterior Styling
    3. Manual Transmission
    4. Previous Experience with Model
    5. Exterior Color
    
    KEY VALUES & FEATURE HIGHLIGHTS
    - Manual Transmission
    - Retractable Fastback
    - Lightweight Design
    """
    
    mx5_message = parser.parse_mazda_one_pager(
        mx5_text,
        {'make': 'Mazda', 'model': 'MX-5', 'year': 2024}
    )
    
    print(json.dumps(mx5_message.__dict__, indent=2))