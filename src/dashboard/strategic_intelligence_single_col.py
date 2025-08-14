"""
Strategic Intelligence display - Single column layout
Shows complete enhanced sentiment data with proper parsing
"""
import json
import streamlit as st
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def display_strategic_intelligence_tab(sentiment_clips):
    """
    Display the entire Strategic Intelligence tab in single column layout
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
        # Fall back to legacy display
        st.warning("No enhanced sentiment data available. Showing legacy data.")
        if selected_clip.get('summary'):
            st.markdown("### Summary")
            st.write(selected_clip['summary'])
        return
    
    # Executive Summary
    if enhanced_data.get('summary'):
        st.markdown("### 📝 Executive Summary")
        st.info(enhanced_data['summary'])
    
    # Key Features with context
    st.markdown("### 🔑 Key Features Mentioned")
    key_features = enhanced_data.get('key_features_mentioned', []) or enhanced_data.get('key_features', [])
    
    if key_features:
        # Display in a nice format with context
        for i, feature in enumerate(key_features[:10], 1):
            with st.container():
                if isinstance(feature, dict):
                    feature_text = feature.get('feature', '')
                    context = feature.get('context', '')
                    st.markdown(f"**{i}. {feature_text}**")
                    if context:
                        st.caption(f"Context: _{context}_")
                else:
                    st.markdown(f"**{i}. {feature}**")
    else:
        st.info("No specific features were extracted from this review")
    
    # Brand Attributes - Check the actual JSON structure
    st.markdown("### 🏷️ Brand Attributes Identified")
    
    # Debug to see what we actually have
    logger.info(f"Looking for brand attributes in: {list(enhanced_data.keys())}")
    
    # Try to find brand attributes in various possible locations
    brand_attrs = None
    if 'brand_attributes_identified' in enhanced_data:
        brand_attrs = enhanced_data['brand_attributes_identified']
    elif 'brand_attributes' in enhanced_data:
        brand_attrs = enhanced_data['brand_attributes']
    elif 'brand_narrative_elements' in enhanced_data:
        # Sometimes it might be under a different name
        narrative = enhanced_data['brand_narrative_elements']
        if isinstance(narrative, dict) and 'attributes' in narrative:
            brand_attrs = narrative['attributes']
    
    # Display brand attributes
    if brand_attrs:
        # Create a nice grid display
        attr_cols = st.columns(3)
        for idx, attr in enumerate(brand_attrs[:6]):
            with attr_cols[idx % 3]:
                if isinstance(attr, dict):
                    attr_text = attr.get('attribute', attr.get('name', str(attr)))
                    st.info(f"**{attr_text}**")
                else:
                    st.info(f"**{attr}**")
    else:
        st.warning("No brand attributes were identified in this review")
        # Show what fields we do have for debugging
        with st.expander("Debug: Available fields"):
            st.write([k for k in enhanced_data.keys() if 'brand' in k.lower() or 'attribute' in k.lower()])
    
    # Purchase Drivers with full quotes
    st.markdown("### 💰 Purchase Decision Factors")
    purchase_drivers = enhanced_data.get('purchase_drivers', [])
    
    if purchase_drivers:
        for i, driver in enumerate(purchase_drivers[:5], 1):
            with st.container():
                if isinstance(driver, dict):
                    reason = driver.get('reason', 'Unknown')
                    sentiment = driver.get('sentiment', '')
                    quote = driver.get('quote', '')
                    
                    # Color-coded container based on sentiment
                    if sentiment == 'positive':
                        with st.success(f"**Driver #{i}: {reason}**"):
                            if quote:
                                st.write(f"*\"{quote}\"*")
                    elif sentiment == 'negative':
                        with st.warning(f"**Driver #{i}: {reason}**"):
                            if quote:
                                st.write(f"*\"{quote}\"*")
                    else:
                        with st.info(f"**Driver #{i}: {reason}**"):
                            if quote:
                                st.write(f"*\"{quote}\"*")
                else:
                    st.write(f"**{i}.** {driver}")
    else:
        st.info("No specific purchase drivers were identified")
    
    # Competitive Context
    st.markdown("### 🚗 Competitive Analysis")
    
    # Look for competitive data in multiple places
    competitive_found = False
    
    # Direct fields
    if 'competitors_mentioned' in enhanced_data:
        competitive_found = True
        st.markdown("**Competitors Mentioned:**")
        for comp in enhanced_data['competitors_mentioned']:
            st.write(f"• {comp}")
    
    if 'competitive_comparisons' in enhanced_data:
        competitive_found = True
        st.markdown("**Key Comparisons:**")
        for comp in enhanced_data['competitive_comparisons']:
            st.write(f"• {comp}")
    
    # Nested competitive context
    if 'competitive_context' in enhanced_data:
        context = enhanced_data['competitive_context']
        if isinstance(context, dict):
            if 'competitors_mentioned' in context:
                competitive_found = True
                if 'competitors_mentioned' not in enhanced_data:  # Avoid duplication
                    st.markdown("**Competitors Mentioned:**")
                    for comp in context['competitors_mentioned']:
                        st.write(f"• {comp}")
            
            if 'comparison_points' in context:
                competitive_found = True
                st.markdown("**Comparison Points:**")
                for point in context['comparison_points']:
                    st.write(f"• {point}")
        elif isinstance(context, str) and context:
            competitive_found = True
            st.write(context)
    
    if not competitive_found:
        st.info("No competitive comparisons were found in this review")
    
    # Pros and Cons
    st.markdown("### ⚖️ Pros & Cons Analysis")
    pros_col, cons_col = st.columns(2)
    
    with pros_col:
        st.markdown("#### ✅ Strengths")
        pros = enhanced_data.get('pros', [])
        if isinstance(pros, list) and pros:
            for pro in pros:
                st.write(f"• {pro}")
        elif isinstance(pros, str) and pros:
            pros_list = [p.strip() for p in pros.split('|') if p.strip()]
            for pro in pros_list:
                st.write(f"• {pro}")
        else:
            st.write("*No specific strengths noted*")
    
    with cons_col:
        st.markdown("#### ⚠️ Concerns")
        cons = enhanced_data.get('cons', [])
        if isinstance(cons, list) and cons:
            for con in cons:
                st.write(f"• {con}")
        elif isinstance(cons, str) and cons:
            cons_list = [c.strip() for c in cons.split('|') if c.strip()]
            for con in cons_list:
                st.write(f"• {con}")
        else:
            st.write("*No specific concerns noted*")
    
    # Sentiment Scores
    st.markdown("### 📊 Sentiment Metrics")
    metric_cols = st.columns(4)
    
    with metric_cols[0]:
        sentiment = enhanced_data.get('overall_sentiment', enhanced_data.get('overall', 'N/A'))
        if sentiment and sentiment != 'N/A':
            color = {'positive': '🟢', 'neutral': '🟡', 'negative': '🔴'}.get(str(sentiment).lower(), '🔵')
            st.metric("Overall", f"{color} {str(sentiment).title()}")
        else:
            st.metric("Overall", "N/A")
    
    with metric_cols[1]:
        confidence = enhanced_data.get('confidence', 'N/A')
        if confidence != 'N/A':
            st.metric("Confidence", f"{confidence:.2f}" if isinstance(confidence, (int, float)) else confidence)
        else:
            st.metric("Confidence", "N/A")
    
    with metric_cols[2]:
        score = enhanced_data.get('overall_score', enhanced_data.get('score', 'N/A'))
        st.metric("Score", f"{score}/10" if score != 'N/A' else "N/A")
    
    with metric_cols[3]:
        relevance = enhanced_data.get('relevance_score', 'N/A')
        st.metric("Relevance", f"{relevance}/10" if relevance != 'N/A' else "N/A")
    
    # Recommendation
    if enhanced_data.get('recommendation'):
        st.markdown("### 💼 Strategic Recommendation")
        st.warning(enhanced_data['recommendation'])
    
    # Actions
    st.markdown("---")
    action_cols = st.columns(3)
    with action_cols[0]:
        if st.button("📥 Export This Analysis", key="export_single"):
            st.info("Export functionality coming soon...")
    
    with action_cols[1]:
        if st.button("🔗 View Full Clip", key="view_clip"):
            if selected_clip.get('clip_url'):
                st.markdown(f"[Open in new tab]({selected_clip['clip_url']})")
    
    with action_cols[2]:
        with st.expander("🔧 View Raw JSON"):
            st.json(enhanced_data)