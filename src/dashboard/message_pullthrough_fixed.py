"""
Fixed Message Pull-Through Analysis - Clear and meaningful comparisons
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
    st.markdown("See which OEM messages actually appear in media coverage")
    st.markdown("---")
    
    db = DatabaseManager()
    
    # Get OEM messages and reviews
    oem_messages = db.supabase.table('oem_model_messaging').select('*').order('make, model, year').execute()
    
    if not oem_messages.data:
        st.warning("No OEM messaging found. Please add OEM messages first.")
        return
    
    # Create model selector
    col1, col2 = st.columns(2)
    
    with col1:
        # Create unique model list
        model_options = []
        for msg in oem_messages.data:
            option = f"{msg['make']} {msg['model']} ({msg['year']})"
            if option not in model_options:
                model_options.append(option)
        
        selected_model = st.selectbox("Select Vehicle", ["Choose..."] + sorted(model_options))
    
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
        
        # Show OEM positioning first
        st.markdown("### 📢 OEM Intended Messaging")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Positioning Statement:**")
            st.info(oem_messaging.get('positioning_statement', 'Not specified'))
        
        with col2:
            st.markdown("**Target Audience:**")
            st.info(oem_messaging.get('target_audience', 'Not specified'))
        
        # Key features OEM wants to emphasize
        st.markdown("**Key Features OEM Wants Emphasized:**")
        oem_features = oem_messaging.get('key_features_intended', [])
        if oem_features:
            features_df = pd.DataFrame([
                {
                    'Feature': f['feature'],
                    'Category': f.get('category', 'other'),
                    'Priority': f.get('priority', 'secondary')
                }
                for f in oem_features
            ])
            st.dataframe(features_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Analyze each review
        st.markdown("### 📰 Analysis by Review")
        
        for review in reviews.data:
            with st.expander(f"{review['media_outlet']} - {review['wo_number']} ({review['published_date']})"):
                
                try:
                    review_data = json.loads(review['sentiment_data_enhanced'])
                except:
                    st.error("Could not parse review sentiment data")
                    continue
                
                # Show what the review actually said
                if review_data.get('summary'):
                    st.markdown("**Review Summary:**")
                    st.write(review_data['summary'])
                
                # Feature comparison
                st.markdown("#### Feature Pull-Through:")
                
                # Check each OEM feature
                pull_through_results = []
                
                for oem_feature in oem_features:
                    feature_name = oem_feature['feature']
                    found = False
                    found_as = ""
                    
                    # Check if mentioned in review
                    for review_feature in review_data.get('key_features_mentioned', []):
                        if (feature_name.lower() in review_feature['feature'].lower() or 
                            review_feature['feature'].lower() in feature_name.lower()):
                            found = True
                            found_as = review_feature['feature']
                            sentiment = review_feature.get('sentiment', 'neutral')
                            break
                    
                    pull_through_results.append({
                        'OEM Feature': feature_name,
                        'Mentioned?': '✅' if found else '❌',
                        'As': found_as if found else '-',
                        'Sentiment': sentiment if found else '-'
                    })
                
                # Display results
                if pull_through_results:
                    results_df = pd.DataFrame(pull_through_results)
                    st.dataframe(results_df, use_container_width=True, hide_index=True)
                    
                    # Calculate score
                    mentioned_count = sum(1 for r in pull_through_results if r['Mentioned?'] == '✅')
                    total_features = len(pull_through_results)
                    pull_through_rate = (mentioned_count / total_features * 100) if total_features > 0 else 0
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Pull-Through Rate", f"{pull_through_rate:.0f}%")
                    with col2:
                        st.metric("Features Mentioned", f"{mentioned_count} of {total_features}")
                
                # Brand Attributes Analysis
                st.markdown("#### Brand Attributes Pull-Through:")
                
                oem_attributes = oem_messaging.get('brand_attributes_intended', [])
                review_attributes = review_data.get('brand_attributes_identified', [])
                
                if oem_attributes:
                    attr_results = []
                    for oem_attr in oem_attributes:
                        found = any(oem_attr.lower() in ra.lower() or ra.lower() in oem_attr.lower() 
                                   for ra in review_attributes)
                        attr_results.append({
                            'OEM Attribute': oem_attr,
                            'Communicated?': '✅' if found else '❌'
                        })
                    
                    attr_df = pd.DataFrame(attr_results)
                    st.dataframe(attr_df, use_container_width=True, hide_index=True)
                    
                    attrs_found = sum(1 for r in attr_results if r['Communicated?'] == '✅')
                    st.metric("Brand Attribute Pull-Through", f"{attrs_found}/{len(oem_attributes)}")
                
                # Purchase Drivers Analysis
                st.markdown("#### Purchase Drivers Pull-Through:")
                
                oem_drivers = oem_messaging.get('purchase_drivers_intended', [])
                review_drivers = review_data.get('purchase_drivers', [])
                
                if oem_drivers:
                    driver_results = []
                    for oem_driver in oem_drivers:
                        oem_reason = oem_driver['reason'].lower()
                        found = False
                        found_as = ""
                        
                        for review_driver in review_drivers:
                            review_reason = review_driver['reason'].lower()
                            # Check for partial matches
                            if (oem_reason in review_reason or review_reason in oem_reason or
                                (oem_reason == 'price/deal' and 'affordability' in review_reason) or
                                (oem_reason == 'exterior styling' and 'design' in review_reason)):
                                found = True
                                found_as = review_driver['reason']
                                break
                        
                        driver_results.append({
                            'OEM Driver': oem_driver['reason'],
                            'Priority': oem_driver['priority'],
                            'Mentioned?': '✅' if found else '❌',
                            'As': found_as if found else '-'
                        })
                    
                    driver_df = pd.DataFrame(driver_results)
                    st.dataframe(driver_df, use_container_width=True, hide_index=True)
                    
                    drivers_found = sum(1 for r in driver_results if r['Mentioned?'] == '✅')
                    st.metric("Purchase Driver Pull-Through", f"{drivers_found}/{len(oem_drivers)}")
                
                # What else did the review mention?
                review_features = [f['feature'] for f in review_data.get('key_features_mentioned', [])]
                oem_feature_names = [f['feature'].lower() for f in oem_features]
                
                unexpected = []
                for rf in review_features:
                    if not any(oem.lower() in rf.lower() or rf.lower() in oem.lower() for oem in oem_feature_names):
                        unexpected.append(rf)
                
                if unexpected:
                    st.markdown("**Additional Features Mentioned (not in OEM messaging):**")
                    for feature in unexpected:
                        st.write(f"• {feature}")
        
        # Overall summary
        st.markdown("---")
        st.markdown("### 📊 Overall Pull-Through Summary")
        
        # Calculate aggregate metrics for all three categories
        oem_attributes = oem_messaging.get('brand_attributes_intended', [])
        oem_drivers = oem_messaging.get('purchase_drivers_intended', [])
        
        # Track metrics
        total_features_mentions = 0
        total_attr_mentions = 0
        total_driver_mentions = 0
        
        for review in reviews.data:
            try:
                review_data = json.loads(review['sentiment_data_enhanced'])
                
                # Features
                review_features = [f['feature'].lower() for f in review_data.get('key_features_mentioned', [])]
                for oem_feature in oem_features:
                    if any(oem_feature['feature'].lower() in rf or rf in oem_feature['feature'].lower() 
                          for rf in review_features):
                        total_features_mentions += 1
                
                # Attributes
                review_attrs = [a.lower() for a in review_data.get('brand_attributes_identified', [])]
                for oem_attr in oem_attributes:
                    if any(oem_attr.lower() in ra or ra in oem_attr.lower() for ra in review_attrs):
                        total_attr_mentions += 1
                
                # Drivers
                review_drivers = [d['reason'].lower() for d in review_data.get('purchase_drivers', [])]
                for oem_driver in oem_drivers:
                    if any(oem_driver['reason'].lower() in rd or rd in oem_driver['reason'].lower() 
                          for rd in review_drivers):
                        total_driver_mentions += 1
                        
            except:
                continue
        
        # Calculate rates
        features_rate = (total_features_mentions / (len(oem_features) * len(reviews.data)) * 100) if oem_features else 0
        attrs_rate = (total_attr_mentions / (len(oem_attributes) * len(reviews.data)) * 100) if oem_attributes else 0
        drivers_rate = (total_driver_mentions / (len(oem_drivers) * len(reviews.data)) * 100) if oem_drivers else 0
        
        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Features Pull-Through", f"{features_rate:.0f}%", 
                     help=f"{total_features_mentions} mentions across {len(reviews.data)} reviews")
        with col2:
            st.metric("Attributes Pull-Through", f"{attrs_rate:.0f}%",
                     help=f"{total_attr_mentions} mentions across {len(reviews.data)} reviews")
        with col3:
            st.metric("Drivers Pull-Through", f"{drivers_rate:.0f}%",
                     help=f"{total_driver_mentions} mentions across {len(reviews.data)} reviews")
        with col4:
            overall_rate = (features_rate + attrs_rate + drivers_rate) / 3
            st.metric("Overall Average", f"{overall_rate:.0f}%")