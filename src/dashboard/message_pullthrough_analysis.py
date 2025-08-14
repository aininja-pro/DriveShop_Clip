"""
Message Pull-Through Analysis Dashboard
Compares OEM intended messages vs what actually appears in media coverage
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime
from src.utils.database import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def display_pullthrough_analysis_tab():
    """Display the Message Pull-Through Analysis interface"""
    st.markdown("## 📊 Message Pull-Through Analysis")
    st.markdown("Compare what OEMs want said vs. what media actually says")
    st.markdown("---")
    
    db = DatabaseManager()
    
    # Get available OEM messages
    oem_messages = db.supabase.table('oem_model_messaging').select('*').order('make, model').execute()
    
    if not oem_messages.data:
        st.warning("No OEM messaging found. Please add OEM messages first.")
        return
    
    # Create selection interface
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Get unique makes
        makes = list(set(msg['make'] for msg in oem_messages.data))
        selected_make = st.selectbox("Select Make", ["All"] + sorted(makes))
    
    with col2:
        # Filter models by make
        if selected_make == "All":
            models = [(msg['make'], msg['model']) for msg in oem_messages.data]
        else:
            models = [(msg['make'], msg['model']) for msg in oem_messages.data if msg['make'] == selected_make]
        
        model_options = ["All"] + [f"{make} {model}" for make, model in sorted(set(models))]
        selected_model = st.selectbox("Select Model", model_options)
    
    with col3:
        analysis_type = st.selectbox(
            "Analysis Type",
            ["Summary Overview", "Detailed Comparison", "Gap Analysis", "Trend Analysis"]
        )
    
    # Run Analysis button
    if st.button("🔍 Run Analysis", type="primary"):
        run_pullthrough_analysis(selected_make, selected_model, analysis_type, db)

def run_pullthrough_analysis(make, model, analysis_type, db):
    """Run the pull-through analysis"""
    
    with st.spinner("Analyzing message pull-through..."):
        
        # Get OEM messages
        if model != "All" and " " in model:
            make_filter, model_filter = model.split(" ", 1)
            oem_query = db.supabase.table('oem_model_messaging').select('*').eq('make', make_filter).eq('model', model_filter)
        elif make != "All":
            oem_query = db.supabase.table('oem_model_messaging').select('*').eq('make', make)
        else:
            oem_query = db.supabase.table('oem_model_messaging').select('*')
        
        oem_messages = oem_query.execute()
        
        if not oem_messages.data:
            st.error("No OEM messages found for selection")
            return
        
        # Get corresponding reviews with sentiment
        reviews_data = []
        for oem_msg in oem_messages.data:
            # Use LIKE query to match model variants (e.g., "CX-50" matches "CX-50 Turbo Premium")
            reviews = db.supabase.table('clips').select('*').eq('make', oem_msg['make']).like('model', f"{oem_msg['model']}%").eq('sentiment_completed', True).execute()
            
            if reviews.data:
                for review in reviews.data:
                    review['oem_messaging_id'] = oem_msg['id']
                    review['oem_data'] = oem_msg
                    reviews_data.extend(reviews.data)
        
        if not reviews_data:
            st.warning("No reviews found with sentiment analysis for selected vehicles")
            return
        
        # Display analysis based on type
        if analysis_type == "Summary Overview":
            display_summary_overview(oem_messages.data, reviews_data)
        elif analysis_type == "Detailed Comparison":
            display_detailed_comparison(oem_messages.data, reviews_data)
        elif analysis_type == "Gap Analysis":
            display_gap_analysis(oem_messages.data, reviews_data)
        elif analysis_type == "Trend Analysis":
            display_trend_analysis(oem_messages.data, reviews_data)

def display_summary_overview(oem_messages, reviews):
    """Display high-level pull-through metrics"""
    
    st.markdown("### 📈 Pull-Through Summary")
    
    # Calculate overall metrics
    total_metrics = {
        'total_oem_messages': len(oem_messages),
        'total_reviews': len(reviews),
        'models_analyzed': len(set((r['make'], r['model']) for r in reviews))
    }
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("OEM Models", total_metrics['total_oem_messages'])
    with col2:
        st.metric("Reviews Analyzed", total_metrics['total_reviews'])
    with col3:
        st.metric("Models Covered", total_metrics['models_analyzed'])
    
    # Analyze each model
    st.markdown("### 🚗 Model-by-Model Analysis")
    
    for oem_msg in oem_messages:
        model_reviews = [r for r in reviews if r['make'] == oem_msg['make'] and r['model'].startswith(oem_msg['model'])]
        
        if model_reviews:
            with st.expander(f"{oem_msg['make']} {oem_msg['model']} ({len(model_reviews)} reviews)", expanded=True):
                
                # Parse OEM messaging
                oem_data = json.loads(oem_msg['messaging_data_enhanced']) if oem_msg.get('messaging_data_enhanced') else {}
                
                # Calculate pull-through metrics
                metrics = calculate_pullthrough_metrics(oem_data, model_reviews)
                
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "Features Pull-Through",
                        f"{metrics['features_pullthrough']:.0f}%",
                        help="% of OEM features mentioned in reviews"
                    )
                
                with col2:
                    st.metric(
                        "Brand Attributes",
                        f"{metrics['attributes_pullthrough']:.0f}%",
                        help="% of brand attributes communicated"
                    )
                
                with col3:
                    st.metric(
                        "Purchase Drivers",
                        f"{metrics['drivers_pullthrough']:.0f}%",
                        help="% of purchase drivers reinforced"
                    )
                
                with col4:
                    sentiment_score = metrics.get('sentiment_alignment', 0)
                    delta_color = "normal" if sentiment_score >= 70 else "inverse"
                    st.metric(
                        "Sentiment Alignment",
                        f"{sentiment_score:.0f}%",
                        delta=f"{sentiment_score - 70:.0f}",
                        delta_color=delta_color,
                        help="How well sentiment matches OEM intent"
                    )
                
                # Top performing features
                st.markdown("**💪 Strongest Pull-Through:**")
                if metrics['top_features']:
                    for feature in metrics['top_features'][:3]:
                        st.success(f"✓ {feature}")
                
                # Biggest gaps
                st.markdown("**⚠️ Biggest Gaps:**")
                if metrics['missing_features']:
                    for feature in metrics['missing_features'][:3]:
                        st.warning(f"✗ {feature}")

def calculate_pullthrough_metrics(oem_data, reviews):
    """Calculate pull-through metrics for a model"""
    
    metrics = {
        'features_pullthrough': 0,
        'attributes_pullthrough': 0,
        'drivers_pullthrough': 0,
        'sentiment_alignment': 0,
        'top_features': [],
        'missing_features': []
    }
    
    # Aggregate all review data
    all_features_mentioned = []
    all_attributes_mentioned = []
    all_drivers_mentioned = []
    
    for review in reviews:
        if review.get('sentiment_data_enhanced'):
            try:
                review_data = json.loads(review['sentiment_data_enhanced'])
            except (json.JSONDecodeError, TypeError):
                continue
            
            # Collect all mentioned items
            all_features_mentioned.extend([f['feature'].lower() for f in review_data.get('key_features_mentioned', [])])
            all_attributes_mentioned.extend([a.lower() for a in review_data.get('brand_attributes_identified', [])])
            all_drivers_mentioned.extend([d['reason'].lower() for d in review_data.get('purchase_drivers', [])])
    
    # Calculate feature pull-through
    oem_features = [f['feature'].lower() for f in oem_data.get('key_features_intended', [])]
    if oem_features:
        features_found = 0
        for oem_feature in oem_features:
            if any(oem_feature in mentioned or mentioned in oem_feature for mentioned in all_features_mentioned):
                features_found += 1
                metrics['top_features'].append(oem_feature.title())
            else:
                metrics['missing_features'].append(oem_feature.title())
        
        metrics['features_pullthrough'] = (features_found / len(oem_features)) * 100
    
    # Calculate attribute pull-through
    oem_attributes = [a.lower() for a in oem_data.get('brand_attributes_intended', [])]
    if oem_attributes:
        attrs_found = sum(1 for attr in oem_attributes if attr in all_attributes_mentioned)
        metrics['attributes_pullthrough'] = (attrs_found / len(oem_attributes)) * 100
    
    # Calculate driver pull-through
    oem_drivers = [d['reason'].lower() for d in oem_data.get('purchase_drivers_intended', [])]
    if oem_drivers:
        drivers_found = sum(1 for driver in oem_drivers if driver in all_drivers_mentioned)
        metrics['drivers_pullthrough'] = (drivers_found / len(oem_drivers)) * 100
    
    # Calculate sentiment alignment (simplified)
    # High score if reviews are mostly positive when OEM wants positive
    positive_reviews = 0
    for r in reviews:
        try:
            data = json.loads(r.get('sentiment_data_enhanced', '{}'))
            if data.get('sentiment_classification', {}).get('overall') == 'positive':
                positive_reviews += 1
        except (json.JSONDecodeError, TypeError):
            continue
    if reviews:
        metrics['sentiment_alignment'] = (positive_reviews / len(reviews)) * 100
    
    return metrics

def display_detailed_comparison(oem_messages, reviews):
    """Show detailed side-by-side comparison"""
    
    st.markdown("### 🔍 Detailed Message Comparison")
    
    # Select specific review to compare
    review_options = [f"{r['media_outlet']} - {r['wo_number']} ({r['make']} {r['model']})" for r in reviews]
    selected_review_idx = st.selectbox("Select Review to Analyze", range(len(review_options)), format_func=lambda x: review_options[x])
    
    if selected_review_idx is not None:
        selected_review = reviews[selected_review_idx]
        oem_msg = selected_review['oem_data']
        
        # Parse data
        try:
            oem_data = json.loads(oem_msg['messaging_data_enhanced']) if oem_msg.get('messaging_data_enhanced') else {}
            review_data = json.loads(selected_review['sentiment_data_enhanced']) if selected_review.get('sentiment_data_enhanced') else {}
        except (json.JSONDecodeError, TypeError) as e:
            st.error(f"Error parsing data: {str(e)}")
            return
        
        # Display comparison
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📢 OEM Intended")
            
            # Positioning
            st.markdown("**Positioning:**")
            st.info(oem_data.get('positioning_statement', 'N/A'))
            
            # Key Features
            st.markdown("**Key Features:**")
            for feature in oem_data.get('key_features_intended', [])[:5]:
                st.write(f"• {feature['feature']}")
            
            # Brand Attributes
            st.markdown("**Brand Attributes:**")
            for attr in oem_data.get('brand_attributes_intended', []):
                st.write(f"• {attr}")
        
        with col2:
            st.markdown("### 📰 Media Coverage")
            
            # Summary
            st.markdown("**Review Summary:**")
            st.info(review_data.get('summary', 'N/A'))
            
            # Features Mentioned
            st.markdown("**Features Mentioned:**")
            for feature in review_data.get('key_features_mentioned', [])[:5]:
                sentiment = feature.get('sentiment', 'neutral')
                emoji = {'positive': '✅', 'negative': '❌', 'neutral': '➖'}.get(sentiment, '')
                st.write(f"{emoji} {feature['feature']}")
            
            # Attributes Identified
            st.markdown("**Attributes Identified:**")
            for attr in review_data.get('brand_attributes_identified', []):
                st.write(f"• {attr}")
        
        # Pull-through analysis for this specific review
        st.markdown("### 📊 Pull-Through Analysis")
        
        # Check each OEM feature
        feature_matches = []
        for oem_feature in oem_data.get('key_features_intended', []):
            found = False
            for review_feature in review_data.get('key_features_mentioned', []):
                if oem_feature['feature'].lower() in review_feature['feature'].lower() or review_feature['feature'].lower() in oem_feature['feature'].lower():
                    found = True
                    feature_matches.append({
                        'oem': oem_feature['feature'],
                        'review': review_feature['feature'],
                        'sentiment': review_feature.get('sentiment', 'neutral'),
                        'quote': review_feature.get('quote', '')
                    })
                    break
            
            if not found:
                feature_matches.append({
                    'oem': oem_feature['feature'],
                    'review': 'NOT MENTIONED',
                    'sentiment': 'missing',
                    'quote': ''
                })
        
        # Display matches
        for match in feature_matches:
            if match['sentiment'] == 'missing':
                st.error(f"❌ **{match['oem']}** - Not mentioned")
            elif match['sentiment'] == 'positive':
                st.success(f"✅ **{match['oem']}** → {match['review']}")
                if match['quote']:
                    st.caption(f"Quote: \"{match['quote']}\"")
            elif match['sentiment'] == 'negative':
                st.warning(f"⚠️ **{match['oem']}** → {match['review']} (negative sentiment)")
            else:
                st.info(f"➖ **{match['oem']}** → {match['review']} (neutral)")

def display_gap_analysis(oem_messages, reviews):
    """Identify biggest gaps in messaging"""
    
    st.markdown("### 🎯 Gap Analysis")
    st.info("Identifying OEM messages that aren't getting through to media")
    
    # Analyze gaps for each model
    gap_data = []
    
    for oem_msg in oem_messages:
        model_reviews = [r for r in reviews if r['make'] == oem_msg['make'] and r['model'].startswith(oem_msg['model'])]
        
        if model_reviews:
            oem_data = json.loads(oem_msg['messaging_data_enhanced'])
            
            # Track which messages appear in reviews
            feature_coverage = {}
            
            for feature in oem_data.get('key_features_intended', []):
                feature_name = feature['feature']
                feature_coverage[feature_name] = {
                    'mentioned_count': 0,
                    'total_reviews': len(model_reviews),
                    'coverage_rate': 0
                }
                
                # Check each review
                for review in model_reviews:
                    review_data = json.loads(review.get('sentiment_data_enhanced', '{}'))
                    review_features = [f['feature'].lower() for f in review_data.get('key_features_mentioned', [])]
                    
                    if any(feature_name.lower() in rf or rf in feature_name.lower() for rf in review_features):
                        feature_coverage[feature_name]['mentioned_count'] += 1
                
                # Calculate coverage rate
                if len(model_reviews) > 0:
                    feature_coverage[feature_name]['coverage_rate'] = (
                        feature_coverage[feature_name]['mentioned_count'] / len(model_reviews)
                    ) * 100
            
            # Add to gap data
            for feature_name, coverage in feature_coverage.items():
                gap_data.append({
                    'Make': oem_msg['make'],
                    'Model': oem_msg['model'],
                    'Feature': feature_name,
                    'Coverage Rate': f"{coverage['coverage_rate']:.0f}%",
                    'Mentioned In': f"{coverage['mentioned_count']} of {coverage['total_reviews']} reviews",
                    'Gap Score': 100 - coverage['coverage_rate']
                })
    
    if gap_data:
        # Sort by gap score (biggest gaps first)
        gap_df = pd.DataFrame(gap_data)
        gap_df = gap_df.sort_values('Gap Score', ascending=False)
        
        # Display biggest gaps
        st.markdown("#### 🚨 Biggest Messaging Gaps")
        
        biggest_gaps = gap_df.head(10)
        for _, row in biggest_gaps.iterrows():
            if row['Gap Score'] > 50:  # Only show significant gaps
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.error(f"**{row['Make']} {row['Model']}**: {row['Feature']}")
                with col2:
                    st.write(row['Mentioned In'])
                with col3:
                    st.write(row['Coverage Rate'])
        
        # Full table
        st.markdown("#### 📊 Complete Gap Analysis")
        st.dataframe(gap_df, use_container_width=True)

def display_trend_analysis(oem_messages, reviews):
    """Show trends over time"""
    
    st.markdown("### 📈 Pull-Through Trends")
    
    # Prepare data for trend analysis
    trend_data = []
    
    for review in reviews:
        if review.get('sentiment_data_enhanced') and review.get('published_date'):
            oem_msg = review['oem_data']
            oem_data = json.loads(oem_msg['messaging_data_enhanced'])
            review_data = json.loads(review['sentiment_data_enhanced'])
            
            # Calculate pull-through for this review
            oem_features = [f['feature'].lower() for f in oem_data.get('key_features_intended', [])]
            review_features = [f['feature'].lower() for f in review_data.get('key_features_mentioned', [])]
            
            features_found = 0
            for oem_feature in oem_features:
                if any(oem_feature in rf or rf in oem_feature for rf in review_features):
                    features_found += 1
            
            pullthrough_rate = (features_found / len(oem_features) * 100) if oem_features else 0
            
            trend_data.append({
                'Date': review['published_date'],
                'Make': review['make'],
                'Model': review['model'],
                'Pull-Through Rate': pullthrough_rate,
                'Media Outlet': review['media_outlet']
            })
    
    if trend_data:
        df = pd.DataFrame(trend_data)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        
        # Group by month
        df['Month'] = df['Date'].dt.to_period('M')
        monthly_avg = df.groupby(['Month', 'Make', 'Model'])['Pull-Through Rate'].mean().reset_index()
        
        # Display chart
        st.line_chart(
            data=monthly_avg.pivot(index='Month', columns='Model', values='Pull-Through Rate'),
            use_container_width=True
        )
        
        # Summary stats
        st.markdown("#### 📊 Summary Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_rate = df['Pull-Through Rate'].mean()
            st.metric("Average Pull-Through", f"{avg_rate:.1f}%")
        
        with col2:
            best_outlet = df.groupby('Media Outlet')['Pull-Through Rate'].mean().idxmax()
            st.metric("Best Performing Outlet", best_outlet)
        
        with col3:
            trend = "📈 Improving" if df.tail(5)['Pull-Through Rate'].mean() > df.head(5)['Pull-Through Rate'].mean() else "📉 Declining"
            st.metric("Recent Trend", trend)

# Add export functionality
def export_analysis(data, filename):
    """Export analysis results"""
    import io
    
    output = io.StringIO()
    
    if isinstance(data, pd.DataFrame):
        data.to_csv(output, index=False)
    else:
        json.dump(data, output, indent=2)
    
    st.download_button(
        label="📥 Download Analysis",
        data=output.getvalue(),
        file_name=filename,
        mime="text/csv" if filename.endswith('.csv') else "application/json"
    )