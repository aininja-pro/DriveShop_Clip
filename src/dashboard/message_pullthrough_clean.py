"""
Clean Message Pull-Through Analysis - Side-by-side comparison view
"""
import streamlit as st
import pandas as pd
import json
from src.utils.database import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def display_pullthrough_analysis_tab():
    """Display the Message Pull-Through Analysis interface"""
    st.markdown("## 📊 Message Pull-Through Analysis")
    st.markdown("Compare OEM intended messages vs. actual media coverage")
    st.markdown("---")
    
    db = DatabaseManager()
    
    # Initialize session state
    if 'pullthrough_analysis_active' not in st.session_state:
        st.session_state.pullthrough_analysis_active = False
    if 'selected_vehicle' not in st.session_state:
        st.session_state.selected_vehicle = None
    
    # Get OEM messages
    oem_messages = db.supabase.table('oem_model_messaging').select('*').order('make, model, year').execute()
    
    if not oem_messages.data:
        st.warning("No OEM messaging found. Please add OEM messages first.")
        return
    
    # Vehicle selector
    col1, col2 = st.columns(2)
    
    with col1:
        # Create unique model list
        model_options = []
        for msg in oem_messages.data:
            option = f"{msg['make']} {msg['model']} ({msg['year']})"
            if option not in model_options:
                model_options.append(option)
        
        selected_model = st.selectbox("Select Vehicle", ["Choose..."] + sorted(model_options), key="vehicle_selector")
    
    with col2:
        if selected_model != "Choose...":
            # Parse selection
            parts = selected_model.split(' (')
            year = int(parts[1].rstrip(')'))
            make_model = parts[0].split(' ', 1)
            make = make_model[0]
            model = make_model[1]
            
            # Get matching reviews
            reviews = db.supabase.table('clips').select('wo_number, media_outlet, published_date').eq('make', make).like('model', f"{model}%").eq('sentiment_completed', True).execute()
            
            st.metric("Reviews with Sentiment", len(reviews.data))
    
    if selected_model != "Choose..." and st.button("🔍 Analyze Pull-Through", type="primary"):
        st.session_state.pullthrough_analysis_active = True
        st.session_state.selected_vehicle = (make, model, year)
    
    # Show analysis if active
    if st.session_state.pullthrough_analysis_active and st.session_state.selected_vehicle:
        make, model, year = st.session_state.selected_vehicle
        analyze_model_pullthrough(make, model, year, db)

