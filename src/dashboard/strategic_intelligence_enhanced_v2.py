"""
Enhanced Strategic Intelligence display using full width layout
Shows complete context and quotes from sentiment analysis
"""
import json
import streamlit as st
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def display_enhanced_sentiment_data(selected_row):
    """
    Display enhanced sentiment data from sentiment_data_enhanced field
    Uses full page width for better readability
    """
    
    # Parse the enhanced sentiment data
    enhanced_data = {}
    raw_data = selected_row.get('sentiment_data_enhanced')
    
    if raw_data:
        try:
            if isinstance(raw_data, str):
                enhanced_data = json.loads(raw_data)
            else:
                enhanced_data = raw_data
            logger.info(f"Successfully parsed enhanced sentiment data for WO# {selected_row.get('WO #', 'Unknown')}")
        except Exception as e:
            logger.error(f"Failed to parse enhanced sentiment data: {e}")
            return False
    
    if not enhanced_data:
        return False
    
    # Executive Summary at the top
    if enhanced_data.get('summary'):
        st.markdown("### 📝 Executive Summary")
        st.info(enhanced_data['summary'])
        st.markdown("---")
    
    # Key Features Section - Full width
    st.markdown("### 🔑 Key Features Mentioned")
    key_features = enhanced_data.get('key_features_mentioned', []) or enhanced_data.get('key_features', [])
    if key_features:
        for i, feature in enumerate(key_features[:10], 1):
            if isinstance(feature, dict):
                feature_text = feature.get('feature', '')
                context = feature.get('context', '')
                if context:
                    st.markdown(f"**{i}. {feature_text}**")
                    st.markdown(f"   _{context}_")
                else:
                    st.markdown(f"**{i}.** {feature_text}")
            else:
                st.markdown(f"**{i}.** {feature}")
    else:
        st.info("No specific features extracted")
    
    st.markdown("---")
    
    # Brand Attributes Section
    st.markdown("### 🏷️ Brand Attributes Identified")
    # Check all possible field names
    brand_attributes = (enhanced_data.get('brand_attributes_identified') or 
                       enhanced_data.get('brand_attributes') or 
                       enhanced_data.get('brand_attributes_mentioned') or [])
    
    if brand_attributes:
        # Create columns for brand attributes
        cols = st.columns(min(len(brand_attributes), 3))
        for idx, attr in enumerate(brand_attributes[:6]):
            with cols[idx % 3]:
                if isinstance(attr, dict):
                    attr_text = attr.get('attribute', str(attr))
                    st.markdown(f"**{attr_text}**")
                else:
                    st.markdown(f"**{attr}**")
    else:
        st.info("No brand attributes identified")
    
    st.markdown("---")
    
    # Purchase Drivers Section with full quotes
    st.markdown("### 💰 Purchase Decision Factors")
    purchase_drivers = enhanced_data.get('purchase_drivers', [])
    if purchase_drivers:
        for i, driver in enumerate(purchase_drivers[:5], 1):
            if isinstance(driver, dict):
                reason = driver.get('reason', 'Unknown')
                sentiment = driver.get('sentiment', '')
                quote = driver.get('quote', '')
                
                # Color code by sentiment
                if sentiment == 'positive':
                    st.success(f"**{i}. {reason}**")
                elif sentiment == 'negative':
                    st.warning(f"**{i}. {reason}**")
                else:
                    st.info(f"**{i}. {reason}**")
                
                if quote:
                    st.markdown(f"> *\"{quote}\"*")
                st.markdown("")  # Add spacing
            else:
                st.markdown(f"**{i}.** {driver}")
    else:
        st.info("No purchase drivers identified")
    
    st.markdown("---")
    
    # Competitive Analysis Section
    st.markdown("### 🚗 Competitive Context")
    
    # Check multiple possible locations for competitive data
    competitors = enhanced_data.get('competitors_mentioned', [])
    comparisons = enhanced_data.get('competitive_comparisons', [])
    competitive_context = enhanced_data.get('competitive_context', {})
    
    has_competitive_data = False
    
    if competitors:
        has_competitive_data = True
        st.markdown("**Competitors Mentioned:**")
        for comp in competitors:
            st.markdown(f"• {comp}")
    
    if comparisons:
        has_competitive_data = True
        st.markdown("**Key Comparisons:**")
        for comp in comparisons:
            st.markdown(f"• {comp}")
    
    if isinstance(competitive_context, dict):
        if competitive_context.get('competitors_mentioned'):
            has_competitive_data = True
            if not competitors:  # Avoid duplication
                st.markdown("**Competitors Mentioned:**")
                for comp in competitive_context['competitors_mentioned']:
                    st.markdown(f"• {comp}")
        
        if competitive_context.get('comparison_points'):
            has_competitive_data = True
            st.markdown("**Comparison Points:**")
            for point in competitive_context['comparison_points']:
                st.markdown(f"• {point}")
    elif isinstance(competitive_context, str) and competitive_context:
        has_competitive_data = True
        st.markdown(competitive_context)
    
    if not has_competitive_data:
        st.info("No competitive analysis found in this review")
    
    st.markdown("---")
    
    # Pros and Cons in columns
    st.markdown("### ⚖️ Pros & Cons Analysis")
    pros_col, cons_col = st.columns(2)
    
    with pros_col:
        st.markdown("#### ✅ Strengths")
        pros = enhanced_data.get('pros', [])
        if isinstance(pros, list) and pros:
            for pro in pros:
                st.markdown(f"• {pro}")
        elif isinstance(pros, str) and pros:
            # Handle pipe-separated format
            pros_list = [p.strip() for p in pros.split('|') if p.strip()]
            for pro in pros_list:
                st.markdown(f"• {pro}")
        else:
            st.markdown("*No specific strengths noted*")
    
    with cons_col:
        st.markdown("#### ⚠️ Areas of Concern")
        cons = enhanced_data.get('cons', [])
        if isinstance(cons, list) and cons:
            for con in cons:
                st.markdown(f"• {con}")
        elif isinstance(cons, str) and cons:
            # Handle pipe-separated format
            cons_list = [c.strip() for c in cons.split('|') if c.strip()]
            for con in cons_list:
                st.markdown(f"• {con}")
        else:
            st.markdown("*No specific concerns noted*")
    
    # Overall Sentiment and Scores
    st.markdown("---")
    st.markdown("### 📊 Sentiment Classification")
    
    score_cols = st.columns(4)
    with score_cols[0]:
        sentiment = enhanced_data.get('overall_sentiment') or enhanced_data.get('overall', 'neutral')
        if sentiment:
            sentiment_color = {
                'positive': '🟢',
                'neutral': '🟡',
                'negative': '🔴'
            }.get(str(sentiment).lower(), '🔵')
            st.metric("Overall Sentiment", f"{sentiment_color} {str(sentiment).title()}")
    
    with score_cols[1]:
        confidence = enhanced_data.get('confidence', 0)
        if confidence:
            st.metric("Confidence", f"{confidence:.2f}" if isinstance(confidence, float) else str(confidence))
    
    with score_cols[2]:
        score = enhanced_data.get('overall_score', enhanced_data.get('score', 'N/A'))
        if score != 'N/A':
            st.metric("Score", f"{score}/10")
    
    with score_cols[3]:
        relevance = enhanced_data.get('relevance_score', 'N/A')
        if relevance != 'N/A':
            st.metric("Relevance", f"{relevance}/10")
    
    # Recommendation if available
    if enhanced_data.get('recommendation'):
        st.markdown("---")
        st.markdown("### 💼 Strategic Recommendation")
        st.warning(enhanced_data['recommendation'])
    
    # Raw data in collapsed section
    with st.expander("🔧 View Complete JSON Data", expanded=False):
        st.json(enhanced_data)
    
    return True