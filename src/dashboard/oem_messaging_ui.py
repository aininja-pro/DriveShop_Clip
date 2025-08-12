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
    """URL extraction interface"""
    st.markdown("### 🌐 Extract from URL")
    
    url = st.text_input(
        "Enter URL",
        placeholder="https://www.mazdausa.com/press-release/2024-cx-50"
    )
    
    make = st.text_input("Make (leave blank to auto-detect)", placeholder="e.g., Mazda")
    
    if st.button("🔍 Extract OEM Messaging"):
        if url:
            with st.spinner("Extracting messaging from URL..."):
                # Here we would call the extraction tool
                st.info("URL extraction functionality coming soon...")
                # extractor = OEMExtractorUnified()
                # results = extractor.extract(url, make)
        else:
            st.error("Please enter a URL")

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