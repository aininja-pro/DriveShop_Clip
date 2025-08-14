"""
Clean Message Pull-Through Analysis - Side-by-side comparison view
"""
import streamlit as st
import pandas as pd
import json
import altair as alt
from src.utils.database import get_database
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def display_pullthrough_analysis_tab():
    """Display the Message Pull-Through Analysis interface"""
    st.markdown("## 📊 Message Pull-Through Analysis")
    st.markdown("Compare OEM intended messages vs. actual media coverage")
    st.markdown("---")
    
    # Use cached database connection
    @st.cache_resource
    def get_cached_db():
        return get_database()
    
    db = get_cached_db()
    
    # Initialize session state
    if 'pullthrough_analysis_active' not in st.session_state:
        st.session_state.pullthrough_analysis_active = False
    if 'selected_vehicle' not in st.session_state:
        st.session_state.selected_vehicle = None
    
    # Cache OEM messages for 5 minutes - return just the data
    @st.cache_data(ttl=300, show_spinner=False)
    def load_oem_messages():
        # Lightweight projection for initial UI population
        result = db.supabase.table('oem_model_messaging')\
            .select('id, make, model, year')\
            .order('make, model, year')\
            .limit(500)\
            .execute()
        return result.data if result.data else []
    
    # Get OEM messages with caching
    try:
        with st.spinner("Loading OEM messages..."):
            oem_messages_data = load_oem_messages()
        
        # Only show debug in development mode
        if st.checkbox("Show Debug Info", value=False, key="debug_mode"):
            st.sidebar.markdown("### Debug Info")
            st.sidebar.write(f"OEM records found: {len(oem_messages_data)}")
        
        if not oem_messages_data:
            st.warning("No OEM messaging found. Please add OEM messages first.")
            
            # Show more debug info
            st.info("Checking database connection...")
            
            # Try a simpler query to test connection
            test_query = db.supabase.table('oem_model_messaging').select('count', count='exact').execute()
            st.write(f"Table exists with {test_query.count} total records")
            
            # Check if this is an RLS issue
            st.info("💡 This might be a Row Level Security (RLS) issue. The table exists but no rows are visible.")
            st.info("To fix: Check if RLS is enabled on 'oem_model_messaging' table in Supabase and add appropriate policies.")
            
            # Try to show what tables we CAN access
            st.markdown("### Tables we can access:")
            try:
                clips_test = db.supabase.table('clips').select('count', count='exact').execute()
                st.write(f"✅ clips table: {clips_test.count} records")
            except:
                st.write("❌ clips table: Cannot access")
            
            return
    except Exception as e:
        st.error(f"Error querying OEM messages: {str(e)}")
        logger.error(f"Database query error: {str(e)}")
        return
    
    # ---------------------------------
    # Vehicle selector (scalable UX)
    # ---------------------------------
    # Build master vehicle list
    vehicles = [
        {"make": m["make"], "model": m["model"], "year": m["year"]} for m in oem_messages_data
    ]

    # Initialize recents/favorites
    st.session_state.setdefault('recent_vehicles', [])  # list of (make, model, year)
    st.session_state.setdefault('favorite_vehicles', [])

    # Quick search
    st.markdown("#### Find a Vehicle")
    s_col1, s_col2 = st.columns([3, 2])
    with s_col1:
        search_text = st.text_input("Quick Search (type make/model/year)", key="vehicle_quick_search")
    with s_col2:
        st.caption("Tip: try 'cx-50 2025' or 'Mazda CX-50'")

    selected_tuple = None

    if search_text:
        q = search_text.strip().lower()
        filtered = [v for v in vehicles if q in f"{v['make']} {v['model']} {v['year']}".lower()]
        labels = [f"{v['make']} {v['model']} ({v['year']})" for v in filtered]
        choice = st.selectbox("Search results", ["None"] + labels, key="vehicle_search_results")
        if choice != "None":
            parts = choice.split(' (')
            year = int(parts[1].rstrip(')'))
            mk, md = parts[0].split(' ', 1)
            selected_tuple = (mk, md, year)

    # Stepper selectors (Make → Model → Year)
    st.markdown("#### Or use step-by-step selection")
    step_col1, step_col2, step_col3 = st.columns(3)
    with step_col1:
        makes = sorted({v['make'] for v in vehicles})
        sel_make = st.selectbox("Make", ["Choose..."] + makes, key="vehicle_make_sel")
    with step_col2:
        models = sorted({v['model'] for v in vehicles if sel_make == "Choose..." or v['make'] == sel_make})
        sel_model = st.selectbox("Model", ["Choose..."] + models, key="vehicle_model_sel")
    with step_col3:
        years = sorted({v['year'] for v in vehicles if (sel_make == "Choose..." or v['make'] == sel_make) and (sel_model == "Choose..." or v['model'] == sel_model)}, reverse=True)
        sel_year = st.selectbox("Year", ["Choose..."] + [int(y) for y in years], key="vehicle_year_sel")

    if not selected_tuple and sel_make != "Choose..." and sel_model != "Choose..." and sel_year != "Choose...":
        selected_tuple = (sel_make, sel_model, int(sel_year))

    # Favorites and Recents pickers
    favs = st.session_state.get('favorite_vehicles', [])
    recents = st.session_state.get('recent_vehicles', [])
    fr_col1, fr_col2 = st.columns(2)
    with fr_col1:
        if favs:
            fav_labels = [f"{m} {d} ({y})" for (m, d, y) in favs]
            fav_pick = st.selectbox("Favorites", ["None"] + fav_labels, key="vehicle_fav_pick")
            if fav_pick != "None":
                parts = fav_pick.split(' (')
                yr = int(parts[1].rstrip(')'))
                mk, md = parts[0].split(' ', 1)
                selected_tuple = (mk, md, yr)
    with fr_col2:
        if recents:
            rec_labels = [f"{m} {d} ({y})" for (m, d, y) in recents]
            rec_pick = st.selectbox("Recent", ["None"] + rec_labels, key="vehicle_recent_pick")
            if rec_pick != "None":
                parts = rec_pick.split(' (')
                yr = int(parts[1].rstrip(')'))
                mk, md = parts[0].split(' ', 1)
                selected_tuple = (mk, md, yr)

    # Show count for selected
    if selected_tuple:
        make, model, year = selected_tuple
        @st.cache_data(ttl=300, show_spinner=False)
        def get_review_count(make, model):
            result = db.supabase.table('clips').select('count', count='exact').eq('make', make).like('model', f"{model}%").eq('sentiment_completed', True).execute()
            return result.count
        st.metric("Reviews with Sentiment", get_review_count(make, model))

        # Favorite toggle
        is_fav = selected_tuple in favs
        fav_toggle = st.checkbox("⭐ Add to favorites", value=is_fav, key="fav_toggle")
        if fav_toggle and not is_fav:
            st.session_state.favorite_vehicles = list({*favs, selected_tuple})
        if not fav_toggle and is_fav:
            st.session_state.favorite_vehicles = [t for t in favs if t != selected_tuple]

    if selected_tuple and st.button("🔍 Analyze Pull-Through", type="primary"):
        st.session_state.pullthrough_analysis_active = True
        st.session_state.selected_vehicle = selected_tuple
        # Update recents (most recent first, unique, max 10)
        new_recents = [selected_tuple] + [t for t in st.session_state.recent_vehicles if t != selected_tuple]
        st.session_state.recent_vehicles = new_recents[:10]
    
    # Show analysis if active
    if st.session_state.pullthrough_analysis_active and st.session_state.selected_vehicle:
        make, model, year = st.session_state.selected_vehicle
        analyze_model_pullthrough(make, model, year, db)

