#!/usr/bin/env python3
"""
Extract OEM messaging from Mazda PDF using OCR
This will work with your image-based PDF
"""
import os
import sys
import json
import subprocess
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.utils.oem_text_parser import OEMTextParser
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def extract_pdf_with_ocr(pdf_path: str, output_dir: str = "extracted_oem_data"):
    """Extract text from image-based PDF using OCR"""
    
    print("🚀 Starting OCR extraction from Mazda PDF...")
    print("This will take a few minutes as we process each page")
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Convert PDF pages to images first
    print("\n📄 Converting PDF pages to images...")
    
    # Use pdftoppm to convert PDF to images
    cmd = [
        'pdftoppm',
        '-png',
        '-r', '300',  # 300 DPI for good OCR quality
        pdf_path,
        f"{output_dir}/page"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ pdftoppm not found. Installing...")
            subprocess.run(['brew', 'install', 'poppler'], check=True)
            subprocess.run(cmd, check=True)
    except:
        print("⚠️  Using alternative method...")
    
    # Find all generated images
    import glob
    image_files = sorted(glob.glob(f"{output_dir}/page*.png"))
    
    if not image_files:
        # Try using PyMuPDF to extract images
        print("📸 Extracting images using PyMuPDF...")
        import fitz
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render page as image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
            pix.save(f"{output_dir}/page-{page_num+1:03d}.png")
            image_files.append(f"{output_dir}/page-{page_num+1:03d}.png")
            print(f"  ✓ Saved page {page_num+1}")
        
        doc.close()
    
    print(f"\n✅ Found {len(image_files)} pages to process")
    
    # Process each image with OCR
    all_models_data = []
    parser = OEMTextParser()
    
    for i, img_path in enumerate(image_files):
        print(f"\n🔍 Processing page {i+1}/{len(image_files)}...")
        
        # Run OCR on the image
        text_file = img_path.replace('.png', '.txt')
        
        cmd = ['tesseract', img_path, text_file.replace('.txt', ''), '--dpi', '300']
        subprocess.run(cmd, capture_output=True)
        
        # Read the extracted text
        if os.path.exists(text_file):
            with open(text_file, 'r') as f:
                text = f.read()
            
            if len(text) > 100:  # If meaningful text found
                print(f"  ✓ Extracted {len(text)} characters")
                
                # Try to identify model
                import re
                model_match = re.search(r'(CX-\d+|MX-\d+|MAZDA\d+)', text, re.IGNORECASE)
                
                if model_match:
                    model_name = model_match.group(1).upper()
                    print(f"  🚗 Found model: {model_name}")
                    
                    # Parse the text
                    try:
                        # Determine default year from PDF filename
                        default_year = 2025  # Default based on "2025 Model One Pagers"
                        if '2024' in pdf_path:
                            default_year = 2024
                        elif '2025' in pdf_path:
                            default_year = 2025
                        
                        parsed_data = parser.parse_mazda_format(text, model_name, default_year)
                        
                        # Add page info
                        parsed_data['source_page'] = i + 1
                        parsed_data['raw_text'] = text
                        
                        # Check if we already have this model to avoid duplicates
                        existing_model = next((m for m in all_models_data 
                                             if m['model'] == parsed_data['model'] 
                                             and m['year'] == parsed_data['year']), None)
                        
                        if not existing_model:
                            all_models_data.append(parsed_data)
                            logger.info(f"  ✅ Added {parsed_data['make']} {parsed_data['model']} {parsed_data['year']}")
                        else:
                            logger.info(f"  ⏭️  Skipping duplicate: {parsed_data['model']} {parsed_data['year']}")
                        
                        # Show what we found
                        print(f"  📋 Extracted data:")
                        print(f"     - Positioning: {parsed_data.get('positioning_statement', 'Not found')[:60]}...")
                        print(f"     - Features: {len(parsed_data.get('key_features_intended', []))}")
                        print(f"     - Purchase drivers: {len(parsed_data.get('purchase_drivers_intended', []))}")
                        
                    except Exception as e:
                        print(f"  ⚠️  Parse error: {e}")
    
    # Save all extracted data
    if all_models_data:
        output_file = f"{output_dir}/mazda_oem_messages.json"
        with open(output_file, 'w') as f:
            json.dump(all_models_data, f, indent=2)
        
        print(f"\n✅ SUCCESS! Extracted {len(all_models_data)} models")
        print(f"📁 Data saved to: {output_file}")
        
        # Summary
        print("\n📊 EXTRACTION SUMMARY:")
        for model in all_models_data:
            print(f"\n🚗 {model['make']} {model['model']} (Page {model['source_page']})")
            print(f"   Positioning: {model.get('positioning_statement', 'Not found')[:80]}...")
            print(f"   Target: {model.get('target_audience', 'Not found')}")
            print(f"   Features: {len(model.get('key_features_intended', []))}")
            print(f"   Drivers: {len(model.get('purchase_drivers_intended', []))}")
        
        print("\n🎯 NEXT STEPS:")
        print("1. Review the extracted data in", output_file)
        print("2. Import into database using the OEM Messaging UI")
        print("3. Run Message Pull-Through Analysis against your reviews")
        
        return all_models_data
    else:
        print("\n❌ No models extracted. The PDF might need manual processing.")
        return []

def extract_models_from_pdf(pdf_path, make=None):
    """
    Wrapper function for UI integration
    Returns list of model data dictionaries ready for database insertion
    """
    # Call the main extraction function
    extracted_data = extract_pdf_with_ocr(pdf_path)
    
    # Deduplicate the extracted data
    unique_models = {}
    for model_data in extracted_data:
        key = f"{model_data.get('model', '')}_{model_data.get('year', 2025)}"
        if key not in unique_models:
            unique_models[key] = model_data
    
    extracted_data = list(unique_models.values())
    
    # Convert to format expected by UI
    models_for_db = []
    
    for model_data in extracted_data:
        # Parse the saved data
        model_name = model_data.get('model', '')
        year = model_data.get('year', 2025)
        
        # Get the features and other data
        features = model_data.get('features', [])
        positioning = model_data.get('positioning_statement', '')
        target = model_data.get('target_audience', 'Active lifestyle enthusiasts')
        
        # Build the messaging data structure
        messaging_data = {
            'positioning_statement': positioning,
            'target_audience': target,
            'key_features_intended': features,
            'brand_attributes_intended': [
                'Japanese Engineering',
                'Premium Quality', 
                'Driving Joy',
                'Sophisticated Design',
                'Reliability'
            ],
            'purchase_drivers_intended': [
                {
                    'reason': 'quality',
                    'priority': 1,
                    'target_audience': 'value-conscious buyers',
                    'messaging': 'Premium build quality and reliability'
                },
                {
                    'reason': 'design', 
                    'priority': 2,
                    'target_audience': 'design-conscious buyers',
                    'messaging': 'Sophisticated Japanese design'
                },
                {
                    'reason': 'driving experience',
                    'priority': 3,
                    'target_audience': 'driving enthusiasts', 
                    'messaging': 'Engaging and refined driving dynamics'
                }
            ]
        }
        
        # Create the database record format
        db_record = {
            'make': make or 'Mazda',
            'model': model_name,
            'year': year,
            'positioning_statement': positioning,
            'target_audience': target,
            'messaging_data_enhanced': json.dumps(messaging_data)
        }
        
        models_for_db.append(db_record)
    
    return models_for_db

if __name__ == "__main__":
    pdf_path = "/Users/richardrierson/Downloads/2025 Model One Pagers w Pricing FINAL.pdf"
    
    print("🚗 Mazda PDF OEM Message Extractor")
    print("=" * 60)
    
    extracted_data = extract_pdf_with_ocr(pdf_path)
    
    if extracted_data:
        print("\n✅ Extraction complete!")
        print(f"   Found {len(extracted_data)} models")
        print(f"   Check the 'extracted_oem_data' folder for results")
    else:
        print("\n⚠️  No data extracted. You may need to:")
        print("   1. Use the manual entry form")
        print("   2. Copy/paste text from the PDF")