def analyze_model_pullthrough(make, model, year, db):
    """Analyze pull-through for a specific model"""
    
    with st.spinner("Analyzing message pull-through..."):
        
        # Get OEM messaging
        oem_data = db.supabase.table('oem_model_messaging').select('*').eq('make', make).eq('model', model).eq('year', year).single().execute()
        
        if not oem_data.data:
            st.error("OEM messaging not found")
            return
        
        # Get reviews
        reviews = db.supabase.table('clips').select('*').eq('make', make).like('model', f"{model}%").eq('sentiment_completed', True).execute()
        
        if not reviews.data:
            st.warning(f"No reviews found for {make} {model}")
            return
        
        # Parse OEM messaging
        try:
            oem_messaging = json.loads(oem_data.data['messaging_data_enhanced'])
        except:
            st.error("Error parsing OEM messaging data")
            return
        
        st.success(f"Found {len(reviews.data)} review(s) to analyze")
        
        # Show OEM messaging overview
        st.markdown("### 📢 OEM Intended Messaging")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Positioning:**")
            st.info(oem_messaging.get('positioning_statement', 'Not specified')[:200] + "...")
        
        with col2:
            st.markdown("**Target Audience:**")
            st.info(oem_messaging.get('target_audience', 'Not specified'))
        
        # Quick summary of what OEM wants
        st.markdown("**Key Messages:**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Key Features", len(oem_messaging.get('key_features_intended', [])))
        with col2:
            st.metric("Brand Attributes", len(oem_messaging.get('brand_attributes_intended', [])))
        with col3:
            st.metric("Purchase Drivers", len(oem_messaging.get('purchase_drivers_intended', [])))
        
        st.markdown("---")
        
        # Review selector - compact dropdown
        st.markdown("### 📰 Select Review to Analyze")
        
        # Filter reviews to only those with valid enhanced sentiment data
        valid_reviews = []
        for r in reviews.data:
            if r.get('sentiment_data_enhanced'):
                try:
                    data = json.loads(r['sentiment_data_enhanced'])
                    if 'key_features_mentioned' in data:  # Check for new format
                        valid_reviews.append(r)
                except:
                    continue
        
        if not valid_reviews:
            st.error("No reviews found with enhanced sentiment analysis. Please run sentiment analysis on some reviews first.")
            return
        
        # Show count difference if applicable
        if len(valid_reviews) < len(reviews.data):
            st.info(f"📌 {len(valid_reviews)} of {len(reviews.data)} reviews have enhanced sentiment data. Others need re-processing.")
        
        # Create review options
        review_options = [
            f"{r['media_outlet']} - {r['wo_number']} ({r['published_date']})"
            for r in valid_reviews
        ]
        
        selected_review_idx = st.selectbox(
            "Choose a review:",
            range(len(review_options)),
            format_func=lambda x: review_options[x],
            key="review_selector"
        )
        
        if selected_review_idx is not None:
            selected_review = valid_reviews[selected_review_idx]
            
            try:
                review_data = json.loads(selected_review['sentiment_data_enhanced'])
            except:
                st.error("Could not parse review sentiment data")
                return
            
            # Show review info with link
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**Review:** {selected_review['media_outlet']} | **Date:** {selected_review['published_date']}")
            
            with col2:
                st.markdown(f"**WO #:** {selected_review['wo_number']}")
            
            with col3:
                if selected_review.get('clip_url'):
                    st.markdown(f"[🔗 View Review]({selected_review['clip_url']})")
                else:
                    st.info("No URL")
            
            # Review summary if available
            if review_data.get('summary'):
                with st.expander("📝 Review Summary", expanded=False):
                    st.write(review_data['summary'])
            
            # SIDE-BY-SIDE COMPARISON
            st.markdown("---")
            st.markdown("### 🔍 Side-by-Side Comparison")
            
            # Create tabs for each analysis type
            tab1, tab2, tab3, tab4 = st.tabs(["🔑 Key Features", "🏷️ Brand Attributes", "💰 Purchase Drivers", "📋 Full Sentiment Analysis"])
            
            with tab1:
                display_features_comparison(oem_messaging, review_data)
            
            with tab2:
                display_attributes_comparison(oem_messaging, review_data)
            
            with tab3:
                display_drivers_comparison(oem_messaging, review_data)
            
            with tab4:
                display_full_sentiment_analysis(review_data)
            
            # Overall metrics for this review
            st.markdown("---")
            st.markdown("### 📊 Pull-Through Metrics for This Review")
            
            metrics = calculate_review_metrics(oem_messaging, review_data)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Features", f"{metrics['features_rate']:.0f}%", 
                         delta=f"{metrics['features_found']}/{metrics['features_total']}")
            with col2:
                st.metric("Attributes", f"{metrics['attrs_rate']:.0f}%",
                         delta=f"{metrics['attrs_found']}/{metrics['attrs_total']}")
            with col3:
                st.metric("Drivers", f"{metrics['drivers_rate']:.0f}%",
                         delta=f"{metrics['drivers_found']}/{metrics['drivers_total']}")
            with col4:
                overall = (metrics['features_rate'] + metrics['attrs_rate'] + metrics['drivers_rate']) / 3
                st.metric("Overall", f"{overall:.0f}%",
                         delta="Good" if overall >= 50 else "Poor")

