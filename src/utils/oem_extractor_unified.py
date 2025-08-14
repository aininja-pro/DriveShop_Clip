"""
Unified OEM Message Extractor - Handles PDFs, URLs, and multi-model documents
Extracts structured messaging data matching our enhanced sentiment analysis format
"""
import os
import json
import re
from typing import Dict, List, Any, Union
from dataclasses import dataclass
from datetime import datetime
import PyPDF2
import requests
from bs4 import BeautifulSoup

from src.utils.logger import setup_logger
from src.utils.database import DatabaseManager
import openai
from src.utils.config import Config

logger = setup_logger(__name__)

@dataclass
class OEMDocument:
    """Represents a source document containing OEM messaging"""
    source_type: str  # 'pdf', 'url', 'file'
    source_path: str
    title: str
    make: str
    content: str
    extracted_date: datetime
    model_sections: Dict[str, str] = None  # Model name -> content mapping

class OEMExtractorUnified:
    """Extract OEM messaging from multiple sources and formats"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.config = Config()
        openai.api_key = self.config.get('OPENAI_API_KEY')
        
    def extract(self, source: str, make: str = None) -> List[Dict]:
        """
        Main extraction method - handles PDFs, URLs, or text files
        Returns list of extracted model messages
        """
        try:
            # Determine source type and extract content
            if source.lower().endswith('.pdf'):
                document = self._extract_from_pdf(source, make)
            elif source.startswith(('http://', 'https://')):
                document = self._extract_from_url(source, make)
            else:
                document = self._extract_from_file(source, make)
            
            # Check if document contains multiple models
            if document.model_sections:
                # Process each model separately
                results = []
                for model_name, model_content in document.model_sections.items():
                    result = self._extract_model_messaging(
                        content=model_content,
                        make=document.make,
                        model=model_name,
                        source_doc=document
                    )
                    if result:
                        results.append(result)
                return results
            else:
                # Single model or brand-level document
                result = self._extract_model_messaging(
                    content=document.content,
                    make=document.make,
                    model=None,  # Will be detected from content
                    source_doc=document
                )
                return [result] if result else []
                
        except Exception as e:
            logger.error(f"❌ Error extracting from {source}: {e}")
            raise
    
    def _extract_from_pdf(self, pdf_path: str, make: str = None) -> OEMDocument:
        """Extract text from PDF, detecting multiple models if present"""
        logger.info(f"📄 Extracting from PDF: {pdf_path}")
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract all text first
            full_text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                full_text += page.extract_text() + "\n\n"
            
            # Try to detect make from content if not provided
            if not make:
                make = self._detect_make(full_text)
            
            # Detect if this is a multi-model document
            model_sections = self._split_into_models(full_text, make)
            
            return OEMDocument(
                source_type='pdf',
                source_path=pdf_path,
                title=os.path.basename(pdf_path),
                make=make,
                content=full_text,
                extracted_date=datetime.now(),
                model_sections=model_sections
            )
    
    def _extract_from_url(self, url: str, make: str = None) -> OEMDocument:
        """Extract content from URL"""
        logger.info(f"🌐 Extracting from URL: {url}")
        
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Try to detect make from content if not provided
        if not make:
            make = self._detect_make(text)
        
        # Get title
        title = soup.find('title').string if soup.find('title') else url
        
        # Check for multiple models
        model_sections = self._split_into_models(text, make)
        
        return OEMDocument(
            source_type='url',
            source_path=url,
            title=title,
            make=make,
            content=text,
            extracted_date=datetime.now(),
            model_sections=model_sections
        )
    
    def _split_into_models(self, content: str, make: str) -> Dict[str, str]:
        """
        Split multi-model documents into sections
        Returns dict of model_name -> content
        """
        model_sections = {}
        
        # Common model patterns for different makes
        model_patterns = {
            'Mazda': r'(CX-\d+|MX-\d+|MAZDA\d+)(?:\s+(?:TURBO|SPORT|TOURING|GRAND TOURING|SIGNATURE))?',
            'Toyota': r'(CAMRY|COROLLA|RAV4|HIGHLANDER|4RUNNER|TACOMA|TUNDRA)',
            'Honda': r'(ACCORD|CIVIC|CR-V|PILOT|RIDGELINE|ODYSSEY)',
            # Add more makes as needed
        }
        
        # Get pattern for this make
        pattern = model_patterns.get(make, r'[A-Z][A-Z0-9\-]+(?:\s+[A-Z]+)?')
        
        # Find all model mentions that look like section headers
        # Look for model names at start of line or after specific markers
        section_pattern = rf'(?:^|\n|MY\s*\d{{4}}\s+)({pattern})(?:\s*\n|:|\s+MY|\s+\d{{4}})'
        
        matches = list(re.finditer(section_pattern, content, re.MULTILINE | re.IGNORECASE))
        
        if len(matches) > 1:  # Multiple models found
            logger.info(f"📚 Found {len(matches)} models in document")
            
            for i, match in enumerate(matches):
                model_name = match.group(1).strip().upper()
                start_pos = match.start()
                
                # Get content until next model or end of document
                if i < len(matches) - 1:
                    end_pos = matches[i + 1].start()
                else:
                    end_pos = len(content)
                
                section_content = content[start_pos:end_pos]
                
                # Only include if section has substantial content
                if len(section_content) > 500:  # Minimum 500 chars
                    model_sections[model_name] = section_content
                    logger.info(f"  - {model_name}: {len(section_content)} chars")
        
        return model_sections if len(model_sections) > 1 else None
    
    def _detect_make(self, content: str) -> str:
        """Detect vehicle make from content"""
        makes = ['Mazda', 'Toyota', 'Honda', 'Ford', 'Chevrolet', 'BMW', 'Mercedes-Benz', 
                 'Audi', 'Volkswagen', 'Hyundai', 'Kia', 'Nissan', 'Subaru']
        
        content_lower = content.lower()
        for make in makes:
            if make.lower() in content_lower:
                return make
        
        return None
    
    def _extract_model_messaging(self, content: str, make: str, model: str, 
                                source_doc: OEMDocument) -> Dict:
        """
        Use GPT-4 to extract structured messaging matching our sentiment format
        """
        # If model not specified, try to detect it
        if not model:
            model = self._detect_model_from_content(content, make)
        
        prompt = f"""
