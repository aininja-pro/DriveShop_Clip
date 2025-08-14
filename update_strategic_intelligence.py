#!/usr/bin/env python3
"""
Script to update Strategic Intelligence tab to use enhanced sentiment data
Shows how to parse and display the new JSON structure
"""

import json
import streamlit as st

def display_enhanced_sentiment(clip_data):
    """
    Display enhanced sentiment data in a clean, organized layout
    
    Args:
        clip_data: Row from database with sentiment_data_enhanced field
    """
    
    # Parse the enhanced sentiment data
    enhanced_data = {}
    if clip_data.get('sentiment_data_enhanced'):
        try:
            if isinstance(clip_data['sentiment_data_enhanced'], str):
                enhanced_data = json.loads(clip_data['sentiment_data_enhanced'])
            else:
                enhanced_data = clip_data['sentiment_data_enhanced']
        except:
            st.warning("Could not parse enhanced sentiment data")
            return
    
    if not enhanced_data:
        st.info("No enhanced sentiment analysis available for this clip")
        return
    
    # Core Sentiment Overview
    st.markdown("### 📊 Sentiment Overview")
    col1, col2, col3 = st.columns(3)
    with col1:
        sentiment = enhanced_data.get('overall_sentiment', 'neutral')
        sentiment_color = {
            'positive': '#28a745',
            'neutral': '#6c757d', 
            'negative': '#dc3545'
        }.get(sentiment, '#6c757d')
        st.markdown(f"**Overall Sentiment:** <span style='color: {sentiment_color}; font-weight: bold;'>{sentiment.title()}</span>", unsafe_allow_html=True)
    with col2:
        score = enhanced_data.get('overall_score', 0)
        st.metric("Sentiment Score", f"{score}/10")
    with col3:
        brand_score = enhanced_data.get('brand_alignment', 0)
        st.metric("Brand Alignment", f"{brand_score}/10")
    
    # Executive Summary
    if enhanced_data.get('summary'):
        st.markdown("### 📝 Executive Summary")
        st.markdown(enhanced_data['summary'])
    
    # Key Features & Attributes (NEW ENHANCED DATA)
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔑 Key Features Mentioned")
        key_features = enhanced_data.get('key_features', [])
        if key_features:
            for i, feature in enumerate(key_features[:10], 1):
                st.markdown(f"**{i}.** {feature}")
        else:
            st.markdown("*No specific features extracted*")
    
    with col2:
        st.markdown("### 🏷️ Brand Attributes")
        brand_attributes = enhanced_data.get('brand_attributes', [])
        if brand_attributes:
            for attr in brand_attributes[:5]:
                st.markdown(f"• **{attr}**")
        else:
            st.markdown("*No brand attributes identified*")
    
    # Purchase Drivers & Competitive Context
    st.markdown("### 🎯 Purchase Decision Factors")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Top Purchase Drivers:**")
        purchase_drivers = enhanced_data.get('purchase_drivers', [])
        if purchase_drivers:
            for driver in purchase_drivers[:3]:
                st.markdown(f"✅ {driver}")
        else:
            st.markdown("*No purchase drivers identified*")
    
    with col2:
        st.markdown("**Competitive Context:**")
        competitive = enhanced_data.get('competitive_context', {})
        if competitive:
            if competitive.get('competitors_mentioned'):
                st.markdown(f"🚗 Mentioned: {', '.join(competitive['competitors_mentioned'])}")
            if competitive.get('comparison_points'):
                for point in competitive['comparison_points'][:2]:
                    st.markdown(f"• {point}")
        else:
            st.markdown("*No competitive analysis*")
    
    # Pros and Cons in expandable section
    with st.expander("💡 Detailed Pros & Cons", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Pros:**")
            pros = enhanced_data.get('pros', [])
            if isinstance(pros, list):
                for pro in pros:
                    st.markdown(f"• {pro}")
            else:
                st.markdown(pros)
        
        with col2:
            st.markdown("**Cons:**")
            cons = enhanced_data.get('cons', [])
            if isinstance(cons, list):
                for con in cons:
                    st.markdown(f"• {con}")
            else:
                st.markdown(cons)
    
    # Strategic Insights (if available)
    if any(enhanced_data.get(field) for field in ['brand_narrative', 'strategic_signal', 'messaging_opportunities']):
        with st.expander("🎭 Strategic Intelligence", expanded=False):
            if enhanced_data.get('brand_narrative'):
                st.markdown("**Brand Narrative Impact:**")
                st.markdown(enhanced_data['brand_narrative'])
            
            if enhanced_data.get('strategic_signal'):
                st.markdown("**Strategic Signal:**")
                st.markdown(f"⚡ {enhanced_data['strategic_signal']}")
            
            if enhanced_data.get('messaging_opportunities'):
                st.markdown("**Messaging Opportunities:**")
                for opp in enhanced_data['messaging_opportunities']:
                    st.markdown(f"• {opp}")
    
    # Marketing Impact
    if enhanced_data.get('recommendation'):
        st.markdown("### 💼 Recommendation")
        st.info(enhanced_data['recommendation'])
    
    # Raw data viewer (for debugging/transparency)
    with st.expander("🔧 View Raw Data", expanded=False):
        st.json(enhanced_data)


# Example of how to integrate into the existing dashboard:
def update_strategic_intelligence_tab():
    """
    Replace the existing sentiment display with enhanced version
    This would go in the Strategic Intelligence tab section
    """
    
    # Your existing code to get selected clip...
    selected_wo = st.session_state.get('selected_work_order', None)
    
    if selected_wo and sentiment_clips and not df.empty:
        selected_row = df[df['WO #'] == selected_wo].iloc[0]
        
        # Display basic info (existing code)
        st.markdown(f"#### {selected_row.get('Model', 'Unknown Model')} - WO #{selected_wo}")
        
        # NEW: Display enhanced sentiment instead of old fields
        display_enhanced_sentiment(selected_row)