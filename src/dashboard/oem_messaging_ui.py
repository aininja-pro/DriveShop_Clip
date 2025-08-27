"""
OEM Messaging Input UI - Streamlit interface for capturing OEM intended messages
Allows manual input and file/URL extraction
"""
import streamlit as st
import json
from datetime import datetime
from src.utils.database import get_database
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Use cached database connection
@st.cache_resource
def get_cached_db():
    return get_database()

def display_oem_messaging_tab():
    """Display the OEM Messaging input interface"""
    st.markdown("## 📢 OEM Messaging Capture")
    st.markdown("---")
    
    # Input method selection
    input_method = st.radio(
        "Choose input method:",
        ["Manual Entry", "Extract from PDF", "Extract from URL"]
    )
    
    if input_method == "Manual Entry":
        display_manual_entry()
    elif input_method == "Extract from PDF":
        display_pdf_extraction()
    else:
        display_url_extraction()

def display_manual_entry():
    """Manual entry form for OEM messaging"""
    st.markdown("### 📝 Manual OEM Messaging Entry")
    
    col1, col2 = st.columns(2)
    
    with col1:
        make = st.text_input("Make", placeholder="e.g., Mazda")
        model = st.text_input("Model", placeholder="e.g., CX-50")
    
    with col2:
        year = st.number_input("Year", min_value=2020, max_value=2030, value=2024)
        trim = st.text_input("Trim (optional)", placeholder="e.g., Turbo Premium")
    
    # Positioning
    st.markdown("### 🎯 Positioning")
    positioning = st.text_area(
        "Positioning Statement",
        placeholder="e.g., CX-50 serves as Mazda's next step in off-road capable & outdoor adventure SUV...",
        height=100
    )
    
    target_audience = st.text_input(
        "Target Audience",
        placeholder="e.g., active lifestyle enthusiasts, outdoor adventurers"
    )
    
    # Key Features
    st.markdown("### 🔑 Key Features (OEM Intended)")
    st.info("Add the features the OEM wants to emphasize. Aim for 10 features.")
    
    features = []
    num_features = st.number_input("Number of features", min_value=1, max_value=15, value=5)
    
    for i in range(num_features):
        with st.expander(f"Feature {i+1}", expanded=(i < 3)):
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                feature_name = st.text_input(
                    "Feature Name",
                    key=f"feature_name_{i}",
                    placeholder="e.g., All-Wheel Drive"
                )
            with col2:
                category = st.selectbox(
                    "Category",
                    ["performance", "technology", "design", "safety", "comfort", "utility"],
                    key=f"feature_cat_{i}"
                )
            with col3:
                priority = st.selectbox(
                    "Priority",
                    ["primary", "secondary", "tertiary"],
                    key=f"feature_priority_{i}"
                )
            
            messaging = st.text_area(
                "How should this be described?",
                key=f"feature_msg_{i}",
                placeholder="e.g., Standard i-Activ AWD for all-weather confidence",
                height=80
            )
            
            if feature_name:
                features.append({
                    "feature": feature_name,
                    "category": category,
                    "priority": priority,
                    "messaging": messaging,
                    "target_sentiment": "positive"
                })
    
    # Brand Attributes
    st.markdown("### 🏷️ Brand Attributes")
    brand_attrs = st.text_area(
        "Enter brand attributes (one per line)",
        placeholder="Premium Quality\nJapanese Engineering\nDriving Joy\nOutdoor Adventure",
        height=100
    )
    brand_attributes = [attr.strip() for attr in brand_attrs.split('\n') if attr.strip()]
    
    # Purchase Drivers
    st.markdown("### 💰 Purchase Drivers")
    st.info("Why would someone buy this vehicle? List in order of importance.")
    
    drivers = []
    num_drivers = st.number_input("Number of purchase drivers", min_value=1, max_value=6, value=3)
    
    for i in range(num_drivers):
        with st.expander(f"Purchase Driver {i+1}", expanded=(i < 2)):
            col1, col2 = st.columns(2)
            with col1:
                reason = st.text_input(
                    "Reason",
                    key=f"driver_reason_{i}",
                    placeholder="e.g., interior volume, value for money"
                )
            with col2:
                audience = st.text_input(
                    "Target Audience",
                    key=f"driver_audience_{i}",
                    placeholder="e.g., families, value seekers"
                )
            
            if reason:
                drivers.append({
                    "reason": reason,
                    "priority": i + 1,
                    "target_audience": audience,
                    "messaging": ""
                })
    
    # Competitive Positioning
    st.markdown("### 🚗 Competitive Positioning")
    competitors = st.text_area(
        "Main competitors (one per line)",
        placeholder="Toyota RAV4\nHonda CR-V\nSubaru Outback",
        height=80
    )
    
    market_position = st.text_input(
        "Market Positioning",
        placeholder="e.g., The outdoor adventure SUV with Mazda driving dynamics"
    )
    
    # Save button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("💾 Save OEM Messaging", type="primary"):
            if make and model and year:
                save_oem_messaging({
                    "make": make,
                    "model": model,
                    "year": year,
                    "trim": trim,
                    "positioning_statement": positioning,
                    "target_audience": target_audience,
                    "key_features_intended": features,
                    "brand_attributes_intended": brand_attributes,
                    "purchase_drivers_intended": drivers,
                    "competitive_positioning": {
                        "competitors": [c.strip() for c in competitors.split('\n') if c.strip()],
                        "market_positioning": market_position
                    }
                })
            else:
                st.error("Please fill in Make, Model, and Year")
    
    with col2:
        if st.button("🔄 Clear Form"):
            st.rerun()

