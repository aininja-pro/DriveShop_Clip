"""
Strategic Intelligence display - Shows JSON data exactly as stored
Displays all fields with proper formatting
"""
import json
import streamlit as st
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def display_strategic_intelligence_tab(sentiment_clips):
    """
    Display the entire Strategic Intelligence tab showing exact JSON data
    """
    st.markdown("## 🔍 Strategic Intelligence Dashboard")
    st.markdown("---")
    
    if not sentiment_clips:
        st.info("No clips with sentiment analysis found. Run sentiment analysis on approved clips to see detailed insights.")
        return
    
    # Create DataFrame for selection
    import pandas as pd
    
    # Prepare data for display
    display_data = []
    for clip in sentiment_clips:
        display_data.append({
            'WO #': clip.get('wo_number', ''),
            'Make': clip.get('make', ''),
            'Model': clip.get('model', ''),
            'Media Personality': f"{clip.get('contact_first_name', '')} {clip.get('contact_last_name', '')}".strip() or 'Unknown',
            'Affiliation': clip.get('media_outlet', ''),
            'Sentiment': clip.get('overall_sentiment', 'N/A'),
            'Date': clip.get('publish_date', '')
        })
    
    df = pd.DataFrame(display_data)
    
    # Work Order Selection at the top
    st.markdown("### Select a Clip to Analyze")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_wo = st.selectbox(
            "Choose Work Order:",
            options=[''] + df['WO #'].tolist(),
            format_func=lambda x: f"{x} - {df[df['WO #']==x]['Model'].iloc[0]}" if x else "Select a clip...",
            key="strategic_wo_selector"
        )
    
    with col2:
        if st.button("🔄 Refresh Data", key="refresh_strategic"):
            st.rerun()
    
    if not selected_wo:
        st.info("👆 Select a work order above to view detailed sentiment analysis")
        return
    
    # Get the selected clip data
    selected_clip = next((clip for clip in sentiment_clips if clip.get('wo_number') == selected_wo), None)
    if not selected_clip:
        st.error("Could not find selected clip data")
        return
    
    # Display clip header info
    st.markdown("---")
    info_cols = st.columns(4)
    with info_cols[0]:
        st.markdown(f"**👤 Media Contact**  \n{selected_clip.get('contact_first_name', '')} {selected_clip.get('contact_last_name', '')}")
    with info_cols[1]:
        st.markdown(f"**📰 Publication**  \n{selected_clip.get('media_outlet', 'N/A')}")
    with info_cols[2]:
        st.markdown(f"**🚗 Vehicle**  \n{selected_clip.get('make', '')} {selected_clip.get('model', '')}")
    with info_cols[3]:
        st.markdown(f"**📅 Date**  \n{selected_clip.get('publish_date', 'N/A')}")
    
    st.markdown("---")
    
    # Parse enhanced sentiment data
    enhanced_data = {}
    raw_data = selected_clip.get('sentiment_data_enhanced')
    
    if raw_data:
        try:
            if isinstance(raw_data, str):
                enhanced_data = json.loads(raw_data)
            else:
                enhanced_data = raw_data
        except Exception as e:
            st.error(f"Failed to parse sentiment data: {e}")
            return
    
    if not enhanced_data:
        st.warning("No enhanced sentiment data available.")
        return
    
    # Display each section of the JSON data exactly as it appears
    
    # 1. Sentiment Classification
    if 'sentiment_classification' in enhanced_data:
        st.markdown("### 📊 Sentiment Classification")
        sent_class = enhanced_data['sentiment_classification']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            overall = sent_class.get('overall', 'N/A')
            color = {'positive': '🟢', 'neutral': '🟡', 'negative': '🔴'}.get(overall, '🔵')
            st.metric("Overall", f"{color} {overall}")
        
        with col2:
            confidence = sent_class.get('confidence', 'N/A')
            st.metric("Confidence", f"{confidence:.2f}" if isinstance(confidence, (float, int)) else confidence)
        
        with col3:
            st.markdown("**Rationale:**")
            st.info(sent_class.get('rationale', 'No rationale provided'))
    
    # 2. Key Features Mentioned
    if 'key_features_mentioned' in enhanced_data:
        st.markdown("### 🔑 Key Features Mentioned")
        features = enhanced_data['key_features_mentioned']
        
        if features:
            for i, feature in enumerate(features[:10]):  # Limit to top 10
                feature_name = feature.get('feature', 'Unknown')
                sentiment = feature.get('sentiment', 'neutral')
                quote = feature.get('quote', '')
                context = feature.get('context', '')
                
                # Create a container for each feature
                with st.container():
                    # Title bar with feature name and sentiment
                    if sentiment == 'positive':
                        st.success(f"**Feature {i+1}: {feature_name.upper()}** ({sentiment})")
                    elif sentiment == 'negative':
                        st.warning(f"**Feature {i+1}: {feature_name.upper()}** ({sentiment})")
                    else:
                        st.info(f"**Feature {i+1}: {feature_name.upper()}** ({sentiment})")
                    
                    # Quote below if available
                    if quote:
                        st.markdown(f"**Quote:** *\"{quote}\"*")
                    
                    # Context if available
                    if context and context != quote:  # Don't repeat if context is same as quote
                        st.markdown(f"**Context:** {context}")
                    
                    st.markdown("")  # Add spacing
        else:
            st.info("No features found")
    
    # 3. Brand Attributes
    if 'brand_attributes_identified' in enhanced_data:
        st.markdown("### 🏷️ Brand Attributes Identified")
        attributes = enhanced_data['brand_attributes_identified']
        
        if attributes:
            attr_cols = st.columns(min(len(attributes), 3))
            for i, attr in enumerate(attributes):
                with attr_cols[i % 3]:
                    st.info(f"**{attr}**")
        else:
            st.info("No brand attributes identified")
    
    # 4. Purchase Drivers
    if 'purchase_drivers' in enhanced_data:
        st.markdown("### 💰 Purchase Drivers")
        drivers = enhanced_data['purchase_drivers']
        
        if drivers:
            for i, driver in enumerate(drivers):
                reason = driver.get('reason', 'Unknown')
                sentiment = driver.get('sentiment', 'neutral')
                strength = driver.get('strength', 'unknown')
                quote = driver.get('quote', '')
                
                # Create a container for each driver
                with st.container():
                    # Title bar with reason and sentiment
                    if sentiment == 'positive':
                        st.success(f"**Driver {i+1}: {reason.upper()}** ({sentiment})")
                    elif sentiment == 'negative':
                        st.warning(f"**Driver {i+1}: {reason.upper()}** ({sentiment})")
                    else:
                        st.info(f"**Driver {i+1}: {reason.upper()}** ({sentiment})")
                    
                    # Details below
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.markdown(f"**Strength:** {strength}")
                    with col2:
                        if quote:
                            st.markdown(f"**Quote:** *\"{quote}\"*")
                    
                    st.markdown("")  # Add spacing
        else:
            st.info("No purchase drivers identified")
    
    # 5. Competitive Context
    if 'competitive_context' in enhanced_data:
        st.markdown("### 🚗 Competitive Context")
        competitive = enhanced_data['competitive_context']
        
        if isinstance(competitive, dict):
            # Direct Comparisons
            if 'direct_comparisons' in competitive:
                st.markdown("#### Direct Comparisons")
                comparisons = competitive['direct_comparisons']
                for i, comp in enumerate(comparisons):
                    # Parse the comparison to extract competitor name
                    if ':' in comp:
                        competitor, details = comp.split(':', 1)
                        st.info(f"**{competitor.strip().upper()}**")
                        st.markdown(f"*{details.strip()}*")
                    else:
                        st.info(f"**Comparison {i+1}**")
                        st.markdown(f"*{comp}*")
                    st.markdown("")  # Add spacing
            
            # Market Positioning
            if 'market_positioning' in competitive:
                st.markdown("#### Market Positioning")
                st.success(competitive['market_positioning'])
            
            # Any other competitive fields
            for key, value in competitive.items():
                if key not in ['direct_comparisons', 'market_positioning']:
                    st.markdown(f"#### {key.replace('_', ' ').title()}")
                    if isinstance(value, list):
                        for item in value:
                            st.write(f"• {item}")
                    else:
                        st.write(value)
        
        elif isinstance(competitive, str):
            st.info(competitive)
        else:
            st.info("No competitive context found")
    
    # Also check for direct competitors_mentioned field
    elif 'competitors_mentioned' in enhanced_data:
        st.markdown("### 🚗 Competitors Mentioned")
        for comp in enhanced_data['competitors_mentioned']:
            st.write(f"• {comp}")
    
    # Pros and Cons removed per user request - data is covered in other sections
    
    # 7. Summary
    if 'summary' in enhanced_data:
        st.markdown("### 📝 Summary")
        st.info(enhanced_data['summary'])
    
    # 8. Additional scores
    if 'overall_score' in enhanced_data or 'relevance_score' in enhanced_data:
        st.markdown("### 📊 Additional Scores")
        score_cols = st.columns(4)
        
        scores = [
            ('overall_score', 'Overall Score'),
            ('relevance_score', 'Relevance Score'),
            ('marketing_impact_score', 'Marketing Impact'),
            ('brand_alignment', 'Brand Alignment')
        ]
        
        for i, (key, label) in enumerate(scores):
            if key in enhanced_data:
                with score_cols[i]:
                    value = enhanced_data[key]
                    st.metric(label, f"{value}/10" if value else "N/A")
    
    # 9. Recommendation
    if 'recommendation' in enhanced_data:
        st.markdown("### 💼 Recommendation")
        st.warning(enhanced_data['recommendation'])
    
    # 10. Any other fields in the JSON
    st.markdown("### 📋 Additional Data")
    
    # Show any fields we haven't displayed yet
    displayed_fields = {
        'sentiment_classification', 'key_features_mentioned', 'brand_attributes_identified',
        'purchase_drivers', 'competitive_context', 'competitors_mentioned', 'pros', 'cons',
        'summary', 'overall_score', 'relevance_score', 'marketing_impact_score',
        'brand_alignment', 'recommendation'
    }
    
    other_fields = {k: v for k, v in enhanced_data.items() if k not in displayed_fields and v}
    
    if other_fields:
        for field, value in other_fields.items():
            with st.expander(f"📌 {field.replace('_', ' ').title()}", expanded=False):
                if isinstance(value, (dict, list)):
                    st.json(value)
                else:
                    st.write(value)
    
    # Actions and raw data
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📥 Export Analysis", key="export_analysis"):
            st.info("Export functionality coming soon...")
    
    with col2:
        if st.button("🔗 View Clip", key="view_clip_url"):
            url = selected_clip.get('clip_url')
            if url:
                st.markdown(f"[Open clip in new tab]({url})")
    
    with col3:
        with st.expander("🔧 View Complete Raw JSON"):
            st.json(enhanced_data)