def analyze_model_pullthrough(make, model, year, db):
    """Analyze pull-through for a specific model"""
    
    with st.spinner("Analyzing message pull-through..."):
        
        # Cache OEM messaging and reviews - return just the data
        @st.cache_data(ttl=300, show_spinner=False)
        def get_vehicle_data(make, model, year):
            oem_result = db.supabase.table('oem_model_messaging')\
                .select('id, make, model, year, messaging_data_enhanced')\
                .eq('make', make).eq('model', model).eq('year', year)\
                .single().execute()
            reviews_result = db.supabase.table('clips')\
                .select('id, wo_number, make, model, media_outlet, published_date, sentiment_data_enhanced, clip_url')\
                .eq('make', make).like('model', f"{model}%").eq('sentiment_completed', True)\
                .limit(500)\
                .execute()
            return oem_result.data, reviews_result.data if reviews_result.data else []
        
        with st.spinner(f"Loading data for {make} {model}..."):
            oem_data, reviews_data = get_vehicle_data(make, model, year)
        
        if not oem_data:
            st.error("OEM messaging not found")
            return
        
        if not reviews_data:
            st.warning(f"No reviews found for {make} {model}")
            return
        
        # Parse OEM messaging
        try:
            oem_messaging = json.loads(oem_data['messaging_data_enhanced'])
        except:
            st.error("Error parsing OEM messaging data")
            return
        
        st.success(f"Found {len(reviews_data)} review(s) to analyze")
        
        # =========================
        # Aggregate vs OEM overview
        # =========================
        try:
            aggregate = aggregate_model_against_oem(oem_messaging, reviews_data)
            display_model_aggregate_overview(make, model, year, aggregate)
        except Exception as e:
            st.warning(f"Aggregate overview unavailable: {e}")

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
        
        # Review selector - compact dropdown & trends
        st.markdown("### 📰 Select Review to Analyze")
        
        # Quick review analysis
        reviews_with_enhanced = sum(1 for r in reviews_data if r.get('sentiment_data_enhanced'))
        
        # Only show debug if enabled
        if st.session_state.get('debug_mode', False):
            st.sidebar.markdown("### Review Analysis")
            st.sidebar.write(f"Total: {len(reviews_data)}")
            st.sidebar.write(f"Enhanced: {reviews_with_enhanced}")
        
        # Show ALL reviews, marking which have enhanced sentiment
        if not reviews_data:
            st.error("No reviews found for this vehicle.")
            return
        
        # Instead of filtering out, show all and mark status
        st.info(f"Found {len(reviews_data)} reviews. {reviews_with_enhanced} have enhanced sentiment analysis.")
        
        # Create review options showing ALL reviews with status indicators
        review_options = []
        review_dict = {}  # To map display string to review data
        
        for r in reviews_data:
            has_enhanced = "✅" if r.get('sentiment_data_enhanced') else "❌"
            option = f"{has_enhanced} {r.get('media_outlet', 'Unknown')} - {r.get('wo_number', 'No WO')} - {r.get('published_date', 'No date')[:10]}"
            review_options.append(option)
            review_dict[option] = r
        
        selected_review_str = st.selectbox(
            "Choose a review:",
            review_options,
            key="review_selector"
        )

        # Trend chart moved into the aggregate overview
        
        if selected_review_str:
            selected_review = review_dict[selected_review_str]
            
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