def display_pdf_extraction():
    """PDF extraction interface"""
    st.markdown("### 📄 Extract from PDF")
    
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    if uploaded_file:
        st.success(f"✅ Uploaded: {uploaded_file.name}")
        
        make = st.text_input("Make (leave blank to auto-detect)", placeholder="e.g., Mazda")
        
        col1, col2 = st.columns(2)
        with col1:
            extract_mode = st.radio("Extraction Mode", ["Extract All Models", "Update Specific Models"])
        
        with col2:
            if extract_mode == "Update Specific Models":
                models_to_update = st.multiselect("Select models to update", 
                    ["CX-30", "CX-5", "CX-50", "CX-70", "CX-90", "MX-5", "MX-30"])
        
        if st.button("🔍 Extract OEM Messaging", type="primary"):
            with st.spinner("Extracting messaging from PDF..."):
                try:
                    # Save uploaded file temporarily
                    import tempfile
                    import os
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(uploaded_file.getbuffer())
                        tmp_path = tmp_file.name
                    
                    # Run extraction
                    from extract_mazda_pdf import extract_models_from_pdf
                    results = extract_models_from_pdf(tmp_path, make or None)
                    
                    # Clean up temp file
                    os.unlink(tmp_path)
                    
                    if results:
                        st.success(f"✅ Successfully extracted {len(results)} models!")
                        
                        # Show what was extracted
                        updated_count = 0
                        for model_data in results:
                            st.write(f"- {model_data['make']} {model_data['model']} {model_data['year']}")
                            
                            # If updating specific models, only update those
                            if extract_mode == "Update Specific Models":
                                if model_data['model'] not in models_to_update:
                                    continue
                            
                            try:
                                # Check if exists and update
                                db = get_cached_db()
                                existing = db.supabase.table('oem_model_messaging')\
                                    .select('id')\
                                    .eq('make', model_data['make'])\
                                    .eq('model', model_data['model'])\
                                    .eq('year', model_data['year'])\
                                    .execute()
                                
                                if existing.data and len(existing.data) > 0:
                                    # Handle multiple records - update the first one
                                    if len(existing.data) > 1:
                                        st.warning(f"⚠️ Found {len(existing.data)} records for {model_data['model']} {model_data['year']}. Updating first one.")
                                    
                                    # Update existing
                                    result = db.supabase.table('oem_model_messaging')\
                                        .update(model_data)\
                                        .eq('id', existing.data[0]['id'])\
                                        .execute()
                                    st.info(f"✅ Updated: {model_data['make']} {model_data['model']} {model_data['year']}")
                                    updated_count += 1
                                else:
                                    # Insert new
                                    result = db.supabase.table('oem_model_messaging')\
                                        .insert(model_data)\
                                        .execute()
                                    st.info(f"➕ Added new: {model_data['make']} {model_data['model']} {model_data['year']}")
                                    updated_count += 1
                                
                            except Exception as e:
                                st.error(f"❌ Failed to update {model_data['model']} {model_data['year']}: {str(e)}")
                        
                        if updated_count > 0:
                            st.balloons()
                            st.success(f"🎉 Successfully updated {updated_count} models! Check the Message Pull-Through Analysis tab.")
                        else:
                            st.warning("⚠️ No models were updated. They may have been filtered out or errors occurred.")
                    else:
                        st.error("❌ No models extracted from PDF")
                        
                except Exception as e:
                    st.error(f"❌ Extraction failed: {str(e)}")
                    st.info("This PDF might have a different format. Try Manual Entry instead.")

