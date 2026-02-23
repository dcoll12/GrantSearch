"""
Instrumentl Grant Matcher — Web Interface
==========================================
Run entirely in the browser via Streamlit.
Deploy to Streamlit Community Cloud (share.streamlit.io) for free.
"""

import os
import io
import time
import tempfile
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from core import (
    InstrumentlAPI,
    DocumentProcessor,
    TextChunker,
    TFIDFMatcher,
    grant_matches_location,
    build_results_dataframe,
    load_config,
    save_config,
)

# ==============================================================================
# PAGE CONFIG
# ==============================================================================

st.set_page_config(
    page_title="Instrumentl Grant Matcher",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# SESSION STATE INIT
# ==============================================================================

defaults = {
    "api_connected": False,
    "api_client": None,
    "projects": [],
    "grants_data": [],
    "uploaded_docs": [],   # list of {"name": str, "text": str}
    "match_results": [],
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ==============================================================================
# SIDEBAR — API CREDENTIALS
# ==============================================================================

_saved_config = load_config()

with st.sidebar:
    st.title("⚙️ API Credentials")
    st.caption("Credentials are saved locally to config.json and never sent anywhere except the Instrumentl API.")

    api_key_id = st.text_input(
        "API Key ID",
        value=_saved_config.get("api_key_id", ""),
        type="password",
        placeholder="019c24d3-...",
        help="Found in your Instrumentl account settings",
    )
    api_private_key = st.text_input(
        "API Private Key",
        value=_saved_config.get("api_private_key", ""),
        type="password",
        placeholder="instr-apikey-...",
        help="Found in your Instrumentl account settings",
    )

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        connect_clicked = st.button("🔌 Connect", use_container_width=True, type="primary")
    with btn_col2:
        save_clicked = st.button("💾 Save", use_container_width=True)

    if save_clicked:
        if not api_key_id or not api_private_key:
            st.error("Enter both credentials before saving.")
        else:
            cfg = load_config()
            cfg["api_key_id"] = api_key_id
            cfg["api_private_key"] = api_private_key
            save_config(cfg)
            st.success("Saved!")

    if connect_clicked:
        if not api_key_id or not api_private_key:
            st.error("Please enter both API credentials.")
        else:
            with st.spinner("Testing connection..."):
                try:
                    client = InstrumentlAPI(api_key_id, api_private_key)
                    account = client.get_account()
                    if account:
                        st.session_state.api_client = client
                        st.session_state.api_connected = True
                        st.success("Connected!")
                    else:
                        st.error("Could not verify credentials.")
                except Exception as e:
                    st.error(str(e))

    st.divider()

    if st.session_state.api_connected:
        st.success("🟢 Connected to Instrumentl")
    else:
        st.warning("🔴 Not connected")

    st.divider()
    st.caption("**Session summary**")
    st.caption(f"Documents loaded: {len(st.session_state.uploaded_docs)}")
    st.caption(f"Grants fetched: {len(st.session_state.grants_data)}")
    st.caption(f"Match results: {len(st.session_state.match_results)}")

    if st.button("🔄 Reset Session", use_container_width=True):
        st.session_state.uploaded_docs = []
        st.session_state.grants_data = []
        st.session_state.match_results = []
        st.rerun()

# ==============================================================================
# MAIN HEADER
# ==============================================================================

st.title("📊 Instrumentl Grant Matcher")
st.caption("Match your organization's documents against grant opportunities — entirely in the browser.")
st.divider()

# ==============================================================================
# TABS
# ==============================================================================

tab_docs, tab_fetch, tab_match, tab_results = st.tabs([
    "📁 1. Upload Documents",
    "☁️ 2. Fetch Grants",
    "🔍 3. Run Matching",
    "📊 4. Results Dashboard",
])

# ------------------------------------------------------------------------------
# TAB 1 — UPLOAD DOCUMENTS
# ------------------------------------------------------------------------------

with tab_docs:
    st.header("Upload Your Documents")
    st.write("Upload PDFs, Word docs, Excel files, PowerPoints, CSVs, or plain text. "
             "The matcher reads the content and builds a profile of your organization.")

    uploaded_files = st.file_uploader(
        "Choose files",
        accept_multiple_files=True,
        type=["pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt", "csv", "txt", "md"],
    )

    if uploaded_files:
        st.caption(f"{len(uploaded_files)} file(s) selected:")
        for f in uploaded_files:
            st.markdown(f"- {f.name}")

    col1, col2 = st.columns([1, 3])
    with col1:
        chunk_size = st.number_input(
            "Chunk size (words)",
            min_value=100,
            max_value=2000,
            value=500,
            step=50,
            help="Larger chunks = more context per segment. 500 is a good default.",
        )

    if uploaded_files:
        if st.button("📂 Process Documents", type="primary"):
            docs = []
            progress = st.progress(0)
            status = st.empty()
            errors = []

            for i, uploaded_file in enumerate(uploaded_files):
                status.text(f"Processing: {uploaded_file.name}...")
                progress.progress((i) / len(uploaded_files))
                try:
                    suffix = os.path.splitext(uploaded_file.name)[1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_file.read())
                        tmp_path = tmp.name
                    text = DocumentProcessor.extract_text(tmp_path)
                    os.unlink(tmp_path)
                    if text.strip():
                        docs.append({"name": uploaded_file.name, "text": text})
                    else:
                        errors.append(f"{uploaded_file.name}: no text extracted")
                except Exception as e:
                    errors.append(f"{uploaded_file.name}: {e}")

            progress.progress(1.0)
            status.empty()
            st.session_state.uploaded_docs = docs

            if docs:
                st.success(f"✅ Processed {len(docs)} document(s) successfully.")
            for err in errors:
                st.warning(f"⚠️ {err}")

    if st.session_state.uploaded_docs:
        st.subheader("Loaded Documents")
        for doc in st.session_state.uploaded_docs:
            words = len(doc["text"].split())
            chunks = len(TextChunker.chunk_text(doc["text"], chunk_size=chunk_size))
            st.markdown(f"- **{doc['name']}** — {words:,} words → {chunks} chunks")

        if st.button("🗑️ Clear Documents"):
            st.session_state.uploaded_docs = []
            st.rerun()

        st.divider()
        st.info("✅ Documents ready. Click the **☁️ 2. Fetch Grants** tab above to continue.")

# ------------------------------------------------------------------------------
# TAB 2 — FETCH GRANTS
# ------------------------------------------------------------------------------

with tab_fetch:
    st.header("Fetch Grants from Instrumentl")

    if not st.session_state.api_connected:
        st.warning("Connect your API credentials in the sidebar first.")
    else:
        # Project selector
        st.subheader("Project (optional)")
        col1, col2 = st.columns([3, 1])
        with col1:
            project_options = ["-- All Projects --"] + [
                p.get("project_title") or f"Project {p.get('id', 'Unknown')}"
                for p in st.session_state.projects
            ]
            selected_project_label = st.selectbox("Select a project", project_options)

        with col2:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh Projects"):
                with st.spinner("Loading projects..."):
                    try:
                        projects = st.session_state.api_client.get_all_projects()
                        st.session_state.projects = projects
                        st.success(f"Loaded {len(projects)} projects")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        # Resolve selected project ID
        selected_project_id = None
        if selected_project_label != "-- All Projects --":
            for p in st.session_state.projects:
                label = p.get("project_title") or f"Project {p.get('id', 'Unknown')}"
                if label == selected_project_label:
                    selected_project_id = p.get("id")
                    break

        st.divider()

        # Fetch options
        st.subheader("Fetch Options")
        col1, col2 = st.columns(2)
        with col1:
            fetch_saved = st.checkbox("Fetch Saved Grants", value=True,
                                      help="Grants you've already saved to projects in Instrumentl")
            fetch_matches = st.checkbox("Fetch Grant Matches (first page)", value=True,
                                        help="First page of Instrumentl's grant recommendations for the selected project (fast — fetches up to 50 grants)")
            fetch_all = st.checkbox("Fetch All Available Grants", value=False,
                                    help="Discover new grant opportunities — fetches every grant in the database (slow)")
        with col2:
            location_filter = st.radio(
                "Geographic Filter",
                options=["all", "indiana", "usa", "indiana_usa"],
                format_func=lambda x: {
                    "all": "All locations",
                    "indiana": "Indiana only",
                    "usa": "USA (nationwide)",
                    "indiana_usa": "Indiana + USA nationwide",
                }[x],
            )

        st.caption("Location filtering is applied after fetching based on each grant's geographic restrictions.")

        st.divider()

        if st.button("⬇️ Fetch Grants", type="primary", use_container_width=True):
            if not fetch_saved and not fetch_matches and not fetch_all:
                st.error("Select at least one fetch option.")
            else:
                all_grants = []
                status_box = st.status("Fetching grants...", expanded=True)
                try:
                    client = st.session_state.api_client

                    if fetch_saved:
                        status_box.write("Fetching saved grants...")
                        saved = client.get_all_saved_grants(
                            project_id=selected_project_id,
                            callback=lambda msg: status_box.write(msg),
                        )
                        for s in saved:
                            grant_id = s.get("grant_id")
                            if grant_id:
                                try:
                                    detail = client.get_grant(grant_id)
                                    if detail:
                                        detail["_saved_grant_info"] = s
                                        all_grants.append(detail)
                                    time.sleep(0.2)
                                except Exception:
                                    pass

                    if fetch_matches:
                        project_label = selected_project_label if selected_project_id else "all projects"
                        status_box.write(f"Fetching grant matches (first page) for {project_label}...")
                        matched = client.get_grants_first_page(project_id=selected_project_id)
                        existing_ids = {g.get("id") for g in all_grants}
                        new_matches = [g for g in matched if g.get("id") not in existing_ids]
                        for idx, g in enumerate(new_matches, 1):
                            grant_id = g.get("id")
                            if grant_id:
                                try:
                                    status_box.write(f"Fetching match details {idx}/{len(new_matches)}...")
                                    detail = client.get_grant(grant_id)
                                    if detail:
                                        all_grants.append(detail)
                                    time.sleep(0.2)
                                except Exception:
                                    all_grants.append(g)

                    if fetch_all:
                        status_box.write("Fetching all available grants...")
                        grants = client.get_all_grants(callback=lambda msg: status_box.write(msg))
                        existing_ids = {g.get("id") for g in all_grants}
                        to_fetch = [g for g in grants if g.get("id") not in existing_ids]
                        total = len(to_fetch)
                        for idx, g in enumerate(to_fetch, 1):
                            grant_id = g.get("id")
                            if grant_id:
                                try:
                                    status_box.write(f"Fetching grant details {idx}/{total}...")
                                    detail = client.get_grant(grant_id)
                                    if detail:
                                        all_grants.append(detail)
                                    time.sleep(0.2)
                                except Exception:
                                    all_grants.append(g)

                    if location_filter != "all":
                        status_box.write("Applying location filter...")
                        all_grants = [g for g in all_grants if grant_matches_location(g, location_filter)]

                    st.session_state.grants_data = all_grants
                    status_box.update(label=f"✅ Fetched {len(all_grants)} grants", state="complete")

                except Exception as e:
                    status_box.update(label="Error fetching grants", state="error")
                    st.error(str(e))

        if st.session_state.grants_data:
            st.success(f"📦 {len(st.session_state.grants_data)} grants ready for matching.")
            if st.button("🗑️ Clear Grants"):
                st.session_state.grants_data = []
                st.rerun()

            st.divider()
            st.info("✅ Grants fetched. Click the **🔍 3. Run Matching** tab above to continue.")

# ------------------------------------------------------------------------------
# TAB 3 — RUN MATCHING
# ------------------------------------------------------------------------------

with tab_match:
    st.header("Run Matching")

    ready = st.session_state.uploaded_docs and st.session_state.grants_data
    if not st.session_state.uploaded_docs:
        st.warning("Upload and process documents in Tab 1 first.")
    if not st.session_state.grants_data:
        st.warning("Fetch grants in Tab 2 first.")

    if ready:
        col1, col2, col3 = st.columns(3)
        with col1:
            chunk_size_match = st.number_input(
                "Chunk size (words)", min_value=100, max_value=2000, value=500, step=50
            )
        with col2:
            min_score = st.number_input(
                "Min match score", min_value=0.0, max_value=1.0, value=0.01,
                step=0.01, format="%.3f",
                help="Scores above this threshold are included. Lower = more results.",
            )
        with col3:
            top_matches = st.number_input(
                "Max results (0 = all)", min_value=0, max_value=5000, value=100, step=10,
                help="Maximum number of top grants to return. Set to 0 to return all above min score.",
            )

        st.caption(
            "**Score guide:** 0.10–0.50 = very strong · 0.05–0.10 = good · "
            "0.02–0.05 = moderate · 0.01–0.02 = weak · <0.01 = very weak"
        )

        if st.button("🚀 Run Matching", type="primary", use_container_width=True):
            with st.status("Running matching algorithm...", expanded=True) as status:
                try:
                    # Build combined document text
                    st.write("Processing documents into chunks...")
                    doc_chunks = []
                    for doc in st.session_state.uploaded_docs:
                        chunks = TextChunker.chunk_text(doc["text"], chunk_size=int(chunk_size_match))
                        doc_chunks.extend(chunks)

                    if not doc_chunks:
                        st.error("No text could be extracted from documents.")
                        st.stop()

                    combined_text = " ".join(doc_chunks)

                    # Build grant index
                    st.write(f"Building index for {len(st.session_state.grants_data)} grants...")
                    matcher = TFIDFMatcher()
                    grant_texts = []
                    grant_metas = []
                    for grant in st.session_state.grants_data:
                        parts = [grant.get("name", ""), grant.get("overview", "")]
                        funder = grant.get("funder", "")
                        parts.append(funder.get("name", "") if isinstance(funder, dict) else str(funder))
                        categories = grant.get("categories", {})
                        if isinstance(categories, dict):
                            for cat_vals in categories.values():
                                if isinstance(cat_vals, list):
                                    parts.extend(cat_vals)
                        grant_text = " ".join(str(p) for p in parts if p)
                        if grant_text.strip():
                            grant_texts.append(grant_text)
                            grant_metas.append(grant)

                    matcher.add_documents(grant_texts, grant_metas)
                    matcher.build_index()

                    # Find matches
                    st.write("Finding matches...")
                    actual_top_k = int(top_matches) if top_matches > 0 else len(grant_metas)
                    matches = matcher.find_matches(combined_text, top_k=actual_top_k, min_score=float(min_score))

                    st.session_state.match_results = matches
                    status.update(label=f"✅ Found {len(matches)} matches", state="complete")

                except Exception as e:
                    status.update(label="Error during matching", state="error")
                    st.error(str(e))

    if st.session_state.match_results:
        st.success(f"✅ {len(st.session_state.match_results)} results ready.")
        st.info("Click the **📊 4. Results Dashboard** tab above to view your matches.")

# ------------------------------------------------------------------------------
# TAB 4 — RESULTS DASHBOARD
# ------------------------------------------------------------------------------

with tab_results:
    st.header("Results Dashboard")

    if not st.session_state.match_results:
        st.info("No results yet. Run matching in Tab 3 to see your dashboard.")
    else:
        df = build_results_dataframe(st.session_state.match_results)

        # ── Summary metrics ───────────────────────────────────────────────────
        st.subheader("Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Matches", len(df))
        m2.metric("Top Score", f"{df['Score'].max():.4f}")
        m3.metric("Avg Score", f"{df['Score'].mean():.4f}")
        upcoming = df[df["Next Deadline"].notna() & (df["Next Deadline"] != "")]
        m4.metric("With Upcoming Deadlines", len(upcoming))

        st.divider()

        # ── Filters ───────────────────────────────────────────────────────────
        st.subheader("Filter & Search")
        col1, col2, col3 = st.columns(3)
        with col1:
            search_term = st.text_input("Search grant name or funder", "")
        with col2:
            score_min = st.slider(
                "Minimum score",
                min_value=float(df["Score"].min()),
                max_value=float(df["Score"].max()),
                value=float(df["Score"].min()),
                step=0.001,
                format="%.3f",
            )
        with col3:
            funders = ["All"] + sorted(df["Funder"].dropna().unique().tolist())
            funder_filter = st.selectbox("Funder", funders)

        filtered = df[df["Score"] >= score_min]
        if search_term:
            mask = (
                filtered["Grant Name"].str.contains(search_term, case=False, na=False) |
                filtered["Funder"].str.contains(search_term, case=False, na=False)
            )
            filtered = filtered[mask]
        if funder_filter != "All":
            filtered = filtered[filtered["Funder"] == funder_filter]

        st.caption(f"Showing {len(filtered)} of {len(df)} results")

        st.divider()

        # ── Results table ─────────────────────────────────────────────────────
        st.subheader("Grant Matches")

        display_df = filtered.copy()

        st.dataframe(
            display_df[[
                "Rank", "Score", "Grant Name", "Funder",
                "Next Deadline", "Status", "Funding Cycle", "Grant URL", "Description"
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Rank": st.column_config.NumberColumn(width="small"),
                "Score": st.column_config.NumberColumn(format="%.4f", width="small"),
                "Grant Name": st.column_config.TextColumn(width="large"),
                "Funder": st.column_config.TextColumn(width="medium"),
                "Next Deadline": st.column_config.TextColumn(width="medium"),
                "Status": st.column_config.TextColumn(width="small"),
                "Funding Cycle": st.column_config.TextColumn(width="small"),
                "Grant URL": st.column_config.LinkColumn("Link", width="small", display_text="Open ↗"),
                "Description": st.column_config.TextColumn(width="large"),
            },
        )

        st.divider()

        # ── Charts ────────────────────────────────────────────────────────────
        st.subheader("Visualizations")
        chart1, chart2 = st.columns(2)

        with chart1:
            fig_hist = px.histogram(
                filtered,
                x="Score",
                nbins=30,
                title="Match Score Distribution",
                color_discrete_sequence=["#6366f1"],
                labels={"Score": "Match Score", "count": "Number of Grants"},
            )
            fig_hist.update_layout(showlegend=False, margin=dict(t=40, b=0))
            st.plotly_chart(fig_hist, use_container_width=True)

        with chart2:
            top_funders = (
                filtered["Funder"]
                .dropna()
                .value_counts()
                .head(10)
                .reset_index()
            )
            top_funders.columns = ["Funder", "Count"]
            fig_funders = px.bar(
                top_funders,
                x="Count",
                y="Funder",
                orientation="h",
                title="Top 10 Funders in Results",
                color_discrete_sequence=["#6366f1"],
            )
            fig_funders.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(t=40, b=0))
            st.plotly_chart(fig_funders, use_container_width=True)

        # Deadline timeline (only if deadline data exists)
        deadline_df = filtered[filtered["Next Deadline"].notna() & (filtered["Next Deadline"] != "")].copy()
        if not deadline_df.empty:
            try:
                deadline_df["Deadline Date"] = pd.to_datetime(deadline_df["Next Deadline"], errors="coerce")
                deadline_df = deadline_df.dropna(subset=["Deadline Date"]).sort_values("Deadline Date")
                if not deadline_df.empty:
                    st.subheader("Upcoming Deadlines")
                    fig_timeline = px.scatter(
                        deadline_df.head(30),
                        x="Deadline Date",
                        y="Score",
                        hover_name="Grant Name",
                        hover_data={"Funder": True, "Score": ":.4f"},
                        color="Score",
                        color_continuous_scale="Viridis",
                        title="Top 30 Grants by Deadline (bubble = match score)",
                        size="Score",
                        size_max=20,
                    )
                    fig_timeline.update_layout(margin=dict(t=40, b=0))
                    st.plotly_chart(fig_timeline, use_container_width=True)
            except Exception:
                pass

        st.divider()

        # ── Export ────────────────────────────────────────────────────────────
        st.subheader("Export Results")
        dl1, dl2 = st.columns(2)

        with dl1:
            csv_data = filtered.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_data,
                file_name=f"grant_matches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with dl2:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                filtered.to_excel(writer, index=False, sheet_name="Grant Matches")
            st.download_button(
                label="⬇️ Download Excel",
                data=buffer.getvalue(),
                file_name=f"grant_matches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