def aggregate_model_against_oem(oem_messaging: dict, reviews: list) -> dict:
    """Aggregate all reviews for a model against OEM intent (no weights).

    Returns a dictionary with:
    - reviews_count, review_distribution
    - features/attributes/drivers stats with sentiment counts and quotes
    - pull-through percentages and overall alignment
    - per-feature coverage rates and emergent features not in OEM
    """

    # Prepare intended sets (normalized)
    intended_features = [
        (f.get('feature') or '').strip().lower() for f in oem_messaging.get('key_features_intended', [])
    ]
    intended_attributes = [
        (a or '').strip().lower() for a in oem_messaging.get('brand_attributes_intended', [])
    ]
    intended_drivers = [
        (d.get('reason') or '').strip().lower() for d in oem_messaging.get('purchase_drivers_intended', [])
    ]

    # Initialize counters
    feature_stats = {
        f: {'pos': 0, 'neu': 0, 'neg': 0, 'mentions': 0, 'quotes': [], 'review_ids': set()} for f in intended_features
    }
    attr_stats = {
        a: {'reinforced': 0, 'challenged': 0, 'neutral': 0} for a in intended_attributes
    }
    driver_stats = {
        d: {'pos': 0, 'neu': 0, 'neg': 0, 'mentions': 0, 'quotes': []} for d in intended_drivers
    }

    sentiment_totals = {'positive': 0, 'neutral': 0, 'negative': 0}
    emergent_features = {}

    # Helper for sentiment key mapping
    def _s_key(val: str) -> str:
        return {'positive': 'pos', 'neutral': 'neu', 'negative': 'neg'}.get((val or '').lower(), 'neu')

    for r in reviews:
        try:
            data = json.loads(r.get('sentiment_data_enhanced') or '{}')
        except Exception:
            data = {}

        overall = ((data.get('sentiment_classification') or {}).get('overall') or '').lower()
        if overall in sentiment_totals:
            sentiment_totals[overall] += 1

        review_id = r.get('id')

        # Features mentioned
        for m in data.get('key_features_mentioned', []) or []:
            name = (m.get('feature') or '').strip().lower()
            sent = (m.get('sentiment') or 'neutral').lower()
            quote = m.get('quote') or ''

            matched = False
            for f in intended_features:
                if not f:
                    continue
                if f in name or name in f:
                    feature_stats[f]['mentions'] += 1
                    feature_stats[f][_s_key(sent)] += 1
                    if quote:
                        feature_stats[f]['quotes'].append(quote)
                    if review_id is not None:
                        feature_stats[f]['review_ids'].add(review_id)
                    matched = True
                    break

            if not matched and name:
                e = emergent_features.setdefault(name, {'count': 0, 'pos': 0, 'neu': 0, 'neg': 0})
                e['count'] += 1
                e[_s_key(sent)] += 1

        # Brand attributes captured
        for a in data.get('brand_attributes_captured', []) or []:
            name = (a.get('attribute') or '').strip().lower()
            state = (a.get('sentiment') or 'neutral').lower()
            for ia in intended_attributes:
                if ia and (ia in name or name in ia):
                    if state in attr_stats[ia]:
                        attr_stats[ia][state] += 1
                    else:
                        attr_stats[ia]['neutral'] += 1

        # Purchase drivers
        for d in data.get('purchase_drivers', []) or []:
            name = (d.get('reason') or '').strip().lower()
            sent = (d.get('sentiment') or 'neutral').lower()
            quote = d.get('quote') or ''
            for idr in intended_drivers:
                if idr and (idr in name or name in idr):
                    driver_stats[idr]['mentions'] += 1
                    driver_stats[idr][_s_key(sent)] += 1
                    if quote:
                        driver_stats[idr]['quotes'].append(quote)
                    break

    n_reviews = max(len(reviews), 1)

    # Pull-through metrics
    features_pull = (sum(1 for f, v in feature_stats.items() if v['mentions'] > 0) / max(len(intended_features), 1)) * 100
    attrs_pull = (sum(1 for a, v in attr_stats.items() if v['reinforced'] > 0) / max(len(intended_attributes), 1)) * 100
    drivers_pull = (sum(1 for d, v in driver_stats.items() if v['pos'] > 0) / max(len(intended_drivers), 1)) * 100

    # Consistency threshold: mentioned in >=20% of reviews
    threshold = max(int(0.2 * n_reviews), 1)
    features_consistency = (
        sum(1 for _, v in feature_stats.items() if len(v.get('review_ids', set())) >= threshold)
        / max(len(intended_features), 1)
    ) * 100

    review_dist = {
        'positive_pct': 100 * sentiment_totals['positive'] / n_reviews,
        'neutral_pct': 100 * sentiment_totals['neutral'] / n_reviews,
        'negative_pct': 100 * sentiment_totals['negative'] / n_reviews,
    }

    # Compute per-feature coverage rate
    feature_coverage = [
        {
            'feature': f.title(),
            'coverage_pct': (len(v.get('review_ids', set())) / n_reviews) * 100 if n_reviews else 0,
            'mentions': v['mentions'],
            'positive': v['pos'],
            'neutral': v['neu'],
            'negative': v['neg'],
        }
        for f, v in feature_stats.items()
    ]

    # Emergent features sorted by frequency
    emergent_sorted = sorted(emergent_features.items(), key=lambda kv: kv[1]['count'], reverse=True)

    # Monthly sentiment trend (average score per month)
    try:
        trend_df = pd.DataFrame([
            {
                'month': (pd.to_datetime(r.get('published_date')).to_period('M').to_timestamp() if r.get('published_date') else None),
                'overall': ((json.loads(r.get('sentiment_data_enhanced') or '{}').get('sentiment_classification', {}) or {}).get('overall'))
            } for r in reviews
        ])
        trend_df = trend_df.dropna(subset=['month'])
        if not trend_df.empty:
            score_map = {'positive': 1.0, 'neutral': 0.5, 'negative': 0.0}
            trend_df['score'] = trend_df['overall'].map(score_map).fillna(0.5)
            monthly_sent = trend_df.groupby('month')['score'].mean().reset_index()
        else:
            monthly_sent = pd.DataFrame([])
    except Exception:
        monthly_sent = pd.DataFrame([])

    return {
        'reviews_count': len(reviews),
        'review_distribution': review_dist,
        'features_pullthrough_pct': features_pull,
        'features_consistency_pct': features_consistency,
        'attributes_pullthrough_pct': attrs_pull,
        'drivers_pullthrough_pct': drivers_pull,
        'overall_alignment_pct': (features_pull + attrs_pull + drivers_pull) / 3 if (intended_features or intended_attributes or intended_drivers) else 0,
        'feature_coverage': feature_coverage,
        'attr_stats': attr_stats,
        'driver_stats': driver_stats,
        'emergent_features': emergent_sorted,
        'monthly_sentiment': monthly_sent,
    }


