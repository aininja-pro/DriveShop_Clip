"""
Strategic Intelligence Dashboard - Search-driven sentiment analysis viewer.
Loads filter options instantly, queries clips only when user searches/filters.
"""
import json
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def display_strategic_intelligence_tab(search_clips, load_filter_options, fetch_detail):
    """
    Display the Strategic Intelligence tab with search-driven clip loading.

    Args:
        search_clips: Callable(make, sentiment, search_text) -> list of clip dicts.
        load_filter_options: Callable() -> (makes_list, sentiments_list, total_count).
        fetch_detail: Callable(clip_id) -> dict with sentiment_data_enhanced.
    """
    # ── Header ──────────────────────────────────────────────────────────
    st.markdown(
        '<h2 style="margin-bottom: 0.2rem;">Strategic Intelligence Dashboard</h2>'
        '<p style="color: #6c757d; margin-top: 0; margin-bottom: 1rem;">'
        'Search, filter, and explore enhanced sentiment analysis across all reviewed clips</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Load filter options (lightweight) ───────────────────────────────
    makes, sentiments, total_count = load_filter_options()

    # ── Filter Bar ──────────────────────────────────────────────────────
    f1, f2, f3, f4 = st.columns([1.5, 1.5, 3, 1])

    with f1:
        selected_make = st.selectbox("Make / Brand", ["All"] + makes, key="si_make")

    with f2:
        selected_sentiment = st.selectbox("Sentiment", ["All"] + sentiments, key="si_sentiment")

    with f3:
        search_text = st.text_input(
            "Search WO#, Contact, or Media Outlet",
            placeholder="e.g. 1261373 or Motor Trend",
            key="si_search",
        )

    with f4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Refresh", key="si_refresh"):
            st.cache_data.clear()
            st.rerun()

    # ── Run search ──────────────────────────────────────────────────────
    make_filter = selected_make if selected_make != "All" else ''
    sentiment_filter = selected_sentiment if selected_sentiment != "All" else ''

    has_filters = make_filter or sentiment_filter or search_text

    if not has_filters:
        st.markdown("---")
        m1, m2 = st.columns([1, 3])
        with m1:
            st.metric("Total Analyzed Clips", total_count)
        with m2:
            st.info("Use the filters above to search clips, or select a Make/Brand to browse. "
                    "You can also search by WO number, contact name, or media outlet.")
        return

    with st.spinner("Searching clips..."):
        results = search_clips(make_filter, sentiment_filter, search_text)

    if not results:
        st.warning("No clips match your search. Try different filters.")
        return

    # ── Build DataFrame ─────────────────────────────────────────────────
    df = pd.DataFrame(results)
    df['published_date'] = pd.to_datetime(df['published_date'], errors='coerce')

    # ── Summary Metrics ─────────────────────────────────────────────────
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Results", len(df))
    with m2:
        st.metric("Positive", int((df['overall_sentiment'].str.lower() == 'positive').sum()))
    with m3:
        st.metric("Neutral", int((df['overall_sentiment'].str.lower() == 'neutral').sum()))
    with m4:
        st.metric("Negative", int((df['overall_sentiment'].str.lower() == 'negative').sum()))

    # ── Results Table (AgGrid) ──────────────────────────────────────────
    display_df = df[['wo_number', 'make', 'model', 'contact',
                      'media_outlet', 'published_date', 'overall_sentiment']].copy()
    display_df.columns = ['WO #', 'Make', 'Model', 'Contact',
                           'Media Outlet', 'Published Date', 'Sentiment']
    display_df['Published Date'] = display_df['Published Date'].dt.strftime('%Y-%m-%d')
    display_df = display_df.fillna('')
    display_df = display_df.reset_index(drop=True)

    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_default_column(sortable=True, resizable=True)
    gb.configure_column("WO #", minWidth=120)
    gb.configure_column("Make", minWidth=90)
    gb.configure_column("Model", minWidth=110)
    gb.configure_column("Contact", minWidth=150)
    gb.configure_column("Media Outlet", minWidth=180)
    gb.configure_column("Published Date", minWidth=120)
    gb.configure_column("Sentiment", minWidth=100)
    gb.configure_pagination(paginationAutoPageSize=True)
    grid_options = gb.build()

    st.markdown("**Select a clip to view detailed analysis:**")
    grid_response = AgGrid(
        display_df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=350,
        fit_columns_on_grid_load=True,
        columns_auto_size_mode='FIT_ALL_COLUMNS_TO_VIEW',
        theme="alpine",
        enable_enterprise_modules=True,
        key="si_grid",
    )

    # ── Selection → Detail Fetch ────────────────────────────────────────
    selected_rows = grid_response.selected_rows
    has_selection = (
        selected_rows is not None
        and (len(selected_rows) > 0 if not hasattr(selected_rows, 'empty') else not selected_rows.empty)
    )

    if not has_selection:
        return

    # Get the selected WO and look up the clip id
    if hasattr(selected_rows, 'iloc'):
        sel = selected_rows.iloc[0].to_dict()
    else:
        sel = selected_rows[0]

    selected_wo = sel.get('WO #', '')
    clip_record = next((c for c in results if c.get('wo_number') == selected_wo), None)
    if not clip_record:
        st.error(f"Could not locate clip data for WO {selected_wo}")
        return

    # Stage 2: fetch the heavy sentiment payload for this one clip
    with st.spinner(f"Loading analysis for WO {selected_wo}..."):
        detail = fetch_detail(clip_record['id'])

    raw_data = detail.get('sentiment_data_enhanced') if detail else None
    if not raw_data:
        st.warning("No enhanced sentiment data available for this clip.")
        return

    enhanced = json.loads(raw_data) if isinstance(raw_data, str) else raw_data

    # ── Render Full Analysis ────────────────────────────────────────────
    _render_analysis(clip_record, enhanced)


# ═══════════════════════════════════════════════════════════════════════════
# Private rendering helpers
# ═══════════════════════════════════════════════════════════════════════════

def _render_analysis(clip: dict, data: dict):
    """Render the complete analysis view for a selected clip."""
    st.markdown("---")

    # ── Clip Info Header ────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        contact = clip.get('contact') or 'Unknown'
        st.markdown(f"**Media Contact**  \n{contact}")
    with c2:
        st.markdown(f"**Publication**  \n{clip.get('media_outlet') or 'N/A'}")
    with c3:
        st.markdown(f"**Vehicle**  \n{clip.get('make', '')} {clip.get('model', '')}")
    with c4:
        date_val = clip.get('published_date') or 'N/A'
        st.markdown(f"**Date**  \n{date_val}")

    # ── Executive Summary ───────────────────────────────────────────────
    if data.get('summary'):
        st.markdown("")
        st.info(f"**Executive Summary:** {data['summary']}")

    # ── Scores Row ──────────────────────────────────────────────────────
    _render_scores(data)

    # ── Tabbed Detail Sections ──────────────────────────────────────────
    tab_overview, tab_features, tab_brand, tab_competitive, tab_raw = st.tabs([
        "Overview", "Key Features", "Brand & Purchase",
        "Competitive", "Raw Data",
    ])

    with tab_overview:
        _render_overview(data)
    with tab_features:
        _render_features(data)
    with tab_brand:
        _render_brand_purchase(data)
    with tab_competitive:
        _render_competitive(data)
    with tab_raw:
        st.json(data)

    # ── Action Bar ──────────────────────────────────────────────────────
    st.markdown("---")
    a1, a2, _ = st.columns([1, 1, 4])
    with a1:
        if st.button("Export Analysis", key="si_export"):
            st.info("Export functionality coming soon.")
    with a2:
        url = clip.get('clip_url')
        if url:
            st.link_button("View Original Clip", url)


def _render_scores(data: dict):
    """Render the 4-column scores metrics row."""
    scores = [
        ('overall_score', 'Overall Score'),
        ('relevance_score', 'Relevance'),
        ('marketing_impact_score', 'Marketing Impact'),
        ('brand_alignment', 'Brand Alignment'),
    ]
    has_any = any(k in data for k, _ in scores)
    if not has_any:
        return

    cols = st.columns(4)
    for i, (key, label) in enumerate(scores):
        with cols[i]:
            val = data.get(key)
            if val is not None:
                if isinstance(val, bool):
                    st.metric(label, "Yes" if val else "No")
                else:
                    st.metric(label, f"{val}/10" if isinstance(val, (int, float)) else str(val))


def _sentiment_color(sentiment: str) -> str:
    """Return emoji indicator for a sentiment string."""
    s = str(sentiment).lower()
    if 'positive' in s:
        return '🟢'
    if 'negative' in s:
        return '🔴'
    return '🟡'


def _render_overview(data: dict):
    """Render sentiment classification and pros/cons."""
    # Sentiment Classification
    sent = data.get('sentiment_classification', {})
    if sent:
        st.markdown("#### Sentiment Classification")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            overall = sent.get('overall', 'N/A')
            st.metric("Overall", f"{_sentiment_color(overall)} {overall.title()}")
        with c2:
            conf = sent.get('confidence', 'N/A')
            display = f"{conf:.0%}" if isinstance(conf, (float, int)) else conf
            st.metric("Confidence", display)
        with c3:
            rationale = sent.get('rationale', '')
            if rationale:
                st.markdown(f"**Rationale**")
                st.markdown(f"> {rationale}")

    # Recommendation
    if data.get('recommendation'):
        st.markdown("")
        st.warning(f"**Recommendation:** {data['recommendation']}")

    # Pros / Cons side-by-side
    pros = data.get('pros', [])
    cons = data.get('cons', [])
    if pros or cons:
        st.markdown("---")
        st.markdown("#### Pros & Cons")
        pc1, pc2 = st.columns(2)
        with pc1:
            if pros:
                for p in pros:
                    st.success(f"{p}")
            else:
                st.caption("No pros identified")
        with pc2:
            if cons:
                for c in cons:
                    st.warning(f"{c}")
            else:
                st.caption("No cons identified")


def _render_features(data: dict):
    """Render key features mentioned with quotes."""
    features = data.get('key_features_mentioned', [])
    if not features:
        st.info("No key features identified in this clip.")
        return

    st.markdown(f"#### {len(features)} Key Features Mentioned")
    st.markdown("")

    for i, feat in enumerate(features):
        name = feat.get('feature', 'Unknown')
        sentiment = feat.get('sentiment', 'neutral')
        quote = feat.get('quote', '')
        context = feat.get('context', '')

        icon = _sentiment_color(sentiment)
        label = f"**{i+1}. {name}** {icon} _{sentiment}_"

        if sentiment == 'positive':
            st.success(label)
        elif sentiment == 'negative':
            st.warning(label)
        else:
            st.info(label)

        if quote:
            st.markdown(f'> *"{quote}"*')
        if context and context != quote:
            st.caption(f"Context: {context}")
        st.markdown("")


def _render_brand_purchase(data: dict):
    """Render brand attributes and purchase drivers."""
    # Brand Attributes
    attrs = data.get('brand_attributes_identified', data.get('brand_attributes_captured', []))
    if attrs:
        st.markdown("#### Brand Attributes")
        if isinstance(attrs, list) and attrs:
            if isinstance(attrs[0], dict):
                # Structured: {attribute, sentiment, evidence}
                for attr in attrs:
                    name = attr.get('attribute', str(attr))
                    sentiment = attr.get('sentiment', '')
                    evidence = attr.get('evidence', '')
                    icon = _sentiment_color(sentiment) if sentiment else ''
                    st.markdown(f"- **{name}** {icon} {sentiment}")
                    if evidence:
                        st.markdown(f'  > *"{evidence}"*')
            else:
                # Simple list of strings
                cols = st.columns(min(len(attrs), 3))
                for i, attr in enumerate(attrs):
                    with cols[i % 3]:
                        st.info(f"**{attr}**")
        st.markdown("---")

    # Purchase Drivers
    drivers = data.get('purchase_drivers', [])
    if drivers:
        st.markdown("#### Purchase Drivers")
        st.markdown("")
        for i, driver in enumerate(drivers):
            reason = driver.get('reason', 'Unknown')
            sentiment = driver.get('sentiment', 'neutral')
            strength = driver.get('strength', '')
            quote = driver.get('quote', '')

            icon = _sentiment_color(sentiment)
            header = f"**{i+1}. {reason}** {icon}"
            if strength:
                header += f" | Strength: _{strength}_"

            if sentiment == 'positive':
                st.success(header)
            elif sentiment == 'negative':
                st.warning(header)
            else:
                st.info(header)

            if quote:
                st.markdown(f'> *"{quote}"*')
            st.markdown("")

    if not attrs and not drivers:
        st.info("No brand attributes or purchase drivers identified.")


def _render_competitive(data: dict):
    """Render competitive context."""
    competitive = data.get('competitive_context', {})

    if isinstance(competitive, dict) and competitive:
        # Direct Comparisons
        comparisons = competitive.get('direct_comparisons', [])
        if comparisons:
            st.markdown("#### Direct Comparisons")
            for comp in comparisons:
                if isinstance(comp, str) and ':' in comp:
                    competitor, details = comp.split(':', 1)
                    st.markdown(f"**{competitor.strip()}**")
                    st.markdown(f"> {details.strip()}")
                else:
                    st.markdown(f"- {comp}")
                st.markdown("")

        # Market Positioning
        positioning = competitive.get('market_positioning', '')
        if positioning:
            st.markdown("#### Market Positioning")
            st.success(positioning)

        # Any other competitive fields
        other_keys = set(competitive.keys()) - {'direct_comparisons', 'market_positioning'}
        for key in sorted(other_keys):
            value = competitive[key]
            if value:
                st.markdown(f"#### {key.replace('_', ' ').title()}")
                if isinstance(value, list):
                    for item in value:
                        st.markdown(f"- {item}")
                else:
                    st.write(value)

    elif isinstance(competitive, str) and competitive:
        st.info(competitive)

    # Fallback: competitors_mentioned at root level
    elif 'competitors_mentioned' in data:
        st.markdown("#### Competitors Mentioned")
        for comp in data['competitors_mentioned']:
            st.markdown(f"- {comp}")

    else:
        st.info("No competitive context identified.")
