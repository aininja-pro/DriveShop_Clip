#!/usr/bin/env python3
"""
Process all failed records using Enhanced Crawler with ScrapFly
"""
import os
import json
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from src.utils.logger import setup_logger
from src.utils.database import DatabaseManager
from src.utils.enhanced_crawler_manager import EnhancedCrawlerManager
from openai import OpenAI

logger = setup_logger(__name__)

class FailedRecordsProcessor:
    """Process all failed records with enhanced crawler"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.crawler = EnhancedCrawlerManager()
        self.openai_client = OpenAI()
        
    def get_failed_records(self):
        """Get all records that need processing"""
        excel_path = '/Users/richardrierson/Downloads/Model Name List with Press Site URLS.xlsx'
        df = pd.read_excel(excel_path)
        
        failed_records = []
        
        for index, row in df.iterrows():
            make = str(row['Fleet']).strip()
            model = str(row['Model']).strip()
            url = str(row['URL']).strip()
            
            # Check if already exists in database
            existing = self.db.supabase.table('oem_model_messaging')\
                .select('id')\
                .eq('make', make)\
                .eq('model', model)\
                .execute()
            
            if not existing.data:
                failed_records.append({
                    'index': index,
                    'make': make,
                    'model': model,
                    'url': url
                })
        
        return failed_records
    
    def extract_content_enhanced(self, url: str, make: str, model: str) -> str:
        """Extract content using enhanced crawler with ScrapFly"""
        try:
            logger.info(f"🚀 Using enhanced crawler for: {url}")
            
            result = self.crawler.crawl_url(url, make, model)
            
            if result and result.get('success') and result.get('content'):
                content = result.get('content', '')
                
                if len(content.strip()) > 500:  # Lower threshold for difficult sites
                    logger.info(f"✅ Enhanced crawler success: {len(content)} characters")
                    return content
                else:
                    logger.warning(f"⚠️ Content too short: {len(content)} chars")
                    return None
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result'
                logger.warning(f"❌ Enhanced crawler failed: {error_msg}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Enhanced crawler exception: {e}")
            return None
    
    def extract_oem_messaging(self, content: str, make: str, model: str) -> dict:
        """Extract OEM messaging using GPT-4o-mini"""
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
            logger.info(f"🤖 Making OpenAI API call for {make} {model} (GPT-4o-mini)")
            
            response = self.openai_client.chat.completions.create(
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
    
    def save_to_database(self, extracted_data: dict, make: str, model: str, url: str) -> str:
        """Save to database"""
        try:
            # Create source record
            source_data = {
                'make': make,
                'document_title': f"{make} {model} Marketing Material",
                'document_type': 'url',
                'source_url': url,
                'model_year': extracted_data.get('year', 2024),
                'raw_content': ''
            }
            
            source_result = self.db.supabase.table('oem_messaging_sources').insert(source_data).execute()
            source_id = source_result.data[0]['id']
            
            # Create model messaging record
            messaging_data = {
                'source_id': source_id,
                'make': make,
                'model': model,
                'year': extracted_data.get('year', 2024),
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
    
    def process_failed_records(self):
        """Process all failed records with enhanced crawler"""
        
        failed_records = self.get_failed_records()
        
        if not failed_records:
            print("🎉 No failed records found - all processed!")
            return
        
        print(f"🚀 Processing {len(failed_records)} failed records with ScrapFly...")
        
        results = {'successful': 0, 'failed': 0, 'details': []}
        
        for i, record in enumerate(failed_records, 1):
            make = record['make']
            model = record['model']
            url = record['url']
            index = record['index']
            
            print(f"\n{'='*60}")
            print(f"📋 Processing {i}/{len(failed_records)}: Row {index} - {make} {model}")
            print(f"🔗 URL: {url}")
            
            try:
                # Extract content with enhanced crawler
                content = self.extract_content_enhanced(url, make, model)
                
                if not content:
                    print(f"❌ {make} {model}: Failed to extract content")
                    results['failed'] += 1
                    results['details'].append({'index': index, 'make': make, 'model': model, 'status': 'failed', 'error': 'No content extracted'})
                    continue
                
                print(f"📄 Extracted {len(content)} characters")
                
                # Extract OEM messaging
                messaging = self.extract_oem_messaging(content, make, model)
                
                if not messaging:
                    print(f"❌ {make} {model}: Failed to extract messaging")
                    results['failed'] += 1
                    results['details'].append({'index': index, 'make': make, 'model': model, 'status': 'failed', 'error': 'Failed messaging extraction'})
                    continue
                
                # Save to database
                model_id = self.save_to_database(messaging, make, model, url)
                
                if model_id:
                    print(f"✅ {make} {model}: Successfully saved (ID: {model_id})")
                    results['successful'] += 1
                    results['details'].append({'index': index, 'make': make, 'model': model, 'status': 'successful', 'database_id': model_id})
                else:
                    print(f"❌ {make} {model}: Failed to save to database")
                    results['failed'] += 1
                    results['details'].append({'index': index, 'make': make, 'model': model, 'status': 'failed', 'error': 'Database save failed'})
                
            except Exception as e:
                print(f"❌ {make} {model}: Exception - {e}")
                results['failed'] += 1
                results['details'].append({'index': index, 'make': make, 'model': model, 'status': 'failed', 'error': str(e)})
        
        print(f"\n{'='*60}")
        print(f"FAILED RECORDS PROCESSING COMPLETE")
        print(f"📊 Total failed records processed: {len(failed_records)}")
        print(f"✅ Successfully recovered: {results['successful']}")
        print(f"❌ Still failed: {results['failed']}")
        print(f"🎯 New success rate: {(59 + results['successful'])/98*100:.1f}%")
        print(f"{'='*60}")
        
        return results

def main():
    processor = FailedRecordsProcessor()
    results = processor.process_failed_records()

if __name__ == "__main__":
    main()