def display_model_aggregate_overview(make: str, model: str, year: int, agg: dict) -> None:
    """Render the aggregate overview section for a model."""
    st.markdown("### 📊 Model Aggregate vs OEM")

    # Top metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Features Pull‑Through", f"{agg['features_pullthrough_pct']:.0f}%")
    with c2:
        st.metric("Attributes Pull‑Through", f"{agg['attributes_pullthrough_pct']:.0f}%")
    with c3:
        st.metric("Drivers Pull‑Through", f"{agg['drivers_pullthrough_pct']:.0f}%")
    with c4:
        st.metric("Alignment", f"{agg['overall_alignment_pct']:.0f}%")
    with c5:
        st.metric("Reviews", f"{agg['reviews_count']}")

    # Review sentiment distribution
    st.markdown("#### Review Sentiment Distribution")
    dist_df = pd.DataFrame([
        {"Sentiment": "Positive", "Percent": agg['review_distribution']['positive_pct'], "color": "#B7E1CD"},  # light green
        {"Sentiment": "Neutral", "Percent": agg['review_distribution']['neutral_pct'], "color": "#CFE8FF"},   # light blue
        {"Sentiment": "Negative", "Percent": agg['review_distribution']['negative_pct'], "color": "#F8C7C7"},  # light red
    ])
    bar = alt.Chart(dist_df).mark_bar().encode(
        x=alt.X('Sentiment:N', sort=['Negative', 'Neutral', 'Positive']),
        y=alt.Y('Percent:Q'),
        color=alt.Color('color:N', scale=None, legend=None)
    )
    st.altair_chart(bar, use_container_width=True)

    # Monthly sentiment trend
    if isinstance(agg.get('monthly_sentiment'), pd.DataFrame) and not agg['monthly_sentiment'].empty:
        st.markdown("#### Monthly Sentiment Trend")
        ms_df = agg['monthly_sentiment'].copy()
        chart = alt.Chart(ms_df).mark_line(interpolate='monotone', strokeWidth=3, color='#1976d2').encode(
            x=alt.X('month:T', title='Month'),
            y=alt.Y('score:Q', title='Avg Sentiment', scale=alt.Scale(domain=[0,1]))
        )
        st.altair_chart(chart, use_container_width=True)

    # Feature coverage table (sorted by coverage)
    st.markdown("#### Intended Feature Coverage")
    fc_df = pd.DataFrame(agg['feature_coverage']).sort_values('coverage_pct', ascending=False)
    if not fc_df.empty:
        # Display-friendly copy with percentage formatting
        fc_df_disp = fc_df.copy()
        fc_df_disp['coverage_pct'] = fc_df_disp['coverage_pct'].map(lambda v: f"{v:.0f}%")
        st.dataframe(
            fc_df_disp,
            use_container_width=True,
        )
    else:
        st.info("No intended features defined for this model.")

    # Wins and Gaps
    col_w, col_g = st.columns(2)
    # Thresholds for a "strong" win
    wins_threshold = 20.0  # coverage % to consider a consistent win (reduced from 30)
    wins_pos_share = 0.5   # at least 50% of mentions should be positive (reduced from 60)
    with col_w:
        st.markdown("#### Top Wins (Matched Well)")
        if not fc_df.empty:
            fc = fc_df.copy()
            fc['total'] = fc['positive'] + fc['neutral'] + fc['negative']
            fc['positive_share'] = fc.apply(lambda r: (r['positive'] / r['total']) if r['total'] > 0 else 0.0, axis=1)
            wins = fc[(fc['coverage_pct'] >= wins_threshold) & (fc['positive_share'] >= wins_pos_share) & (fc['total'] > 0)]
            wins = wins.sort_values(['positive_share', 'coverage_pct'], ascending=False)
            # Ensure at least 4 positives shown if possible
            wins = wins.head(max(4, min(5, len(wins))))
            if not wins.empty:
                for _, row in wins.iterrows():
                    st.success(f"✓ {row['feature']} — {(row['coverage_pct']):.0f}% coverage, {int(row['positive'])} positive mentions")
            else:
                # Fallback: show best positive signals even if they don't meet thresholds
                fallback = fc[fc['positive'] > 0].sort_values(['positive', 'coverage_pct'], ascending=False).head(4)
                if not fallback.empty:
                    st.info("Promising positive signals:")
                    for _, row in fallback.iterrows():
                        st.success(f"• {row['feature']} — {int(row['positive'])} positive mentions, {(row['coverage_pct']):.0f}% coverage")
                else:
                    st.info("No strong wins yet. Keep an eye on coverage and tone.")
        else:
            st.info("No intended features to score.")
    with col_g:
        st.markdown("#### Biggest Gaps (Needs Work)")
        if not fc_df.empty:
            fc = fc_df.copy()
            fc['total'] = fc['positive'] + fc['neutral'] + fc['negative']
            # Gap if never mentioned, or if negative dominates
            gaps_df = fc[(fc['coverage_pct'] == 0.0) | ((fc['total'] > 0) & (fc['negative'] > fc['positive']))]
            gaps_df = gaps_df.sort_values(['coverage_pct', 'negative'], ascending=[True, False]).head(5)
            if not gaps_df.empty:
                for _, row in gaps_df.iterrows():
                    note = "not mentioned" if row['coverage_pct'] == 0.0 else f"{int(row['negative'])} negative vs {int(row['positive'])} positive"
                    st.error(f"✗ {row['feature']} — {note}")
            else:
                st.success("No major gaps detected.")
        else:
            st.info("No intended features to score.")

    # Optional: Emergent themes in an expander
    if agg['emergent_features']:
        with st.expander("Emergent Themes (Not in OEM)", expanded=False):
            emergent_df = pd.DataFrame([
                {"Feature": name.title(), "Mentions": stats['count']} for name, stats in agg['emergent_features'][:10]
            ])
            st.dataframe(emergent_df, use_container_width=True)

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