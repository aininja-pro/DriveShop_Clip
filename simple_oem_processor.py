#!/usr/bin/env python3
"""
Simplified OEM processor that bypasses browser crawler issues
Uses direct HTTP extraction + OpenAI processing
"""
import os
import json
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
from datetime import datetime
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.utils.logger import setup_logger
from src.utils.database import DatabaseManager

logger = setup_logger(__name__)

class SimpleOEMProcessor:
    """Simple OEM processor without complex crawler dependencies"""
    
    def __init__(self):
        self.db = DatabaseManager()
        openai.api_key = os.environ.get('OPENAI_API_KEY')
        
    def extract_content_simple(self, url: str) -> Optional[str]:
        """Simple content extraction using requests + BeautifulSoup"""
        try:
            logger.info(f"🌐 Fetching content from: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for script in soup(["script", "style", "nav", "header", "footer", "noscript"]):
                script.decompose()
            
            # Try to find main content
            content_selectors = ['main', 'article', '.content', '#content', '.release-body']
            content = None
            
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = elements[0].get_text()
                    break
            
            if not content:
                # Fallback to body text
                content = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            content = ' '.join(chunk for chunk in chunks if chunk)
            
            logger.info(f"✅ Extracted {len(content)} characters")
            return content
            
        except Exception as e:
            logger.error(f"❌ Error extracting content: {e}")
            return None
    
    def extract_oem_messaging(self, content: str, make: str, model: str) -> Optional[Dict]:
        """Extract OEM messaging using the same prompt"""
        if not content or len(content.strip()) < 200:
            logger.warning(f"Content too short: {len(content)} chars")
            return None
            
        # Use full content for comprehensive analysis
        logger.info(f"Analyzing full content: {len(content)} characters")
        
        prompt = f"""
You are an expert at extracting OEM (Original Equipment Manufacturer) intended messaging from marketing materials.

Analyze this {make} {model} content and extract the following structured information:

CONTENT:
{content}

Extract the following (matching our sentiment analysis structure):

1. POSITIONING STATEMENT: The main positioning or value proposition for this vehicle
2. TARGET AUDIENCE: Who is this vehicle designed for?
3. KEY FEATURES (aim for 10): What features does the OEM emphasize? Include:
   - Feature name
   - Category (performance, technology, design, safety, comfort, utility)
   - Priority (primary, secondary, tertiary)
   - How they want it described (messaging)
4. BRAND ATTRIBUTES (3-5): What brand values/attributes are emphasized?
5. PURCHASE DRIVERS: Why would someone buy this? (in order of importance)
6. COMPETITIVE POSITIONING: How is it positioned against competitors?

Return as JSON in this exact format:
{{
    "model_detected": "MODEL NAME",
    "year": 2024,
    "positioning_statement": "...",
    "target_audience": "...",
    "key_features_intended": [
        {{
            "feature": "Feature Name",
            "category": "category",
            "priority": "primary/secondary/tertiary",
            "messaging": "How OEM describes it",
            "target_sentiment": "positive"
        }}
    ],
    "brand_attributes_intended": ["attribute1", "attribute2", ...],
    "purchase_drivers_intended": [
        {{
            "reason": "reason",
            "priority": 1,
            "target_audience": "who this appeals to",
            "messaging": "supporting message"
        }}
    ],
    "competitive_positioning": {{
        "direct_comparisons": [
            {{
                "competitor": "Make Model",
                "advantages": ["advantage1", "advantage2"],
                "comparison_type": "direct/aspirational"
            }}
        ],
        "market_positioning": "overall market position"
    }}
}}
"""
        
        try:
            logger.info(f"🤖 Making OpenAI API call for {make} {model}")
            
            from openai import OpenAI
            client = OpenAI()
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting structured OEM messaging from marketing materials."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            response_content = response.choices[0].message.content.strip()
            
            # Clean JSON response
            if response_content.startswith('```json'):
                response_content = response_content[7:]
            if response_content.endswith('```'):
                response_content = response_content[:-3]
            
            extracted_data = json.loads(response_content.strip())
            
            logger.info(f"✅ Successfully extracted messaging for {make} {model}")
            return extracted_data
            
        except Exception as e:
            logger.error(f"❌ Error extracting messaging: {e}")
            return None
    
    def save_to_database(self, extracted_data: Dict, make: str, model: str, url: str) -> Optional[str]:
        """Save extracted OEM messaging to database"""
        try:
            # Check if already exists
            existing = self.db.supabase.table('oem_model_messaging')\
                .select('id')\
                .eq('make', make)\
                .eq('model', model)\
                .execute()
            
            if existing.data:
                logger.info(f"⏭️  {make} {model} already exists")
                return existing.data[0]['id']
            
            # Create source record
            source_data = {
                'make': make,
                'document_title': f"{make} {model} Marketing Material",
                'document_type': 'url',
                'source_url': url,
                'model_year': extracted_data.get('year', datetime.now().year),
                'raw_content': ''
            }
            
            source_result = self.db.supabase.table('oem_messaging_sources').insert(source_data).execute()
            source_id = source_result.data[0]['id']
            
            # Create model messaging record
            messaging_data = {
                'source_id': source_id,
                'make': make,
                'model': model,
                'year': extracted_data.get('year', datetime.now().year),
                'positioning_statement': extracted_data.get('positioning_statement'),
                'target_audience': extracted_data.get('target_audience'),
                'messaging_data_enhanced': json.dumps({
                    'positioning_statement': extracted_data.get('positioning_statement'),
                    'target_audience': extracted_data.get('target_audience'),
                    'key_features_intended': extracted_data.get('key_features_intended', []),
                    'brand_attributes_intended': extracted_data.get('brand_attributes_intended', []),
                    'purchase_drivers_intended': extracted_data.get('purchase_drivers_intended', []),
                    'competitive_positioning': extracted_data.get('competitive_positioning', {})
                })
            }
            
            model_result = self.db.supabase.table('oem_model_messaging').insert(messaging_data).execute()
            model_id = model_result.data[0]['id']
            
            logger.info(f"✅ Saved {make} {model} to database (ID: {model_id})")
            return model_id
            
        except Exception as e:
            logger.error(f"❌ Error saving to database: {e}")
            return None
    
    def process_excel_batch(self, excel_path: str, start_index: int = 0, limit: int = 10):
        """Process a batch of records from Excel"""
        try:
            # Read Excel file
            df = pd.read_excel(excel_path)
            
            # Apply batch limits
            batch_df = df.iloc[start_index:start_index + limit]
            
            results = {
                'total': len(batch_df),
                'successful': 0,
                'failed': 0,
                'details': []
            }
            
            print(f"🚀 Processing batch: records {start_index} to {start_index + len(batch_df) - 1}")
            
            for index, row in batch_df.iterrows():
                make = str(row['Fleet']).strip()
                model = str(row['Model']).strip()
                url = str(row['URL']).strip()
                
                record_result = {
                    'index': index,
                    'make': make,
                    'model': model,
                    'url': url,
                    'status': 'pending'
                }
                
                print(f"\n📋 Processing {index}: {make} {model}")
                
                try:
                    # Extract content
                    content = self.extract_content_simple(url)
                    if not content:
                        record_result['status'] = 'failed'
                        record_result['error'] = 'Failed to extract content'
                        results['failed'] += 1
                        results['details'].append(record_result)
                        continue
                    
                    # Extract OEM messaging
                    messaging = self.extract_oem_messaging(content, make, model)
                    if not messaging:
                        record_result['status'] = 'failed'
                        record_result['error'] = 'Failed to extract messaging'
                        results['failed'] += 1
                        results['details'].append(record_result)
                        continue
                    
                    # Save to database
                    model_id = self.save_to_database(messaging, make, model, url)
                    if model_id:
                        record_result['status'] = 'successful'
                        record_result['database_id'] = model_id
                        results['successful'] += 1
                        print(f"✅ {make} {model} completed successfully")
                    else:
                        record_result['status'] = 'failed'
                        record_result['error'] = 'Failed to save to database'
                        results['failed'] += 1
                    
                    results['details'].append(record_result)
                    
                    # Rate limiting
                    time.sleep(2)
                    
                except Exception as e:
                    record_result['status'] = 'failed'
                    record_result['error'] = str(e)
                    results['failed'] += 1
                    results['details'].append(record_result)
                    print(f"❌ {make} {model} failed: {e}")
            
            # Print summary
            print(f"\n{'='*50}")
            print(f"BATCH COMPLETE")
            print(f"Total: {results['total']}")
            print(f"✅ Successful: {results['successful']}")
            print(f"❌ Failed: {results['failed']}")
            print(f"{'='*50}")
            
            return results
            
        except Exception as e:
            print(f"❌ Batch processing error: {e}")
            return {'error': str(e)}

def main():
    """Main function"""
    excel_path = '/Users/richardrierson/Downloads/Model Name List with Press Site URLS.xlsx'
    
    if not os.path.exists(excel_path):
        print(f"❌ Excel file not found: {excel_path}")
        return
    
    processor = SimpleOEMProcessor()
    
    # Process tenth batch of 8 records (final batch)
    start_index = 90
    limit = 8
    
    results = processor.process_excel_batch(excel_path, start_index, limit)
    
    if 'error' not in results:
        print(f"\n📊 Results Summary:")
        for detail in results['details']:
            status_emoji = '✅' if detail['status'] == 'successful' else '❌'
            print(f"{status_emoji} {detail['index']:3}: {detail['make']:10} {detail['model']:15} - {detail['status']}")

if __name__ == "__main__":
    main()