def display_url_extraction():
    """URL extraction interface with smart method detection"""
    st.markdown("### 🌐 Extract from URL")
    
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        url = st.text_input(
            "Enter URL",
            placeholder="https://www.volvocars.com/us/cars/xc60-hybrid/"
        )
    
    with col2:
        make = st.text_input("Make", placeholder="VOLVO")
    
    with col3:
        year = st.number_input("Year", min_value=2024, max_value=2027, value=2025)
    
    model = st.text_input("Model", placeholder="XC60 T8")
    
    # Auto-detection info
    if url:
        method = get_extraction_method(url)
        st.info(f"🤖 Will use: **{method}** based on URL domain")
    
    if st.button("🚀 Extract & Save OEM Messaging", type="primary"):
        if url and make and model:
            extract_and_save_from_url(url, make.upper().strip(), model.strip(), year)
        else:
            st.error("Please fill in all required fields (URL, Make, Model)")

def save_oem_messaging(data):
    """Save OEM messaging to database"""
    try:
        db = get_cached_db()
        
        # Create source record
        source_data = {
            'make': data['make'],
            'document_title': f"Manual Entry - {data['model']} {data['year']}",
            'document_type': 'manual_entry',
            'model_year': data['year'],
            'raw_content': json.dumps(data)
        }
        
        source_result = db.supabase.table('oem_messaging_sources').insert(source_data).execute()
        source_id = source_result.data[0]['id']
        
        # Create model messaging record
        messaging_data = {
            'source_id': source_id,
            'make': data['make'],
            'model': data['model'],
            'year': data['year'],
            'trim_level': data.get('trim'),
            'positioning_statement': data['positioning_statement'],
            'target_audience': data['target_audience'],
            'messaging_data_enhanced': json.dumps({
                'positioning_statement': data['positioning_statement'],
                'target_audience': data['target_audience'],
                'key_features_intended': data['key_features_intended'],
                'brand_attributes_intended': data['brand_attributes_intended'],
                'purchase_drivers_intended': data['purchase_drivers_intended'],
                'competitive_positioning': data['competitive_positioning']
            })
        }
        
        result = db.supabase.table('oem_model_messaging').insert(messaging_data).execute()
        
        st.success(f"✅ Saved OEM messaging for {data['make']} {data['model']} {data['year']}")
        
        # Also save individual features, attributes, etc. to normalized tables
        model_id = result.data[0]['id']
        
        # Save features
        for feature in data['key_features_intended']:
            db.supabase.table('oem_key_features').insert({
                'model_messaging_id': model_id,
                'feature': feature['feature'],
                'feature_category': feature['category'],
                'priority': feature['priority'],
                'messaging_points': feature.get('messaging', ''),
                'target_sentiment': 'positive'
            }).execute()
        
        # Save attributes
        for attr in data['brand_attributes_intended']:
            db.supabase.table('oem_brand_attributes').insert({
                'model_messaging_id': model_id,
                'attribute': attr,
                'importance': 'core'
            }).execute()
        
        # Save drivers
        for driver in data['purchase_drivers_intended']:
            db.supabase.table('oem_purchase_drivers').insert({
                'model_messaging_id': model_id,
                'reason': driver['reason'],
                'priority': driver['priority'],
                'target_audience': driver.get('target_audience', '')
            }).execute()
        
        logger.info(f"✅ Successfully saved complete OEM messaging for {data['make']} {data['model']}")
        
    except Exception as e:
        st.error(f"Error saving: {str(e)}")
        logger.error(f"❌ Error saving OEM messaging: {e}")

