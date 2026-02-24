"""
Instrumentl Grant Matcher — Web Interface
==========================================
Run entirely in the browser via Streamlit.
Deploy to Streamlit Community Cloud (share.streamlit.io) for free.
"""

import os
import io
import sys
import json
import time
import platform
import subprocess
import tempfile
import streamlit as st
import streamlit.components.v1 as components
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
    "navigate_to_tab": None,
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

_PROJECTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instrumentl_projects.json")


def _load_projects() -> dict:
    """Load saved projects dict {name: project_id} from disk."""
    if os.path.exists(_PROJECTS_FILE):
        try:
            with open(_PROJECTS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_projects(projects: dict):
    with open(_PROJECTS_FILE, "w") as f:
        json.dump(projects, f, indent=2)


def _launch_auto_save(project_id: str | None = None):
    """Launch instrumentl_auto_save.py in a new terminal window."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instrumentl_auto_save.py")
    py = sys.executable
    extra = ["--project-id", str(project_id)] if project_id else []
    system = platform.system()
    try:
        if system == "Windows":
            cmd = " ".join([py, script] + extra)
            subprocess.Popen(["start", "cmd", "/k", cmd], shell=True)
        elif system == "Darwin":
            cmd_str = " ".join([py, script] + extra)
            apple = f'tell application "Terminal" to do script "{cmd_str}"'
            subprocess.Popen(["osascript", "-e", apple])
        else:
            base = [py, script] + extra
            terminals = [
                ["gnome-terminal", "--"] + base,
                ["x-terminal-emulator", "-e", " ".join(base)],
                ["xterm", "-e", " ".join(base)],
                ["konsole", "-e"] + base,
                ["xfce4-terminal", "-e", " ".join(base)],
            ]
            launched = False
            for cmd in terminals:
                try:
                    subprocess.Popen(cmd)
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            if not launched:
                return False, "No terminal emulator found. Run manually: python instrumentl_auto_save.py"
        return True, None
    except Exception as exc:
        return False, str(exc)


with tab_docs:
    st.header("Upload Your Documents")

    # ── Auto-Save Launcher ────────────────────────────────────────────────────
    with st.expander("🤖 Auto-Save Instrumentl Matches", expanded=False):
        st.write(
            "Before fetching grants, use the auto-save script to save Instrumentl's "
            "recommended matches to your project. The script opens a Firefox browser, "
            "lets you log in, then automatically clicks **Save** on every match "
            "(4 – 11.5 s random delay between saves)."
        )
        st.caption("Requires Firefox and the `selenium` / `webdriver-manager` packages.")

        # ── Project list management ──────────────────────────────────────────
        if "as_projects" not in st.session_state:
            st.session_state.as_projects = _load_projects()

        projects = st.session_state.as_projects
        project_names = list(projects.keys())

        col_sel, col_manage = st.columns([3, 2])
        with col_sel:
            selected_name = st.selectbox(
                "Select project",
                options=project_names if project_names else ["— no projects saved yet —"],
                disabled=not project_names,
                key="as_selected_project",
            )
        selected_id = projects.get(selected_name) if project_names else None

        with col_manage:
            st.write("")  # vertical spacer
            if st.button("▶ Launch Auto-Save", type="primary", disabled=not project_names):
                ok, err = _launch_auto_save(project_id=selected_id)
                if ok:
                    st.success(
                        f"Launched for project **{selected_name}** (ID: {selected_id}). "
                        "Log in when the browser opens."
                    )
                else:
                    st.error(f"Could not open terminal: {err}")
                    st.code(
                        f"python instrumentl_auto_save.py --project-id {selected_id}",
                        language="bash",
                    )

        # ── Add / remove projects ────────────────────────────────────────────
        with st.expander("Manage projects"):
            st.markdown("**Add a project** — find the ID in the Instrumentl URL: `…/projects/326636`")
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                new_name = st.text_input("Project name", key="as_new_name", label_visibility="collapsed",
                                         placeholder="e.g. Housing Initiative 2025")
            with c2:
                new_id = st.text_input("Project ID", key="as_new_id", label_visibility="collapsed",
                                       placeholder="e.g. 326636")
            with c3:
                if st.button("Add", key="as_add_btn"):
                    if new_name.strip() and new_id.strip():
                        projects[new_name.strip()] = new_id.strip()
                        _save_projects(projects)
                        st.session_state.as_projects = projects
                        st.rerun()
                    else:
                        st.warning("Enter both a name and an ID.")

            if project_names:
                st.markdown("**Remove a project**")
                to_remove = st.selectbox("Select to remove", project_names, key="as_remove_sel")
                if st.button("Remove", key="as_remove_btn"):
                    projects.pop(to_remove, None)
                    _save_projects(projects)
                    st.session_state.as_projects = projects
                    st.rerun()

    # ── Bookmarklet ───────────────────────────────────────────────────────────
    _BOOKMARKLET_JS = (
        "javascript:(function(){if(window.__iasRunning){window.__iasRunning=false;return;}"
        "window.__iasRunning=true;var MIN=4000,MAX=11500,saved=0;"
        "var box=document.createElement('div');"
        "box.style.cssText='position:fixed;top:12px;right:12px;z-index:2147483647;"
        "background:#1e293b;color:#f8fafc;padding:14px 18px;border-radius:10px;"
        "font:13px/1.6 system-ui,sans-serif;box-shadow:0 4px 20px rgba(0,0,0,.45);"
        "min-width:230px;max-width:300px';"
        r"box.innerHTML='<b style=\"font-size:14px\">🤖 Instrumentl Auto-Save<\/b>"
        r"<div id=\"__ias_msg\" style=\"margin:6px 0 10px;color:#94a3b8\">Starting\u2026<\/div>"
        r"<button id=\"__ias_stop\" style=\"background:#ef4444;border:0;color:#fff;"
        r"padding:5px 14px;border-radius:6px;cursor:pointer;font-size:12px\">\u23f9 Stop<\/button>';"
        "document.body.appendChild(box);"
        "var msgEl=document.getElementById('__ias_msg');"
        "function setMsg(s){msgEl.textContent=s;}"
        "document.getElementById('__ias_stop').onclick=function(){"
        "window.__iasRunning=false;setMsg('Stopped. Saved '+saved+' grant(s).');"
        "setTimeout(function(){box.remove();},3000);};"
        "function waitForBtn(t){return new Promise(function(res,rej){"
        "var d=Date.now()+t,i=setInterval(function(){"
        "var e=document.querySelector('.save-button-container > .btn');"
        "if(e&&e.offsetParent!==null){clearInterval(i);res(e);}"
        "else if(Date.now()>d){clearInterval(i);rej(new Error('timeout'));}},600);});}"
        "function countdownDelay(ms){return new Promise(function(resolve){"
        "var end=Date.now()+ms,t=setInterval(function(){"
        "if(!window.__iasRunning){clearInterval(t);resolve();return;}"
        "var s=Math.ceil((end-Date.now())/1000);"
        "if(s<=0){clearInterval(t);resolve();}"
        r"else setMsg('Saved '+saved+'. Next in '+s+'s\u2026');},1000);});}"
        "(async function loop(){while(window.__iasRunning){try{"
        r"setMsg('Waiting for Save button\u2026');"
        "var el=await waitForBtn(20000);"
        "if(!window.__iasRunning)break;"
        "saved++;setMsg('Clicking Save #'+saved+'\u2026');"
        "el.scrollIntoView({behavior:'smooth',block:'center'});"
        "await new Promise(function(r){setTimeout(r,400);});"
        "el.click();"
        "await countdownDelay(Math.random()*(MAX-MIN)+MIN);"
        "}catch(e){setMsg('Done! Saved '+saved+' grant(s).');"
        "window.__iasRunning=false;"
        "setTimeout(function(){box.remove();},6000);break;}}})();})()"
    )

    with st.expander("🔖 Browser Bookmarklet — no install required", expanded=False):
        st.write(
            "Works in **any modern browser** (Chrome, Firefox, Edge, Safari). "
            "No Python, Selenium, or drivers needed — just save it as a bookmark."
        )

        st.subheader("Option A — Drag to install")
        components.html(
            f"""
            <div style="font-family:system-ui,sans-serif;padding:8px 0;">
              <p style="margin:0 0 12px;color:#475569;font-size:13px;">
                Drag the button below to your browser's <b>Bookmarks Bar</b>.<br>
                <span style="font-size:12px;">(Chrome/Edge: Ctrl+Shift+B &nbsp;|&nbsp;
                Firefox: View → Toolbars → Bookmarks Toolbar)</span>
              </p>
              <a href="{_BOOKMARKLET_JS}"
                 style="display:inline-block;background:#6366f1;color:#fff;
                        padding:11px 26px;border-radius:8px;text-decoration:none;
                        font-weight:700;font-size:14px;cursor:grab;
                        box-shadow:0 2px 8px rgba(99,102,241,.35);"
                 title="Drag me to your bookmarks bar">
                🤖 Instrumentl Auto-Save
              </a>
            </div>
            """,
            height=90,
        )

        st.subheader("Option B — Copy & paste")
        st.write(
            "Create a new bookmark, give it any name, then paste the code below "
            "as the **URL / Address**."
        )
        st.code(_BOOKMARKLET_JS, language=None)

        st.subheader("How to use")
        st.markdown(
            "1. Log in to Instrumentl and open your project's **Matches** tab.\n"
            "2. Click the **🤖 Instrumentl Auto-Save** bookmark.\n"
            "3. A status badge appears in the top-right corner of the page.\n"
            "4. The script clicks Save on each grant and waits **4–11.5 seconds** "
            "(random) before the next one.\n"
            "5. Click **⏹ Stop** at any time, or click the bookmark again to stop.\n"
            "6. The script stops automatically when there are no more Save buttons."
        )

    st.divider()

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
        st.success("✅ Documents ready.")
        if st.button("☁️ Go to Fetch Grants →", type="primary", use_container_width=True):
            st.session_state.navigate_to_tab = 1
            st.rerun()

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
        if not st.session_state.projects:
            st.info("Click **🔄 Refresh Projects** to load your active projects from Instrumentl.")
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
        st.caption("💡 To include Instrumentl's recommended matches, use the auto-save script to save them to your project first — they will then appear here.")

        st.divider()

        if st.button("⬇️ Fetch Grants", type="primary", use_container_width=True):
            if not fetch_saved:
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

# ---------------------------------------------------------------------------
# PROGRAMMATIC TAB NAVIGATION
# ---------------------------------------------------------------------------
# If a navigate_to_tab index was set (e.g. by the "Go to Fetch Grants" button
# on the upload tab), inject a tiny script that clicks the target tab header.
_nav_tab = st.session_state.get("navigate_to_tab")
if _nav_tab is not None:
    st.session_state.navigate_to_tab = None
    components.html(
        f"""
        <script>
            // Streamlit renders tab buttons as [data-baseweb="tab"] elements.
            // We wait a tick to ensure they exist in the parent frame's DOM.
            setTimeout(function() {{
                var tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
                if (tabs.length > {_nav_tab}) tabs[{_nav_tab}].click();
            }}, 100);
        </script>
        """,
        height=0,
    )
