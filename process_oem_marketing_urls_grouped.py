#!/usr/bin/env python3
"""
Process OEM Marketing URLs from Excel spreadsheet with URL-first grouping
Handles multiple models per URL and provides detailed tracking per Excel record
"""
import os
import json
import time
import pandas as pd
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import openai
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.utils.logger import setup_logger
from src.utils.database import DatabaseManager
from src.utils.enhanced_crawler_manager import EnhancedCrawlerManager

logger = setup_logger(__name__)

class OEMMarketingProcessor:
    """Process OEM marketing URLs with smart URL grouping and detailed tracking"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.crawler = EnhancedCrawlerManager()
        openai.api_key = os.environ.get('OPENAI_API_KEY')
        
    def read_excel_file(self, file_path: str) -> pd.DataFrame:
        """Read the Excel spreadsheet with Make/Model/URL data"""
        try:
            df = pd.read_excel(file_path)
            logger.info(f"Read {len(df)} records from Excel file")
            logger.info(f"Columns: {list(df.columns)}")
            return df
        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            raise
    
    def group_excel_by_url(self, df: pd.DataFrame) -> Dict[str, List[Dict]]:
        """Group Excel records by URL to handle multi-model pages"""
        url_groups = defaultdict(list)
        
        for index, row in df.iterrows():
            url = str(row['URL']).strip()
            record = {
                'excel_index': index,
                'make': str(row['Fleet']).strip(),
                'model': str(row['Model']).strip(),
                'url': url,
                'status': 'pending',
                'error': None,
                'database_id': None
            }
            url_groups[url].append(record)
        
        logger.info(f"Grouped {len(df)} Excel records into {len(url_groups)} unique URLs")
        return dict(url_groups)
    
    def split_content_by_models(self, content: str, make: str) -> Optional[Dict[str, str]]:
        """
        Split multi-model content into sections (enhanced from oem_extractor_unified.py)
        """
        model_sections = {}
        
        # Enhanced model patterns for different makes
        model_patterns = {
            'MAZDA': r'(CX-\d+|MX-\d+|MAZDA\d+)(?:\s+(?:TURBO|SPORT|TOURING|GRAND TOURING|SIGNATURE))?',
            'TOYOTA': r'(CAMRY|COROLLA|RAV4|HIGHLANDER|4RUNNER|TACOMA|TUNDRA|PRIUS|SIENNA)',
            'HONDA': r'(ACCORD|CIVIC|CR-V|PILOT|RIDGELINE|ODYSSEY|FIT|HR-V)',
            'HYUNDAI': r'(KONA|ELANTRA|SONATA|TUCSON|SANTA FE|PALISADE|IONIQ|VENUE)(?:\s+(?:N|ELECTRIC|HYBRID|SEL|LIMITED))?',
            'KIA': r'(FORTE|OPTIMA|SORENTO|SPORTAGE|TELLURIDE|STINGER|SOUL|RIO|EV6|NIRO)',
            'ACURA': r'(TLX|MDX|RDX|ILX|NSX|ADX|INTEGRA)(?:\s+(?:TYPE S|ADVANCE|TECH))?',
            'FORD': r'(F-150|MUSTANG|EXPLORER|ESCAPE|EDGE|BRONCO|RANGER|EXPEDITION)',
            'CHEVROLET': r'(SILVERADO|CAMARO|CORVETTE|EQUINOX|TRAVERSE|TAHOE|SUBURBAN)',
            'BMW': r'([1-8]\s*SERIES|X[1-7]|Z4|i[3-8])(?:\s+(?:M|xDrive))?',
            'MERCEDES': r'(C-CLASS|E-CLASS|S-CLASS|GLA|GLC|GLE|GLS|AMG)',
            'AUDI': r'(A[3-8]|Q[2-8]|TT|R8)(?:\s+(?:QUATTRO|S-LINE))?',
            'VOLKSWAGEN': r'(JETTA|PASSAT|TIGUAN|ATLAS|GOLF|BEETLE)',
            'NISSAN': r'(ALTIMA|SENTRA|ROGUE|PATHFINDER|MURANO|ARMADA|370Z|GT-R)',
            'SUBARU': r'(OUTBACK|FORESTER|CROSSTREK|IMPREZA|LEGACY|ASCENT|WRX)',
            'LEXUS': r'(ES|IS|GS|LS|NX|RX|GX|LX|LC)(?:\s+(?:HYBRID|F SPORT))?'
        }
        
        # Get pattern for this make
        make_upper = make.upper()
        pattern = model_patterns.get(make_upper, r'[A-Z][A-Z0-9\-]+(?:\s+[A-Z]+)?')
        
        # Multiple section detection patterns
        section_patterns = [
            rf'(?:^|\n)({pattern})(?:\s*\n|:|\s+MY|\s+20\d{{2}})',  # Model at start of line
            rf'({pattern})\s*(?:Overview|Features|Specifications|Details)',  # Model + descriptor
            rf'(?:20\d{{2}}\s+)?({pattern})(?:\s+20\d{{2}})?',  # Year + Model or Model + Year
        ]
        
        all_matches = []
        for i, pattern_str in enumerate(section_patterns):
            matches = list(re.finditer(pattern_str, content, re.MULTILINE | re.IGNORECASE))
            for match in matches:
                all_matches.append((match.start(), match.end(), match.group(1).strip().upper(), i))
        
        # Sort by position and remove duplicates
        all_matches.sort()
        unique_matches = []
        seen_models = set()
        
        for start, end, model_name, pattern_idx in all_matches:
            if model_name not in seen_models:
                unique_matches.append((start, end, model_name))
                seen_models.add(model_name)
        
        if len(unique_matches) > 1:  # Multiple models found
            logger.info(f"📚 Found {len(unique_matches)} potential models: {[m[2] for m in unique_matches]}")
            
            for i, (start_pos, _, model_name) in enumerate(unique_matches):
                # Get content until next model or end of document
                if i < len(unique_matches) - 1:
                    end_pos = unique_matches[i + 1][0]
                else:
                    end_pos = len(content)
                
                section_content = content[start_pos:end_pos]
                
                # Only include if section has substantial content
                if len(section_content) > 500:  # Minimum 500 chars
                    model_sections[model_name] = section_content
                    logger.info(f"  ✅ {model_name}: {len(section_content)} chars")
                else:
                    logger.info(f"  ⏭️  {model_name}: Too short ({len(section_content)} chars)")
        
        return model_sections if len(model_sections) > 1 else None
    
    def extract_content_from_url(self, url: str, make: str = "", model: str = "") -> Optional[str]:
        """Extract text content from a webpage URL using Enhanced Crawler Manager"""
        try:
            logger.info(f"🌐 Fetching content from: {url}")
            
            result = self.crawler.crawl_url(url, make, model)
            
            if result and result.get('success'):
                content = result.get('content', '')
                logger.info(f"✅ Extracted {len(content)} characters using {result.get('method', 'unknown method')}")
                return content
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                logger.error(f"❌ Failed to extract content: {error_msg}")
                return None
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None
    
    def extract_oem_messaging(self, content: str, make: str, model: str, url: str) -> Optional[Dict]:
        """
        Extract OEM messaging using the same prompt as existing OEM extractions
        """
        if not content or len(content.strip()) < 200:
            logger.warning(f"Content too short for analysis: {len(content)} chars")
            return None
            
        # Truncate content if too long for API
        max_content_length = 4000
        if len(content) > max_content_length:
            logger.info(f"Truncating content from {len(content)} to {max_content_length} characters")
            content = content[:max_content_length] + "..."
        
        # The exact same prompt used for existing OEM messaging extractions
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
            
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting structured OEM messaging from marketing materials."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse the response
            response_content = response.choices[0].message.content.strip()
            
            # Clean JSON response
            if response_content.startswith('```json'):
                response_content = response_content[7:]
            if response_content.endswith('```'):
                response_content = response_content[:-3]
            
            extracted_data = json.loads(response_content.strip())
            
            # Add metadata
            extracted_data['make'] = make
            extracted_data['model'] = extracted_data.get('model_detected', model)
            extracted_data['source_type'] = 'url'
            extracted_data['source_path'] = url
            extracted_data['source_title'] = f"{make} {model} Marketing Material"
            extracted_data['extracted_date'] = datetime.now().isoformat()
            
            logger.info(f"✅ Successfully extracted messaging for {make} {model}")
            return extracted_data
            
        except Exception as e:
            logger.error(f"❌ Error extracting messaging for {make} {model}: {e}")
            return None
    
    def save_to_database(self, extracted_data: Dict) -> Optional[str]:
        """Save extracted OEM messaging to database"""
        try:
            # Check if this make/model already exists
            existing = self.db.supabase.table('oem_model_messaging')\
                .select('id')\
                .eq('make', extracted_data['make'])\
                .eq('model', extracted_data['model'])\
                .execute()
            
            if existing.data:
                logger.info(f"⏭️  {extracted_data['make']} {extracted_data['model']} already exists in database")
                return existing.data[0]['id']
            
            # Create source record
            source_data = {
                'make': extracted_data['make'],
                'document_title': extracted_data['source_title'],
                'document_type': extracted_data['source_type'],
                'source_url': extracted_data['source_path'] if extracted_data['source_type'] == 'url' else None,
                'source_file_path': extracted_data['source_path'] if extracted_data['source_type'] != 'url' else None,
                'model_year': extracted_data.get('year', datetime.now().year),
                'raw_content': ''
            }
            
            source_result = self.db.supabase.table('oem_messaging_sources').insert(source_data).execute()
            source_id = source_result.data[0]['id']
            
            # Create model messaging record
            messaging_data = {
                'source_id': source_id,
                'make': extracted_data['make'],
                'model': extracted_data['model'],
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
            
            logger.info(f"✅ Saved {extracted_data['make']} {extracted_data['model']} to database (ID: {model_id})")
            return model_id
            
        except Exception as e:
            logger.error(f"❌ Error saving to database: {e}")
            return None
    
    def process_excel_file(self, excel_path: str, start_index: int = 0, limit: int = None) -> Dict[str, Any]:
        """
        Process Excel file with URL-first grouping and detailed per-record tracking
        """
        try:
            # Read Excel file
            df = self.read_excel_file(excel_path)
            
            # Apply start_index and limit to original dataframe
            if limit:
                df = df.iloc[start_index:start_index + limit]
            else:
                df = df.iloc[start_index:]
            
            # Group by URL
            url_groups = self.group_excel_by_url(df)
            
            # Initialize tracking
            all_records = []
            for records in url_groups.values():
                all_records.extend(records)
            
            results = {
                'total_excel_records': len(all_records),
                'unique_urls': len(url_groups),
                'successful_records': 0,
                'failed_records': 0,
                'skipped_records': 0,
                'record_details': all_records,
                'url_processing_summary': []
            }
            
            logger.info(f"Processing {len(all_records)} Excel records from {len(url_groups)} unique URLs")
            
            # Process each unique URL
            for url_idx, (url, records) in enumerate(url_groups.items(), 1):
                url_summary = {
                    'url': url,
                    'expected_models': [r['model'] for r in records],
                    'excel_indices': [r['excel_index'] for r in records],
                    'content_extracted': False,
                    'models_found': [],
                    'models_processed': []
                }
                
                logger.info(f"\n{'='*60}")
                logger.info(f"URL {url_idx}/{len(url_groups)}: {url}")
                logger.info(f"Expected models: {[r['model'] for r in records]}")
                
                try:
                    # Extract content from URL
                    make = records[0]['make']  # All records for same URL should have same make
                    content = self.extract_content_from_url(url, make)
                    if not content:
                        # Mark all records for this URL as failed
                        for record in records:
                            record['status'] = 'failed'
                            record['error'] = 'Failed to extract content from URL'
                            results['failed_records'] += 1
                        url_summary['error'] = 'Content extraction failed'
                        results['url_processing_summary'].append(url_summary)
                        continue
                    
                    url_summary['content_extracted'] = True
                    
                    # Try to split content by models
                    model_sections = self.split_content_by_models(content, make)
                    
                    if model_sections:
                        # Multi-model page detected
                        logger.info(f"📚 Multi-model page detected. Found sections: {list(model_sections.keys())}")
                        url_summary['models_found'] = list(model_sections.keys())
                        
                        # Process each model section
                        for model_name, model_content in model_sections.items():
                            # Find matching Excel record(s)
                            matching_records = []
                            for record in records:
                                if self._models_match(record['model'], model_name):
                                    matching_records.append(record)
                            
                            if matching_records:
                                # Process for the first matching record
                                record = matching_records[0]
                                success = self._process_single_model(model_content, record, url_summary)
                                if success:
                                    results['successful_records'] += 1
                                    # Mark other matching records as successful too (same data)
                                    for other_record in matching_records[1:]:
                                        other_record['status'] = 'successful'
                                        other_record['database_id'] = record['database_id']
                                        results['successful_records'] += 1
                                else:
                                    results['failed_records'] += len(matching_records)
                                    for mr in matching_records:
                                        mr['status'] = 'failed'
                                        mr['error'] = record['error']
                            else:
                                # Model found in content but not in Excel - create entry anyway
                                logger.info(f"📋 Found model '{model_name}' in content but not in Excel records")
                                dummy_record = {
                                    'make': make,
                                    'model': model_name,
                                    'url': url,
                                    'status': 'bonus_found',
                                    'excel_index': 'N/A'
                                }
                                self._process_single_model(model_content, dummy_record, url_summary)
                        
                        # Mark any unmatched Excel records as failed
                        for record in records:
                            if record['status'] == 'pending':
                                record['status'] = 'failed'
                                record['error'] = f"Model '{record['model']}' not found in multi-model content"
                                results['failed_records'] += 1
                    
                    else:
                        # Single model page or couldn't split - process for each expected model
                        logger.info(f"📄 Single model page. Processing for each expected model.")
                        
                        for record in records:
                            success = self._process_single_model(content, record, url_summary)
                            if success:
                                results['successful_records'] += 1
                            else:
                                results['failed_records'] += 1
                    
                    # Rate limiting
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing URL {url}: {e}")
                    for record in records:
                        record['status'] = 'failed'
                        record['error'] = f"URL processing error: {str(e)}"
                        results['failed_records'] += 1
                    url_summary['error'] = str(e)
                
                results['url_processing_summary'].append(url_summary)
            
            # Final summary
            logger.info(f"\n{'='*60}")
            logger.info(f"PROCESSING COMPLETE")
            logger.info(f"Total Excel records: {results['total_excel_records']}")
            logger.info(f"Unique URLs processed: {results['unique_urls']}")
            logger.info(f"✅ Successful: {results['successful_records']}")
            logger.info(f"❌ Failed: {results['failed_records']}")
            logger.info(f"⏭️  Skipped: {results['skipped_records']}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error processing Excel file: {e}")
            return {'error': str(e)}
    
    def _models_match(self, excel_model: str, found_model: str) -> bool:
        """Check if Excel model name matches found model name (fuzzy matching)"""
        excel_clean = excel_model.upper().strip()
        found_clean = found_model.upper().strip()
        
        # Exact match
        if excel_clean == found_clean:
            return True
        
        # Base model match (e.g., "KONA" matches "KONA ELECTRIC")
        if excel_clean in found_clean or found_clean in excel_clean:
            return True
        
        # Handle common variations
        variations = {
            'INTEGRA': ['INTEGRA TYPE S'],
            'KONA': ['KONA ELECTRIC', 'KONA N'],
            'IONIQ': ['IONIQ 5', 'IONIQ 6'],
        }
        
        for base, variants in variations.items():
            if excel_clean == base and found_clean in variants:
                return True
            if found_clean == base and excel_clean in variants:
                return True
        
        return False
    
    def _process_single_model(self, content: str, record: Dict, url_summary: Dict) -> bool:
        """Process a single model and update the record"""
        try:
            # Extract messaging
            extracted_data = self.extract_oem_messaging(
                content, 
                record['make'], 
                record['model'], 
                record['url']
            )
            
            if not extracted_data:
                record['status'] = 'failed'
                record['error'] = 'Failed to extract messaging from content'
                return False
            
            # Save to database
            model_id = self.save_to_database(extracted_data)
            
            if model_id:
                record['status'] = 'successful'
                record['database_id'] = model_id
                url_summary['models_processed'].append(record['model'])
                logger.info(f"✅ Successfully processed {record['make']} {record['model']}")
                return True
            else:
                record['status'] = 'failed'
                record['error'] = 'Failed to save to database'
                return False
                
        except Exception as e:
            record['status'] = 'failed'
            record['error'] = str(e)
            logger.error(f"❌ Error processing {record['make']} {record['model']}: {e}")
            return False
    
    def generate_detailed_report(self, results: Dict) -> str:
        """Generate a detailed report for each Excel record"""
        report = []
        report.append("="*80)
        report.append("DETAILED PROCESSING REPORT")
        report.append("="*80)
        report.append(f"Total Excel Records: {results['total_excel_records']}")
        report.append(f"Unique URLs: {results['unique_urls']}")
        report.append(f"✅ Successful: {results['successful_records']}")
        report.append(f"❌ Failed: {results['failed_records']}")
        report.append(f"⏭️  Skipped: {results['skipped_records']}")
        report.append("")
        
        # Per-record details
        report.append("RECORD-BY-RECORD RESULTS:")
        report.append("-" * 40)
        
        for record in results['record_details']:
            status_emoji = {
                'successful': '✅',
                'failed': '❌',
                'skipped': '⏭️',
                'bonus_found': '🎁'
            }.get(record['status'], '❓')
            
            line = f"{status_emoji} Row {record.get('excel_index', 'N/A'):3} | {record['make']:10} | {record['model']:20} | {record['status']:12}"
            if record.get('database_id'):
                line += f" | DB ID: {record['database_id']}"
            if record.get('error'):
                line += f" | Error: {record['error']}"
            
            report.append(line)
        
        return "\n".join(report)


def main():
    """Main function to process the Excel file"""
    excel_path = '/Users/richardrierson/Downloads/Model Name List with Press Site URLS.xlsx'
    
    if not os.path.exists(excel_path):
        print(f"❌ Excel file not found: {excel_path}")
        return
    
    processor = OEMMarketingProcessor()
    
    # Processing parameters  
    start_index = 0  # Start from beginning
    limit = 10       # Process 10 records at a time
    
    print(f"🚀 Starting OEM marketing extraction with URL grouping...")
    print(f"📁 File: {excel_path}")
    print(f"🔢 Starting from index: {start_index}")
    print(f"📊 Limit: {limit if limit else 'All records'}")
    
    results = processor.process_excel_file(excel_path, start_index, limit)
    
    if 'error' in results:
        print(f"❌ Processing failed: {results['error']}")
        return
    
    # Generate and display detailed report
    report = processor.generate_detailed_report(results)
    print("\n" + report)
    
    # Save report to file
    report_file = f"oem_processing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Detailed report saved to: {report_file}")

if __name__ == "__main__":
    main()