def display_features_comparison(oem_messaging, review_data):
    """Display side-by-side features comparison"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📢 OEM Wants")
        oem_features = oem_messaging.get('key_features_intended', [])
        
        for i, feature in enumerate(oem_features, 1):
            priority_emoji = "🔴" if feature.get('priority') == 'primary' else "🟡"
            st.write(f"{priority_emoji} **{i}. {feature['feature']}**")
            if feature.get('messaging'):
                st.caption(f"_{feature['messaging'][:80]}..._")
    
    with col2:
        st.markdown("#### 📰 Review Mentioned")
        review_features = review_data.get('key_features_mentioned', [])
        oem_feature_names = [f['feature'].lower() for f in oem_features]
        
        # Check which OEM features were mentioned
        matched_features = []
        unmatched_features = []
        
        # Create a mapping of semantic matches for better matching
        semantic_matches = {
            'cargo': ['cargo space', 'cargo area', 'trunk space', 'storage space', 'luggage'],
            'all-wheel': ['awd', 'all wheel drive', 'all-wheel drive', '4wd', 'four wheel'],
            'turbo': ['turbo engine', 'turbocharged', 'turbocharger', 't engine'],
            'moonroof': ['sunroof', 'panoramic roof', 'glass roof', 'moon roof'],
            'towing': ['tow capacity', 'towing capability', 'haul', 'trailer'],
            'drive mode': ['driving mode', 'mi-drive', 'sport mode', 'drive select'],
            'hybrid': ['hybrid powertrain', 'hybrid system', 'electric motor', 'phev'],
            'roof rail': ['roof rack', 'cargo rail', 'luggage rail']
        }
        
        for rf in review_features:
            matched = False
            review_feature_lower = rf['feature'].lower()
            
            # Check each OEM feature
            for oem_f in oem_feature_names:
                # Direct match (one contains the other)
                if oem_f in review_feature_lower or review_feature_lower in oem_f:
                    matched = True
                    matched_features.append(rf)
                    break
                
                # Semantic match - check if they're talking about the same thing
                matched_semantically = False
                
                # Check each semantic group
                for key, variants in semantic_matches.items():
                    oem_matches_group = any(term in oem_f for term in [key] + variants)
                    review_matches_group = any(term in review_feature_lower for term in [key] + variants)
                    
                    if oem_matches_group and review_matches_group:
                        matched_semantically = True
                        break
                
                if matched_semantically:
                    matched = True
                    matched_features.append(rf)
                    break
            
            if not matched:
                unmatched_features.append(rf)
        
        # Show matched features first
        if matched_features:
            st.success("✅ **Mentioned OEM Features:**")
            for feature in matched_features[:5]:
                sentiment_emoji = {"positive": "😊", "negative": "😟", "neutral": "😐"}.get(feature.get('sentiment', 'neutral'))
                st.write(f"{sentiment_emoji} {feature['feature']}")
                if feature.get('quote'):
                    st.caption(f'_"{feature["quote"][:100]}..."_')
        
        # Show additional features
        if unmatched_features:
            st.info("➕ **Additional Features Mentioned:**")
            for feature in unmatched_features[:3]:
                st.write(f"• {feature['feature']}")
        
        # Show what's missing
        missing = []
        for oem_f in oem_features:
            oem_feature_lower = oem_f['feature'].lower()
            found = False
            
            # Check direct matches
            for rf in review_features:
                review_feature_lower = rf['feature'].lower()
                
                # Direct match
                if oem_feature_lower in review_feature_lower or review_feature_lower in oem_feature_lower:
                    found = True
                    break
                
                # Semantic match
                for key, variants in semantic_matches.items():
                    oem_matches_group = any(term in oem_feature_lower for term in [key] + variants)
                    review_matches_group = any(term in review_feature_lower for term in [key] + variants)
                    
                    if oem_matches_group and review_matches_group:
                        found = True
                        break
                
                if found:
                    break
            
            if not found:
                missing.append(oem_f['feature'])
        
        if missing:
            st.error("❌ **Not Mentioned:**")
            for feature in missing[:5]:
                st.write(f"• {feature}")

def display_attributes_comparison(oem_messaging, review_data):
    """Display side-by-side brand attributes comparison"""
    
    col1, col2 = st.columns(2)
    
    oem_attrs = oem_messaging.get('brand_attributes_intended', [])
    review_attrs = review_data.get('brand_attributes_identified', [])
    
    with col1:
        st.markdown("#### 📢 OEM Brand Values")
        if oem_attrs:
            for attr in oem_attrs:
                st.write(f"🎯 **{attr}**")
        else:
            st.info("No brand attributes specified")
    
    with col2:
        st.markdown("#### 📰 Review Identified")
        if review_attrs:
            # Check which matched
            matched = []
            unmatched = []
            
            for ra in review_attrs:
                if any(oa.lower() in ra.lower() or ra.lower() in oa.lower() for oa in oem_attrs):
                    matched.append(ra)
                else:
                    unmatched.append(ra)
            
            if matched:
                st.success("✅ **Communicated:**")
                for attr in matched:
                    st.write(f"• {attr}")
            
            if unmatched:
                st.info("➕ **Additional Attributes:**")
                for attr in unmatched:
                    st.write(f"• {attr}")
        else:
            st.error("❌ No brand attributes identified in review")
        
        # Show what's missing
        if oem_attrs and review_attrs:
            missing = [oa for oa in oem_attrs if not any(oa.lower() in ra.lower() or ra.lower() in oa.lower() for ra in review_attrs)]
            if missing:
                st.error("❌ **Not Communicated:**")
                for attr in missing:
                    st.write(f"• {attr}")

def display_drivers_comparison(oem_messaging, review_data):
    """Display side-by-side purchase drivers comparison"""
    
    col1, col2 = st.columns(2)
    
    oem_drivers = oem_messaging.get('purchase_drivers_intended', [])
    review_drivers = review_data.get('purchase_drivers', [])
    
    with col1:
        st.markdown("#### 📢 OEM Purchase Drivers")
        if oem_drivers:
            for driver in sorted(oem_drivers, key=lambda x: x.get('priority', 999)):
                st.write(f"**{driver['priority']}. {driver['reason'].title()}**")
                if driver.get('target_audience'):
                    st.caption(f"_Target: {driver['target_audience']}_")
        else:
            st.info("No purchase drivers specified")
    
    with col2:
        st.markdown("#### 📰 Review Mentioned")
        if review_drivers:
            # Check matches
            for rd in review_drivers:
                sentiment_emoji = {"positive": "😊", "negative": "😟", "neutral": "😐"}.get(rd.get('sentiment', 'neutral'))
                
                # Check if it matches OEM driver
                matched = False
                for od in oem_drivers:
                    if (od['reason'].lower() in rd['reason'].lower() or 
                        rd['reason'].lower() in od['reason'].lower() or
                        (od['reason'] == 'price/deal' and 'affordability' in rd['reason'].lower()) or
                        (od['reason'] == 'exterior styling' and 'design' in rd['reason'].lower())):
                        matched = True
                        break
                
                if matched:
                    st.success(f"✅ {sentiment_emoji} **{rd['reason'].title()}**")
                else:
                    st.info(f"➕ {sentiment_emoji} **{rd['reason'].title()}**")
                
                if rd.get('quote'):
                    st.caption(f'_"{rd["quote"][:100]}..."_')
        else:
            st.error("❌ No purchase drivers mentioned in review")
        
        # Show what's missing
        if oem_drivers and review_drivers:
            review_reasons = [rd['reason'].lower() for rd in review_drivers]
            missing = []
            
            for od in oem_drivers:
                found = False
                for rr in review_reasons:
                    if (od['reason'].lower() in rr or rr in od['reason'].lower() or
                        (od['reason'] == 'price/deal' and 'affordability' in rr) or
                        (od['reason'] == 'exterior styling' and 'design' in rr)):
                        found = True
                        break
                if not found:
                    missing.append(od['reason'])
            
            if missing:
                st.error("❌ **Not Mentioned:**")
                for driver in missing:
                    st.write(f"• {driver.title()}")

def display_full_sentiment_analysis(review_data):
    """Display the complete enhanced sentiment analysis data"""
    
    st.markdown("#### 📊 Complete Enhanced Sentiment Analysis")
    st.caption("All data extracted by our AI from this review")
    
    # 1. Sentiment Classification
    if 'sentiment_classification' in review_data:
        st.markdown("##### 🎯 Sentiment Classification")
        sent = review_data['sentiment_classification']
        
        col1, col2 = st.columns([1, 3])
        with col1:
            overall = sent.get('overall', 'N/A')
            emoji = {'positive': '😊', 'neutral': '😐', 'negative': '😟'}.get(overall, '🔵')
            st.metric("Overall", f"{emoji} {overall.title()}")
            st.metric("Confidence", f"{sent.get('confidence', 0):.0%}")
        
        with col2:
            st.info(f"**Rationale:** {sent.get('rationale', 'N/A')}")
    
    # 2. Key Features with full details
    if 'key_features_mentioned' in review_data:
        st.markdown("##### 🔑 All Key Features Mentioned")
        
        for i, feature in enumerate(review_data['key_features_mentioned'], 1):
            with st.expander(f"{i}. {feature['feature'].upper()} ({feature.get('sentiment', 'neutral')})", expanded=(i <= 3)):
                if feature.get('quote'):
                    st.markdown(f"**Quote:** _{feature['quote']}_")
                if feature.get('context') and feature.get('context') != feature.get('quote'):
                    st.markdown(f"**Context:** {feature['context']}")
                sentiment_emoji = {'positive': '😊', 'neutral': '😐', 'negative': '😟'}.get(feature.get('sentiment', 'neutral'))
                st.markdown(f"**Sentiment:** {sentiment_emoji} {feature.get('sentiment', 'neutral')}")
    
    # 3. Brand Attributes (if using newer format)
    if 'brand_attributes_captured' in review_data:
        st.markdown("##### 🏷️ Brand Attributes Captured")
        for attr in review_data['brand_attributes_captured']:
            with st.container():
                st.markdown(f"**{attr['attribute'].title()}** - {attr.get('sentiment', 'N/A')}")
                if attr.get('evidence'):
                    st.caption(f"Evidence: _{attr['evidence']}_")
    elif 'brand_attributes_identified' in review_data:
        st.markdown("##### 🏷️ Brand Attributes Identified")
        attrs = review_data['brand_attributes_identified']
        if attrs:
            cols = st.columns(3)
            for i, attr in enumerate(attrs):
                with cols[i % 3]:
                    st.info(attr)
    
    # 4. Purchase Drivers with full context
    if 'purchase_drivers' in review_data:
        st.markdown("##### 💰 Purchase Drivers")
        
        for driver in review_data['purchase_drivers']:
            with st.container():
                col1, col2 = st.columns([1, 3])
                with col1:
                    sentiment_emoji = {'positive': '😊', 'neutral': '😐', 'negative': '😟'}.get(driver.get('sentiment', 'neutral'))
                    st.markdown(f"**{driver['reason'].title()}**")
                    st.caption(f"{sentiment_emoji} {driver.get('strength', 'N/A')} driver")
                with col2:
                    if driver.get('quote'):
                        st.info(f"_{driver['quote']}_")
    
    # 5. Competitive Context
    if 'competitive_context' in review_data:
        st.markdown("##### 🚗 Competitive Context")
        comp = review_data['competitive_context']
        
        if isinstance(comp, dict):
            if 'direct_comparisons' in comp:
                st.markdown("**Direct Comparisons:**")
                for comparison in comp['direct_comparisons']:
                    st.write(f"• {comparison}")
            
            if 'market_positioning' in comp:
                st.markdown("**Market Positioning:**")
                st.info(comp['market_positioning'])
        else:
            st.write(comp)
    
    # 6. Additional Metadata
    st.markdown("##### 📊 Analysis Metadata")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Relevance Score", review_data.get('relevance_score', 'N/A'))
    
    with col2:
        st.metric("Content Type", review_data.get('content_type', 'N/A'))
    
    with col3:
        brand_aligned = "✅ Yes" if review_data.get('brand_alignment') else "❌ No"
        st.metric("Brand Aligned", brand_aligned)
    
    with col4:
        if 'sentiment_analysis_date' in review_data:
            date = review_data['sentiment_analysis_date'].split('T')[0]
            st.metric("Analysis Date", date)
    
    # 7. Summary
    if 'summary' in review_data:
        st.markdown("##### 📝 AI Summary")
        st.success(review_data['summary'])
    
    # 8. Raw JSON view
    with st.expander("🔧 View Raw JSON Data", expanded=False):
        st.json(review_data)

def calculate_review_metrics(oem_messaging, review_data):
    """Calculate pull-through metrics for a single review"""
    
    metrics = {
        'features_total': len(oem_messaging.get('key_features_intended', [])),
        'features_found': 0,
        'features_rate': 0,
        'attrs_total': len(oem_messaging.get('brand_attributes_intended', [])),
        'attrs_found': 0,
        'attrs_rate': 0,
        'drivers_total': len(oem_messaging.get('purchase_drivers_intended', [])),
        'drivers_found': 0,
        'drivers_rate': 0
    }
    
    # Count features with semantic matching
    oem_features = oem_messaging.get('key_features_intended', [])
    review_features = [f['feature'].lower() for f in review_data.get('key_features_mentioned', [])]
    
    # Same semantic matches as in display
    semantic_matches = {
        'cargo': ['cargo space', 'cargo area', 'trunk space', 'storage space', 'luggage'],
        'all-wheel': ['awd', 'all wheel drive', 'all-wheel drive', '4wd', 'four wheel'],
        'turbo': ['turbo engine', 'turbocharged', 'turbocharger', 't engine'],
        'moonroof': ['sunroof', 'panoramic roof', 'glass roof', 'moon roof'],
        'towing': ['tow capacity', 'towing capability', 'haul', 'trailer'],
        'drive mode': ['driving mode', 'mi-drive', 'sport mode', 'drive select'],
        'hybrid': ['hybrid powertrain', 'hybrid system', 'electric motor', 'phev'],
        'roof rail': ['roof rack', 'cargo rail', 'luggage rail']
    }
    
    for oem_f in oem_features:
        oem_feature_lower = oem_f['feature'].lower()
        found = False
        
        for rf in review_features:
            # Direct match
            if oem_feature_lower in rf or rf in oem_feature_lower:
                found = True
                break
            
            # Semantic match
            for key, variants in semantic_matches.items():
                oem_matches = any(term in oem_feature_lower for term in [key] + variants)
                review_matches = any(term in rf for term in [key] + variants)
                
                if oem_matches and review_matches:
                    found = True
                    break
            
            if found:
                break
        
        if found:
            metrics['features_found'] += 1
    
    if metrics['features_total'] > 0:
        metrics['features_rate'] = (metrics['features_found'] / metrics['features_total']) * 100
    
    # Count attributes
    oem_attrs = [a.lower() for a in oem_messaging.get('brand_attributes_intended', [])]
    review_attrs = [a.lower() for a in review_data.get('brand_attributes_identified', [])]
    
    for oa in oem_attrs:
        if any(oa in ra or ra in oa for ra in review_attrs):
            metrics['attrs_found'] += 1
    
    if metrics['attrs_total'] > 0:
        metrics['attrs_rate'] = (metrics['attrs_found'] / metrics['attrs_total']) * 100
    
    # Count drivers
    oem_drivers = oem_messaging.get('purchase_drivers_intended', [])
    review_drivers = review_data.get('purchase_drivers', [])
    
    for od in oem_drivers:
        for rd in review_drivers:
            if (od['reason'].lower() in rd['reason'].lower() or 
                rd['reason'].lower() in od['reason'].lower() or
                (od['reason'] == 'price/deal' and 'affordability' in rd['reason'].lower()) or
                (od['reason'] == 'exterior styling' and 'design' in rd['reason'].lower())):
                metrics['drivers_found'] += 1
                break
    
    if metrics['drivers_total'] > 0:
        metrics['drivers_rate'] = (metrics['drivers_found'] / metrics['drivers_total']) * 100
    
    return metrics