# View existing OEM messages
def display_existing_messages():
    """Show existing OEM messages in the database"""
    st.markdown("### 📚 Existing OEM Messages")
    
    db = get_cached_db()
    messages = db.supabase.table('oem_model_messaging').select('*').order('created_at', desc=True).execute()
    
    if messages.data:
        for msg in messages.data[:5]:  # Show last 5
            with st.expander(f"{msg['make']} {msg['model']} {msg['year']}"):
                st.write(f"**Positioning:** {msg.get('positioning_statement', 'N/A')}")
                st.write(f"**Target:** {msg.get('target_audience', 'N/A')}")
                st.write(f"**Created:** {msg['created_at']}")
                
                if st.button(f"🗑️ Delete", key=f"del_{msg['id']}"):
                    db.supabase.table('oem_model_messaging').delete().eq('id', msg['id']).execute()
                    st.rerun()
    else:
        st.info("No OEM messages saved yet")

def get_extraction_method(url: str) -> str:
    """Determine which extraction method to use based on URL"""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    
    # Domains that need enhanced crawler (ScrapFly)
    complex_domains = {
        'media.audiusa.com',
        'www.media.maserati.com',
        'media.vw.com', 
        'www.volvocars.com',
        'media.polestar.com',
        'pressroom.toyota.com',
        'pressroom.lexus.com'
    }
    
    for complex_domain in complex_domains:
        if complex_domain in domain:
            return "Enhanced Crawler (ScrapFly)"
    
    return "Simple HTTP"

def extract_and_save_from_url(url: str, make: str, model: str, year: int):
    """Extract and save OEM messaging from URL"""
    import os
    import json
    import requests
    from bs4 import BeautifulSoup
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Step 1: Extract content
        status_text.text("🌐 Extracting content from URL...")
        progress_bar.progress(20)
        
        method = get_extraction_method(url)
        
        if "Enhanced Crawler" in method:
            content = extract_with_enhanced_crawler(url, make, model, status_text)
        else:
            content = extract_with_simple_http(url, status_text)
        
        if not content:
            st.error("❌ Failed to extract content from URL")
            return
        
        progress_bar.progress(50)
        status_text.text(f"✅ Extracted {len(content):,} characters")
        
        # Step 2: Smart trimming for large content
        if len(content) > 25000:
            content = smart_trim_content(content)
            status_text.text(f"✂️ Trimmed to {len(content):,} characters preserving key sections")
        
        progress_bar.progress(70)
        
        # Step 3: Extract messaging with OpenAI
        status_text.text("🤖 Analyzing content with OpenAI...")
        
        messaging = extract_messaging_with_openai(content, make, model, year)
        
        if not messaging:
            st.error("❌ Failed to extract OEM messaging")
            return
        
        progress_bar.progress(90)
        
        # Step 4: Save to database
        status_text.text("💾 Saving to database...")
        
        model_id = save_extracted_messaging(messaging, make, model, url, year)
        
        if model_id:
            progress_bar.progress(100)
            status_text.text("✅ Complete!")
            
            st.balloons()
            st.success(f"🎉 Successfully processed **{make} {model}**!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Features", len(messaging.get('key_features_intended', [])))
            with col2:
                st.metric("Brand Attributes", len(messaging.get('brand_attributes_intended', [])))
            with col3:
                st.metric("Year", year)
            
            st.info(f"📋 Database ID: {model_id}")
        else:
            st.error("❌ Failed to save to database")
            
    except Exception as e:
        st.error(f"❌ Processing failed: {e}")
        logger.error(f"Error processing {make} {model}: {e}")

