"""
Strategic Intelligence Dashboard - Zero-query initial load.
All database queries are deferred until the user searches.
"""
import io
import json
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def display_strategic_intelligence_tab(search_clips, fetch_detail):
    """
    Display the Strategic Intelligence tab. No database queries run
    until the user types a search or clicks Search.
    """
    # ── Header ──────────────────────────────────────────────────────────
    st.markdown(
        '<h2 style="margin-bottom: 0.2rem;">Strategic Intelligence Dashboard</h2>'
        '<p style="color: #6c757d; margin-top: 0; margin-bottom: 1rem;">'
        'Search and explore enhanced sentiment analysis across all reviewed clips</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Search Bar ──────────────────────────────────────────────────────
    s1, s2, s3, s4 = st.columns([3, 1.5, 1.5, 1])

    with s1:
        search_text = st.text_input(
            "Search WO#, Contact, or Media Outlet",
            placeholder="e.g. 1261373, Motor Trend, John Smith",
            key="si_search",
        )

    with s2:
        make_input = st.text_input(
            "Filter by Make",
            placeholder="e.g. Volvo, Ford",
            key="si_make",
        )

    with s3:
        selected_sentiment = st.selectbox(
            "Sentiment",
            ["All", "positive", "neutral", "negative"],
            key="si_sentiment",
        )

    with s4:
        st.markdown("<br>", unsafe_allow_html=True)
        search_clicked = st.button("Search", type="primary", key="si_go")

    # ── Only query when user has provided input ─────────────────────────
    make_filter = make_input.strip() if make_input else ''
    sentiment_filter = selected_sentiment if selected_sentiment != "All" else ''
    has_input = search_text or make_filter or sentiment_filter

    if search_clicked and has_input:
        st.session_state['si_last_search'] = (make_filter, sentiment_filter, search_text.strip())

    last_search = st.session_state.get('si_last_search')

    if not last_search:
        st.markdown("")
        st.info(
            "Enter a **WO number**, **contact name**, or **media outlet** above and click **Search** "
            "to find clips with enhanced sentiment analysis.  \n"
            "You can also filter by **Make** (e.g. Volvo) or **Sentiment**."
        )
        return

    # ── Run the search ──────────────────────────────────────────────────
    mf, sf, st_text = last_search

    with st.spinner("Searching..."):
        results = search_clips(mf, sf, st_text)

    if not results:
        st.warning("No clips match your search. Try different terms.")
        return

    # ── Build DataFrame ─────────────────────────────────────────────────
    df = pd.DataFrame(results)
    df['published_date'] = pd.to_datetime(df['published_date'], errors='coerce')

    # ── Summary Metrics (only when enough results to be useful) ─────────
    if len(df) > 3:
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

    # ── Results Table ───────────────────────────────────────────────────
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

    # Dynamic height: 42px per row + 95px for header/pagination, capped at 300px, min 150px
    grid_height = max(min(len(display_df) * 42 + 95, 300), 150)

    st.markdown("**Select a clip to view detailed analysis:**")
    grid_response = AgGrid(
        display_df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=grid_height,
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

    if hasattr(selected_rows, 'iloc'):
        sel = selected_rows.iloc[0].to_dict()
    else:
        sel = selected_rows[0]

    selected_wo = sel.get('WO #', '')
    clip_record = next((c for c in results if c.get('wo_number') == selected_wo), None)
    if not clip_record:
        st.error(f"Could not locate clip data for WO {selected_wo}")
        return

    with st.spinner(f"Loading analysis for WO {selected_wo}..."):
        detail = fetch_detail(clip_record['id'])

    raw_data = detail.get('sentiment_data_enhanced') if detail else None
    if not raw_data:
        st.warning("No enhanced sentiment data available for this clip.")
        return

    enhanced = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    _render_analysis(clip_record, enhanced, selected_wo)


# ═══════════════════════════════════════════════════════════════════════════
# Analysis rendering
# ═══════════════════════════════════════════════════════════════════════════

def _render_analysis(clip: dict, data: dict, wo_number: str):
    """Render the complete analysis view for a selected clip."""
    st.markdown("---")

    # ── Clip Info Header ────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"**Media Contact**  \n{clip.get('contact') or 'Unknown'}")
    with c2:
        st.markdown(f"**Publication**  \n{clip.get('media_outlet') or 'N/A'}")
    with c3:
        st.markdown(f"**Vehicle**  \n{clip.get('make', '')} {clip.get('model', '')}")
    with c4:
        st.markdown(f"**Date**  \n{clip.get('published_date') or 'N/A'}")

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
    a1, a2, _ = st.columns([1.5, 1, 3.5])
    with a1:
        pdf_bytes = _generate_pdf(clip, data)
        st.download_button(
            "Download PDF Report",
            pdf_bytes,
            file_name=f"SI_Report_{wo_number}.pdf",
            mime="application/pdf",
            key="si_pdf_download",
        )
    with a2:
        url = clip.get('clip_url')
        if url:
            st.link_button("View Original Clip", url)

    # Bottom padding
    st.markdown("<br><br>", unsafe_allow_html=True)


def _render_scores(data: dict):
    scores = [
        ('overall_score', 'Overall Score'),
        ('relevance_score', 'Relevance'),
        ('marketing_impact_score', 'Marketing Impact'),
        ('brand_alignment', 'Brand Alignment'),
    ]
    if not any(k in data for k, _ in scores):
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
    s = str(sentiment).lower()
    if 'positive' in s:
        return '🟢'
    if 'negative' in s:
        return '🔴'
    return '🟡'


def _render_overview(data: dict):
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
                st.markdown("**Rationale**")
                st.markdown(f"> {rationale}")

    if data.get('recommendation'):
        st.markdown("")
        st.warning(f"**Recommendation:** {data['recommendation']}")

    pros = data.get('pros', [])
    cons = data.get('cons', [])
    if pros or cons:
        st.markdown("---")
        st.markdown("#### Pros & Cons")
        pc1, pc2 = st.columns(2)
        with pc1:
            for p in (pros or []):
                st.success(f"{p}")
            if not pros:
                st.caption("No pros identified")
        with pc2:
            for c in (cons or []):
                st.warning(f"{c}")
            if not cons:
                st.caption("No cons identified")


def _render_features(data: dict):
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
    attrs = data.get('brand_attributes_identified', data.get('brand_attributes_captured', []))
    if attrs:
        st.markdown("#### Brand Attributes")
        if isinstance(attrs, list) and attrs:
            if isinstance(attrs[0], dict):
                for attr in attrs:
                    name = attr.get('attribute', str(attr))
                    sentiment = attr.get('sentiment', '')
                    evidence = attr.get('evidence', '')
                    icon = _sentiment_color(sentiment) if sentiment else ''
                    st.markdown(f"- **{name}** {icon} {sentiment}")
                    if evidence:
                        st.markdown(f'  > *"{evidence}"*')
            else:
                cols = st.columns(min(len(attrs), 3))
                for i, attr in enumerate(attrs):
                    with cols[i % 3]:
                        st.info(f"**{attr}**")
        st.markdown("---")

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
    competitive = data.get('competitive_context', {})

    if isinstance(competitive, dict) and competitive:
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

        positioning = competitive.get('market_positioning', '')
        if positioning:
            st.markdown("#### Market Positioning")
            st.success(positioning)

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

    elif 'competitors_mentioned' in data:
        st.markdown("#### Competitors Mentioned")
        for comp in data['competitors_mentioned']:
            st.markdown(f"- {comp}")

    else:
        st.info("No competitive context identified.")


# ═══════════════════════════════════════════════════════════════════════════
# PDF Generation
# ═══════════════════════════════════════════════════════════════════════════

def _generate_pdf(clip: dict, data: dict) -> bytes:
    """Generate a professional PDF summary of the sentiment analysis."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── Title ───────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(25, 118, 210)  # #1976d2
    pdf.cell(0, 12, "Strategic Intelligence Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(25, 118, 210)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # ── Clip Info ───────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)

    vehicle = f"{clip.get('make', '')} {clip.get('model', '')}".strip()
    info_rows = [
        ("Work Order", clip.get('wo_number', 'N/A')),
        ("Vehicle", vehicle or 'N/A'),
        ("Media Contact", clip.get('contact') or 'N/A'),
        ("Publication", clip.get('media_outlet') or 'N/A'),
        ("Published Date", str(clip.get('published_date') or 'N/A')),
    ]

    pdf.set_fill_color(240, 245, 250)
    for i, (label, value) in enumerate(info_rows):
        fill = i % 2 == 0
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 7, label, fill=fill)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, str(value), new_x="LMARGIN", new_y="NEXT", fill=fill)

    pdf.ln(4)

    # ── Executive Summary ───────────────────────────────────────────────
    summary = data.get('summary', '')
    if summary:
        _pdf_section_header(pdf, "Executive Summary")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _clean_text(summary))
        pdf.ln(4)

    # ── Sentiment Classification ────────────────────────────────────────
    sent = data.get('sentiment_classification', {})
    if sent:
        _pdf_section_header(pdf, "Sentiment Classification")
        pdf.set_font("Helvetica", "", 10)
        overall = sent.get('overall', 'N/A')
        confidence = sent.get('confidence', 'N/A')
        if isinstance(confidence, (float, int)):
            confidence = f"{confidence:.0%}"
        pdf.cell(0, 6, f"Overall: {overall}    |    Confidence: {confidence}", new_x="LMARGIN", new_y="NEXT")

        rationale = sent.get('rationale', '')
        if rationale:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(0, 5, _clean_text(rationale))
            pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    # ── Scores ──────────────────────────────────────────────────────────
    score_items = []
    for key, label in [('relevance_score', 'Relevance'), ('overall_score', 'Overall Score'),
                        ('marketing_impact_score', 'Marketing Impact'), ('brand_alignment', 'Brand Alignment')]:
        val = data.get(key)
        if val is not None:
            display_val = "Yes" if isinstance(val, bool) and val else ("No" if isinstance(val, bool) else f"{val}/10")
            score_items.append(f"{label}: {display_val}")

    if score_items:
        _pdf_section_header(pdf, "Scores")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "    |    ".join(score_items), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # ── Key Features ────────────────────────────────────────────────────
    features = data.get('key_features_mentioned', [])
    if features:
        _pdf_section_header(pdf, f"Key Features ({len(features)})")
        for feat in features:
            name = feat.get('feature', 'Unknown')
            sentiment = feat.get('sentiment', 'neutral')
            quote = feat.get('quote', '')

            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, f"  {name} ({sentiment})", new_x="LMARGIN", new_y="NEXT")
            if quote:
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(5)  # indent
                pdf.multi_cell(0, 5, _clean_text(f'"{quote}"'))
                pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    # ── Brand Attributes ────────────────────────────────────────────────
    attrs = data.get('brand_attributes_identified', data.get('brand_attributes_captured', []))
    if attrs:
        _pdf_section_header(pdf, "Brand Attributes")
        pdf.set_font("Helvetica", "", 10)
        for attr in attrs:
            if isinstance(attr, dict):
                name = attr.get('attribute', str(attr))
                sentiment = attr.get('sentiment', '')
                pdf.cell(0, 6, f"  {name} ({sentiment})" if sentiment else f"  {name}", new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.cell(0, 6, f"  {attr}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # ── Purchase Drivers ────────────────────────────────────────────────
    drivers = data.get('purchase_drivers', [])
    if drivers:
        _pdf_section_header(pdf, f"Purchase Drivers ({len(drivers)})")
        for driver in drivers:
            reason = driver.get('reason', 'Unknown')
            sentiment = driver.get('sentiment', 'neutral')
            strength = driver.get('strength', '')
            quote = driver.get('quote', '')

            pdf.set_font("Helvetica", "B", 10)
            label = f"  {reason} ({sentiment})"
            if strength:
                label += f" - {strength}"
            pdf.cell(0, 6, label, new_x="LMARGIN", new_y="NEXT")
            if quote:
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(5)
                pdf.multi_cell(0, 5, _clean_text(f'"{quote}"'))
                pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    # ── Competitive Context ─────────────────────────────────────────────
    competitive = data.get('competitive_context', {})
    if isinstance(competitive, dict) and competitive:
        _pdf_section_header(pdf, "Competitive Context")
        pdf.set_font("Helvetica", "", 10)

        comparisons = competitive.get('direct_comparisons', [])
        if comparisons:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Direct Comparisons:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            for comp in comparisons:
                pdf.cell(5)
                pdf.multi_cell(0, 5, _clean_text(f"  {comp}"))

        positioning = competitive.get('market_positioning', '')
        if positioning:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Market Positioning:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, _clean_text(positioning))

    # ── Footer ──────────────────────────────────────────────────────────
    pdf.ln(8)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "Generated by DriveShop Strategic Intelligence Dashboard", align="C")

    return pdf.output()


def _pdf_section_header(pdf, title: str):
    """Render a styled section header in the PDF."""
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(25, 118, 210)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)


def _clean_text(text: str) -> str:
    """Clean text for PDF output — remove characters that fpdf can't render."""
    if not text:
        return ''
    # Replace common unicode characters with ASCII equivalents
    replacements = {
        '\u2018': "'", '\u2019': "'",  # smart single quotes
        '\u201c': '"', '\u201d': '"',  # smart double quotes
        '\u2013': '-', '\u2014': '--',  # en/em dash
        '\u2026': '...',  # ellipsis
        '\u00a0': ' ',  # non-breaking space
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    # Remove any remaining non-latin1 characters
    return text.encode('latin-1', errors='replace').decode('latin-1')
