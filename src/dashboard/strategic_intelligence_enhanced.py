"""
Enhanced Strategic Intelligence display using sentiment_data_enhanced
"""
import json
import streamlit as st
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def display_enhanced_sentiment_data(selected_row):
    """
    Display enhanced sentiment data from sentiment_data_enhanced field
    Replaces the old individual sentiment fields with rich structured data
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
            
            # Debug: Check what keys we have
            logger.info(f"Enhanced data keys: {list(enhanced_data.keys())}")
            logger.info(f"Key features type: {type(enhanced_data.get('key_features_mentioned'))}")
            logger.info(f"Brand attributes: {enhanced_data.get('brand_attributes_identified')}")
            logger.info(f"Competitive context: {enhanced_data.get('competitive_context')}")
            logger.info(f"Competitors mentioned: {enhanced_data.get('competitors_mentioned')}")
            
        except Exception as e:
            logger.error(f"Failed to parse enhanced sentiment data: {e}")
            # Fall back to legacy display
            return False
    
    if not enhanced_data:
        # No enhanced data, use legacy display
        return False
    
    # Executive Summary - Always show if available
    if enhanced_data.get('summary'):
        with st.expander("📝 Executive Summary", expanded=True):
            st.markdown(enhanced_data['summary'])
    
    # Key Features & Brand Attributes (PRIMARY NEW DATA)
    with st.expander("🔍 Key Insights - Features & Brand Perception", expanded=True):
        feat_col, attr_col = st.columns(2)
        
        with feat_col:
            st.markdown("**🔑 Key Features Mentioned**")
            # Try both possible field names
            key_features = enhanced_data.get('key_features_mentioned', []) or enhanced_data.get('key_features', [])
            if key_features:
                # Show up to 10 features
                for i, feature in enumerate(key_features[:10], 1):
                    if isinstance(feature, dict):
                        # Extract the feature text from the object
                        feature_text = feature.get('feature', str(feature))
                        st.markdown(f"{i}. {feature_text}")
                    else:
                        st.markdown(f"{i}. {feature}")
            else:
                st.info("No specific features extracted")
        
        with attr_col:
            st.markdown("**🏷️ Brand Attributes Identified**")
            # Try both possible field names
            brand_attributes = enhanced_data.get('brand_attributes_identified', []) or enhanced_data.get('brand_attributes', [])
            if brand_attributes:
                for attr in brand_attributes[:5]:
                    st.markdown(f"• {attr}")
            else:
                st.info("No brand attributes identified")
    
    # Purchase Drivers & Competitive Context
    with st.expander("💰 Purchase Decision Factors", expanded=True):
        purchase_col, compete_col = st.columns(2)
        
        with purchase_col:
            st.markdown("**🛒 Top Purchase Drivers**")
            purchase_drivers = enhanced_data.get('purchase_drivers', [])
            if purchase_drivers:
                for i, driver in enumerate(purchase_drivers[:3], 1):
                    if isinstance(driver, dict):
                        # Extract the reason from the driver object
                        reason = driver.get('reason', 'Unknown')
                        sentiment = driver.get('sentiment', '')
                        if sentiment == 'positive':
                            emoji = "✅"
                        elif sentiment == 'negative':
                            emoji = "⚠️"
                        else:
                            emoji = "•"
                        st.markdown(f"{i}. {emoji} {reason}")
                    else:
                        st.markdown(f"{i}. {driver}")
            else:
                st.info("No purchase drivers identified")
        
        with compete_col:
            st.markdown("**🚗 Competitive Context**")
            competitive = enhanced_data.get('competitive_context', {})
            
            # Try direct field access first
            competitors = enhanced_data.get('competitors_mentioned', [])
            comparisons = enhanced_data.get('competitive_comparisons', [])
            
            if competitors or comparisons or (isinstance(competitive, dict) and competitive):
                if competitors:
                    st.markdown("*Competitors Mentioned:*")
                    for comp in competitors[:5]:
                        st.markdown(f"• {comp}")
                elif isinstance(competitive, dict) and competitive.get('competitors_mentioned'):
                    st.markdown("*Competitors Mentioned:*")
                    for comp in competitive['competitors_mentioned']:
                        st.markdown(f"• {comp}")
                
                if comparisons:
                    st.markdown("*Key Comparisons:*")
                    for comp in comparisons[:3]:
                        st.markdown(f"• {comp}")
                elif isinstance(competitive, dict) and competitive.get('comparison_points'):
                    st.markdown("*Key Comparisons:*")
                    for point in competitive['comparison_points'][:3]:
                        st.markdown(f"• {point}")
                        
                # If competitive is a string, display it
                if isinstance(competitive, str) and competitive:
                    st.markdown(competitive)
            else:
                st.info("No competitive analysis found")
    
    # Pros and Cons - Enhanced display
    pros = enhanced_data.get('pros', [])
    cons = enhanced_data.get('cons', [])
    if pros or cons:
        with st.expander("⚖️ Pros & Cons", expanded=False):
            pros_col, cons_col = st.columns(2)
            
            with pros_col:
                st.markdown("**✅ Strengths**")
                if isinstance(pros, list):
                    for pro in pros:
                        st.markdown(f"• {pro}")
                elif pros:
                    # Handle pipe-separated format
                    pros_list = [p.strip() for p in str(pros).split('|') if p.strip()]
                    for pro in pros_list:
                        st.markdown(f"• {pro}")
                else:
                    st.markdown("*No specific strengths noted*")
            
            with cons_col:
                st.markdown("**⚠️ Areas of Concern**")
                if isinstance(cons, list):
                    for con in cons:
                        st.markdown(f"• {con}")
                elif cons:
                    # Handle pipe-separated format
                    cons_list = [c.strip() for c in str(cons).split('|') if c.strip()]
                    for con in cons_list:
                        st.markdown(f"• {con}")
                else:
                    st.markdown("*No specific concerns noted*")
    
    # Aspect Insights - if available in enhanced data
    aspect_insights = enhanced_data.get('aspect_insights', {})
    if aspect_insights:
        with st.expander("📊 Detailed Aspect Analysis", expanded=False):
            # Create columns for each aspect
            cols = st.columns(5)
            aspects = [
                ('performance', '🏎️ Performance', 0),
                ('design', '🎨 Design', 1),
                ('interior', '🪑 Interior', 2),
                ('technology', '💻 Technology', 3),
                ('value', '💰 Value', 4)
            ]
            
            for aspect_key, label, col_idx in aspects:
                with cols[col_idx]:
                    aspect_data = aspect_insights.get(aspect_key, {})
                    if isinstance(aspect_data, dict):
                        sentiment = aspect_data.get('sentiment', 'neutral')
                        impact = aspect_data.get('impact', 'medium')
                        evidence = aspect_data.get('evidence', '')
                        
                        # Score calculation
                        score_map = {
                            'positive': {'high': 9, 'medium': 7, 'low': 5},
                            'neutral': {'high': 6, 'medium': 5, 'low': 4},
                            'negative': {'high': 2, 'medium': 3, 'low': 4}
                        }
                        score = score_map.get(sentiment, {}).get(impact, 5)
                        
                        # Color based on sentiment
                        color = "🟢" if sentiment == "positive" else "🟡" if sentiment == "neutral" else "🔴"
                        sentiment_text = sentiment.title() if sentiment else "Unknown"
                        st.metric(label, f"{color} {score}/10", help=evidence or f"{sentiment_text} sentiment")
                    else:
                        st.metric(label, "N/A")
    
    # Strategic Intelligence - if available
    strategic_data = {
        'brand_narrative': enhanced_data.get('brand_narrative'),
        'strategic_signal': enhanced_data.get('strategic_signal'),
        'messaging_opportunities': enhanced_data.get('messaging_opportunities', []),
        'risks_to_address': enhanced_data.get('risks_to_address', [])
    }
    
    if any(strategic_data.values()):
        with st.expander("🎯 Strategic Intelligence", expanded=False):
            if strategic_data['brand_narrative']:
                st.markdown("**📖 Brand Narrative Impact**")
                st.markdown(strategic_data['brand_narrative'])
            
            if strategic_data['strategic_signal']:
                st.markdown("**⚡ Strategic Signal**")
                st.markdown(strategic_data['strategic_signal'])
            
            col1, col2 = st.columns(2)
            with col1:
                if strategic_data['messaging_opportunities']:
                    st.markdown("**💡 Messaging Opportunities**")
                    for opp in strategic_data['messaging_opportunities']:
                        st.markdown(f"• {opp}")
            
            with col2:
                if strategic_data['risks_to_address']:
                    st.markdown("**⚠️ Risks to Address**")
                    for risk in strategic_data['risks_to_address']:
                        st.markdown(f"• {risk}")
    
    # Recommendation
    if enhanced_data.get('recommendation'):
        with st.expander("💼 Strategic Recommendation", expanded=False):
            st.markdown(enhanced_data['recommendation'])
    
    # Raw JSON viewer for power users
    with st.expander("🔧 View Complete Enhanced Data", expanded=False):
        st.json(enhanced_data)
    
    return True  # Successfully displayed enhanced data