You are an expert at extracting OEM (Original Equipment Manufacturer) intended messaging from marketing materials.

Analyze this {make} {model if model else ''} content and extract the following structured information:

CONTENT:
{content[:4000]}  # Limit to 4000 chars for API limits

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
            # Use GPT to extract structured data
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting structured OEM messaging from marketing materials."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            extracted_data = json.loads(response.choices[0].message.content)
            
            # Add metadata
            extracted_data['make'] = make
            extracted_data['model'] = extracted_data.get('model_detected', model)
            extracted_data['source_type'] = source_doc.source_type
            extracted_data['source_path'] = source_doc.source_path
            extracted_data['source_title'] = source_doc.title
            extracted_data['extracted_date'] = source_doc.extracted_date.isoformat()
            
            logger.info(f"✅ Extracted messaging for {make} {extracted_data['model']}")
            return extracted_data
            
        except Exception as e:
            logger.error(f"❌ Error extracting messaging: {e}")
            return None
    
    def _detect_model_from_content(self, content: str, make: str) -> str:
        """Try to detect model name from content"""
        # This would have make-specific logic
        # For now, simple regex
        model_match = re.search(r'(?:^|\s)([A-Z]+[\-\s]?[\w\d]+)(?:\s+MY|\s+\d{4})', content)
        if model_match:
            return model_match.group(1)
        return "Unknown"
    
    def save_to_database(self, extracted_data: Dict) -> str:
        """Save extracted OEM messaging to database"""
        try:
            # Create source record
            source_data = {
                'make': extracted_data['make'],
                'document_title': extracted_data['source_title'],
                'document_type': extracted_data['source_type'],
                'source_url': extracted_data['source_path'] if extracted_data['source_type'] == 'url' else None,
                'source_file_path': extracted_data['source_path'] if extracted_data['source_type'] != 'url' else None,
                'model_year': extracted_data.get('year', datetime.now().year),
                'raw_content': ''  # Could store full content if needed
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
            
            logger.info(f"✅ Saved OEM messaging for {extracted_data['make']} {extracted_data['model']} to database")
            return model_id
            
        except Exception as e:
            logger.error(f"❌ Error saving to database: {e}")
            raise


# Example usage
if __name__ == "__main__":
    extractor = OEMExtractorUnified()
    
    # Example 1: Extract from multi-model PDF
    print("📄 Extracting from Mazda PDF...")
    results = extractor.extract(
        source="2025 Model One Pagers w Pricing FINAL.pdf",
        make="Mazda"
    )
    print(f"Found {len(results)} models")
    
    # Example 2: Extract from URL
    print("\n🌐 Extracting from press release...")
    results = extractor.extract(
        source="https://www.mazdausa.com/press-release/2024-cx-50",
        make="Mazda"
    )
    
    # Save first result
    if results:
        model_id = extractor.save_to_database(results[0])
        print(f"Saved to database with ID: {model_id}")