def extract_with_enhanced_crawler(url: str, make: str, model: str, status_text) -> str:
    """Extract using enhanced crawler"""
    try:
        from src.utils.enhanced_crawler_manager import EnhancedCrawlerManager
        crawler = EnhancedCrawlerManager()
        
        result = crawler.crawl_url(url, make, model)
        
        if result and result.get('success'):
            return result.get('content', '')
        return None
    except Exception as e:
        status_text.text(f"❌ Enhanced crawler failed: {e}")
        return None

def extract_with_simple_http(url: str, status_text) -> str:
    """Extract using simple HTTP"""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for script in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            script.decompose()
        
        for selector in ['main', 'article', '.content', '#content']:
            elements = soup.select(selector)
            if elements:
                content = elements[0].get_text()
                break
        else:
            content = soup.get_text()
        
        lines = (line.strip() for line in content.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        content = ' '.join(chunk for chunk in chunks if chunk)
        
        return content if len(content) > 500 else None
        
    except Exception as e:
        status_text.text(f"❌ Simple extraction failed: {e}")
        return None

def smart_trim_content(content: str) -> str:
    """Smart trimming that preserves marketing sections"""
    content_lower = content.lower()
    marketing_sections = []
    
    section_markers = [
        ('overview', 'OVERVIEW'),
        ('features', 'FEATURES'), 
        ('interior', 'INTERIOR'),
        ('specifications', 'SPECIFICATIONS'),
        ('performance', 'PERFORMANCE'),
        ('safety', 'SAFETY'),
        ('technology', 'TECHNOLOGY'),
        ('design', 'DESIGN'),
        ('comfort', 'COMFORT'),
        ('utility', 'UTILITY'),
    ]
    
    for marker, name in section_markers:
        if marker in content_lower:
            start_idx = content_lower.find(marker)
            section_content = content[start_idx:start_idx + 3000]
            marketing_sections.append(f"=== {name} ===\n{section_content}")
    
    if marketing_sections:
        return "\n\n".join(marketing_sections[:8])
    else:
        return content[:25000] + "..."

def extract_messaging_with_openai(content: str, make: str, model: str, year: int) -> dict:
    """Extract OEM messaging using OpenAI"""
    import openai
    
    openai.api_key = os.environ.get('OPENAI_API_KEY')
    
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
    "model_detected": "{model}",
    "year": {year},
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
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are an expert at extracting structured OEM messaging from marketing materials."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        response_content = response.choices[0].message.content.strip()
        
        if response_content.startswith('```json'):
            response_content = response_content[7:]
        if response_content.endswith('```'):
            response_content = response_content[:-3]
        
        extracted_data = json.loads(response_content.strip())
        extracted_data['year'] = year  # Ensure correct year
        
        return extracted_data
        
    except Exception as e:
        st.error(f"OpenAI extraction failed: {e}")
        return None

def save_extracted_messaging(extracted_data: dict, make: str, model: str, url: str, year: int) -> str:
    """Save extracted messaging to database"""
    try:
        db = get_cached_db()
        
        # Check if exists
        existing = db.supabase.table('oem_model_messaging')\
            .select('id')\
            .eq('make', make)\
            .eq('model', model)\
            .execute()
        
        if existing.data:
            # Update existing
            model_result = db.supabase.table('oem_model_messaging')\
                .update({
                    'year': year,
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
                })\
                .eq('id', existing.data[0]['id'])\
                .execute()
            
            st.success(f"✅ Updated existing {make} {model}")
            return existing.data[0]['id']
        else:
            # Create new
            source_data = {
                'make': make,
                'document_title': f"{make} {model} Marketing Material", 
                'document_type': 'url',
                'source_url': url,
                'model_year': year
            }
            
            source_result = db.supabase.table('oem_messaging_sources').insert(source_data).execute()
            source_id = source_result.data[0]['id']
            
            messaging_data = {
                'source_id': source_id,
                'make': make,
                'model': model,
                'year': year,
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
            
            model_result = db.supabase.table('oem_model_messaging').insert(messaging_data).execute()
            st.success(f"✅ Created new {make} {model}")
            return model_result.data[0]['id']
            
    except Exception as e:
        st.error(f"Database save failed: {e}")
        return None