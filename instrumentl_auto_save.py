"""
Instrumentl Auto-Save Matches Script
=====================================

WARNING: Use at your own risk. This may violate Instrumentl's Terms of Service.

This script automates clicking "Save" on grants in your Instrumentl project matches.
It uses Selenium to control your browser.

PREREQUISITES:
1. pip install selenium
2. Download ChromeDriver: https://chromedriver.chromium.org/
   OR use: pip install webdriver-manager

USAGE:
1. Update the configuration section below
2. Run: python instrumentl_auto_save.py
3. Log in to Instrumentl when the browser opens
4. The script will navigate to your project and start saving matches
"""

import time
import random
import json
import sys
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# ==============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# ==============================================================================

# How many matches to save (set to None to save ALL visible matches)
MAX_MATCHES_TO_SAVE = None  # or set a number like 50, 100, etc.

# Random delay range between saves (seconds) - keeps behavior less predictable
# Min should not be set too low or you'll get rate limited
DELAY_MIN = 5.5
DELAY_MAX = 18

# Wait time for page loads (seconds)
PAGE_LOAD_TIMEOUT = 10

# Whether to scroll to load more matches (for infinite scroll)
AUTO_SCROLL = True

# Number of scrolls to perform
MAX_SCROLLS = 10

# Print every button found on the page to help diagnose selector issues
DEBUG_MODE = False

# ==============================================================================
# SCRIPT
# ==============================================================================

def select_project_gui(projects: dict) -> str:
    """
    Show a tkinter dropdown so the user can pick (or type) a project URL.
    Returns the URL string, or exits if the user cancels.
    Falls back to a numbered terminal menu if tkinter is unavailable.
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        # Headless / no display — fall back to terminal selection
        return _select_project_terminal(projects)

    result = {"url": None}

    def on_confirm():
        choice = combo.get().strip()
        # Accept either a known project name or a raw URL typed by the user
        result["url"] = projects.get(choice, choice)
        root.destroy()

    def on_cancel():
        root.destroy()

    root = tk.Tk()
    root.title("Select Instrumentl Project")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    tk.Label(root, text="Select a project or paste a URL:", padx=14, pady=8).pack()

    names = list(projects.keys())
    combo = ttk.Combobox(root, values=names, width=54, state="normal")
    if names:
        combo.current(0)
    combo.pack(padx=14, pady=4)

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="OK", width=10, command=on_confirm).pack(side=tk.LEFT, padx=6)
    tk.Button(btn_frame, text="Cancel", width=10, command=on_cancel).pack(side=tk.LEFT, padx=6)

    # Centre the window on screen
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")

    root.mainloop()

    if not result["url"]:
        print("\n❌ No project selected. Exiting.")
        sys.exit(0)

    return result["url"]


def _select_project_terminal(projects: dict) -> str:
    """Numbered terminal fallback when tkinter is unavailable."""
    names = list(projects.keys())
    print("\nAvailable projects:")
    for i, name in enumerate(names, 1):
        print(f"  [{i}] {name}")
    print(f"  [0] Enter a custom URL")

    while True:
        choice = input("\nSelect a project number: ").strip()
        if choice == "0":
            url = input("Paste project URL: ").strip()
            if url:
                return url
        elif choice.isdigit() and 1 <= int(choice) <= len(names):
            return projects[names[int(choice) - 1]]
        else:
            print("Invalid choice, try again.")


class InstrumentlAutoSaver:
    def __init__(self, max_saves=None, delay_min=7, delay_max=15):
        self.project_url = None   # set after user picks from GUI
        self.max_saves = max_saves
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.saved_count = 0
        self.driver = None

    # ------------------------------------------------------------------
    # Project discovery — fetch live from Instrumentl after login
    # ------------------------------------------------------------------

    def fetch_active_projects(self) -> dict:
        """
        Navigate to instrumentl.com/projects, click the 'Active' filter tab
        if one exists, scrape visible project cards, and return only active
        projects as {project_name: matches_url}.
        """
        print("\n📂 Fetching your active projects from Instrumentl...")
        self.driver.get("https://www.instrumentl.com/projects")
        time.sleep(random.uniform(2.5, 4.0))   # wait for SPA render

        # Try to click an "Active" filter tab to exclude archived/deleted projects
        clicked_filter = self.driver.execute_script(r"""
        var candidates = document.querySelectorAll(
            'button, a, [role="tab"], [role="button"], li, span'
        );
        for (var i = 0; i < candidates.length; i++) {
            var el = candidates[i];
            var txt = (el.textContent || '').trim().toLowerCase();
            if (txt === 'active' || txt === 'active projects') {
                el.click();
                return txt;
            }
        }
        return null;
        """)
        if clicked_filter:
            print(f"   Clicked '{clicked_filter}' filter tab")
            time.sleep(random.uniform(1.5, 2.5))   # wait for filter to apply

        raw = self.driver.execute_script(r"""
        var seen = {};
        var results = [];

        document.querySelectorAll('a[href*="/projects/"]').forEach(function(a) {
            var m = (a.getAttribute('href') || '').match(/\/projects\/(\d+)/);
            if (!m) return;
            var id = m[1];
            if (seen[id]) return;

            // Walk up to the card container to get the project name
            var name = a.textContent.trim();
            if (!name || name.length < 2) {
                var card = a.closest(
                    '[class*="card"],[class*="project"],[class*="item"],[class*="row"],[class*="tile"]'
                );
                if (card) {
                    var h = card.querySelector(
                        'h1,h2,h3,h4,h5,[class*="name"],[class*="title"],[class*="heading"]'
                    );
                    name = h ? h.textContent.trim() : '';
                }
            }

            // Skip nav labels and empty names
            var skip = ['projects', 'view', 'open', 'edit', 'settings', 'delete', 'new project', ''];
            if (!name || name.length > 120 || skip.indexOf(name.toLowerCase()) !== -1) return;

            seen[id] = true;
            results.push({ name: name, id: id });
        });

        return results;
        """)

        projects = {}
        for item in (raw or []):
            name = item.get('name', '').strip()
            pid  = item.get('id', '').strip()
            if name and pid:
                projects[name] = f"https://www.instrumentl.com/projects/{pid}#/matches"

        if not projects:
            print("   ⚠️  Could not auto-detect projects — check that you're logged in.")
        else:
            print(f"   Found {len(projects)} active project(s)")
        return projects

    def _random_delay(self, min_override=None, max_override=None):
        """Sleep for a random duration within the configured range."""
        lo = min_override if min_override is not None else self.delay_min
        hi = max_override if max_override is not None else self.delay_max
        duration = random.uniform(lo, hi)
        print(f"   (waiting {duration:.1f}s...)")
        time.sleep(duration)
        
    def setup_driver(self):
        """Initialize Chrome driver"""
        print("Setting up browser...")
        
        try:
            # Try using webdriver-manager (easier)
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except ImportError:
            # Fallback to manual ChromeDriver
            print("⚠️  webdriver-manager not installed. Using system ChromeDriver.")
            print("   Install with: pip install webdriver-manager")
            service = Service()  # Assumes chromedriver is in PATH
        
        options = Options()
        # Uncomment the line below to run headless (no browser window)
        # options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, PAGE_LOAD_TIMEOUT)
        
    def _install_network_interceptor(self):
        """Inject JS to monkey-patch fetch/XHR and record non-GET requests."""
        self.driver.execute_script(r"""
        window.__capturedRequests = [];

        // --- patch fetch ---
        const _origFetch = window.fetch;
        window.fetch = function() {
            var url = arguments[0];
            var opts = arguments[1] || {};
            var method = (opts.method || 'GET').toUpperCase();
            if (method !== 'GET') {
                window.__capturedRequests.push({
                    type: 'fetch', url: (typeof url === 'string' ? url : url.url),
                    method: method,
                    body: opts.body || null,
                    ts: Date.now()
                });
            }
            return _origFetch.apply(this, arguments);
        };

        // --- patch XMLHttpRequest ---
        const _origOpen = XMLHttpRequest.prototype.open;
        const _origSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.open = function(m, u) {
            this.__m = m; this.__u = u;
            return _origOpen.apply(this, arguments);
        };
        XMLHttpRequest.prototype.send = function(body) {
            if (this.__m && this.__m.toUpperCase() !== 'GET') {
                window.__capturedRequests.push({
                    type: 'xhr', url: this.__u,
                    method: this.__m,
                    body: body,
                    ts: Date.now()
                });
            }
            return _origSend.apply(this, arguments);
        };
        """)

    def login_prompt(self):
        """Open Instrumentl login page and wait for the user to log in."""
        print(f"\n📱 Opening Instrumentl...")
        self.driver.get("https://www.instrumentl.com/users/sign_in")

        print("\n" + "="*60)
        print("🔐 PLEASE LOG IN TO INSTRUMENTL")
        print("="*60)
        print("\n1. Log in to your Instrumentl account in the browser")
        print("2. Press ENTER here once you are fully logged in\n")

        input("Press ENTER when logged in: ")
        
    def scroll_to_load_more(self):
        """Scroll the page to trigger lazy loading of more matches"""
        if not AUTO_SCROLL:
            return
            
        print("📜 Scrolling to load more matches...")
        
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scrolls = 0
        
        while scrolls < MAX_SCROLLS:
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1.5, 3.0))

            # Calculate new scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                print(f"   Reached end after {scrolls} scrolls")
                break

            last_height = new_height
            scrolls += 1
            print(f"   Scroll {scrolls}/{MAX_SCROLLS}")

        # Scroll back to top
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(random.uniform(0.8, 1.5))
        
    # ------------------------------------------------------------------
    # Element discovery — JavaScript-based (handles React custom elements)
    # ------------------------------------------------------------------

    def _find_save_elements_js(self):
        """
        Find ANY visible element whose text / aria-label / title contains
        'save' (but not 'saved' or 'unsave').  Intentionally permissive:
        no tag-name or child-count restriction so React custom components
        and icon-button wrappers are all included.
        """
        return self.driver.execute_script(r"""
        var seen = new WeakSet();
        var results = [];

        function isVisible(el) {
            var r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return false;
            var s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
        }

        // Only check the element's own direct text nodes — NOT inherited text
        // from descendants.  This prevents a grant card's "Saved by..." text
        // from contaminating the check on the "Save" button inside it.
        function ownText(el) {
            var t = '';
            el.childNodes.forEach(function(n) {
                if (n.nodeType === 3) t += n.textContent;  // TEXT_NODE
            });
            return t.trim().toLowerCase();
        }

        function looksLikeSave(el) {
            var own   = ownText(el);
            var aria  = (el.getAttribute('aria-label') || '').toLowerCase();
            var title = (el.getAttribute('title') || '').toLowerCase();
            // The element signals "save" via its own text OR via aria/title
            var hasSave = (own === 'save') || aria.includes('save') || title.includes('save');
            // Must NOT already be in "saved" state
            var isSaved = own.includes('saved') || aria.includes('saved') || title.includes('saved');
            return hasSave && !isSaved;
        }

        var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, null);
        while (walker.nextNode()) {
            var el = walker.currentNode;
            if (seen.has(el)) continue;
            if (!isVisible(el)) continue;
            if (!looksLikeSave(el)) continue;

            // Prefer the most specific clickable ancestor
            var clickable = el;
            var p = el.parentElement;
            for (var i = 0; i < 3 && p; i++, p = p.parentElement) {
                var tag = p.tagName;
                var role = (p.getAttribute('role') || '').toLowerCase();
                if (tag === 'BUTTON' || tag === 'A' || role === 'button') {
                    clickable = p; break;
                }
            }

            if (!seen.has(clickable)) {
                seen.add(clickable);
                results.push(clickable);
            }
        }
        return results;
        """)

    def _debug_dump_all_elements(self):
        """Dump every visible clickable element and its text (debug helper)."""
        data = self.driver.execute_script(r"""
        var out = [];
        var all = document.querySelectorAll(
            'button, a, [role="button"], [onclick], [class*="save" i], [class*="Save"]'
        );
        for (var i = 0; i < Math.min(all.length, 80); i++) {
            var el = all[i];
            var r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            out.push({
                tag: el.tagName,
                text: el.textContent.trim().substring(0, 50),
                cls: (el.className || '').substring(0, 60),
                aria: el.getAttribute('aria-label') || '',
                href: el.getAttribute('href') || ''
            });
        }
        return out;
        """)
        print(f"\n[DEBUG] {len(data)} clickable elements found on page:")
        for i, d in enumerate(data, 1):
            print(f"  [{i:02d}] <{d['tag']}> text={d['text']!r:40s} class={d['cls']}")
        print()

    # ------------------------------------------------------------------
    # Network-capture approach (fallback when DOM clicking doesn't work)
    # ------------------------------------------------------------------

    def _get_captured_requests(self):
        """Return the list of non-GET requests captured by the JS interceptor."""
        try:
            return self.driver.execute_script("return window.__capturedRequests || [];")
        except Exception:
            return []

    def _clear_captured_requests(self):
        self.driver.execute_script("window.__capturedRequests = [];")

    def _capture_save_request(self):
        """
        Ask the user to manually save ONE grant, then return the captured
        request that represents the save action.
        """
        self._clear_captured_requests()

        print("\n" + "="*60)
        print("🔎 LEARNING THE SAVE REQUEST")
        print("="*60)
        print("\n  Please click 'Save' on ONE grant in the browser now.")
        print("  The script will capture the network request it triggers.\n")

        input("  Press ENTER after you've saved one grant: ")

        captured = self._get_captured_requests()
        if not captured:
            print("\n⚠️  No network requests were captured.")
            print("   The page may have reloaded (which clears the interceptor).")
            print("   Re-installing interceptor — try saving another grant.\n")
            self._install_network_interceptor()
            self._clear_captured_requests()
            input("  Click Save on one grant, then press ENTER: ")
            captured = self._get_captured_requests()

        if not captured:
            print("❌ Still no requests captured. Cannot proceed.")
            return None

        # Show captured requests and let user pick (or auto-pick the most likely)
        print(f"\n   Captured {len(captured)} request(s):")
        for i, req in enumerate(captured, 1):
            print(f"   [{i}] {req.get('method','?')} {req.get('url','?')[:90]}")
            if req.get('body'):
                body_preview = str(req['body'])[:120]
                print(f"       body: {body_preview}")

        if len(captured) == 1:
            chosen = captured[0]
        else:
            choice = input(f"\n   Which request is the save action? [1-{len(captured)}]: ").strip()
            idx = int(choice) - 1 if choice.isdigit() else 0
            chosen = captured[max(0, min(idx, len(captured) - 1))]

        print(f"\n✓ Captured: {chosen['method']} {chosen['url']}")
        return chosen

    def _replay_save_request(self, template_req, grant_id, old_grant_id):
        """
        Replay a captured save request, swapping old_grant_id → grant_id
        in the URL and body.  Runs inside the browser session (cookies intact).
        Returns True on success (HTTP 2xx).
        """
        url = template_req['url'].replace(str(old_grant_id), str(grant_id))
        body = template_req.get('body') or ''
        if body:
            body = body.replace(str(old_grant_id), str(grant_id))
        method = template_req.get('method', 'POST')

        status = self.driver.execute_script("""
        var url = arguments[0], method = arguments[1], body = arguments[2];
        var xhr = new XMLHttpRequest();
        xhr.open(method, url, false);          // synchronous
        xhr.setRequestHeader('Content-Type', 'application/json');
        try { xhr.send(body); } catch(e) { return -1; }
        return xhr.status;
        """, url, method, body if body else None)

        return 200 <= (status or 0) < 300

    # ------------------------------------------------------------------
    # Grant-ID extraction
    # ------------------------------------------------------------------

    def _extract_grant_ids_from_page(self):
        """
        Scrape grant / funder IDs from the matches page.  Instrumentl
        typically renders links like /grants/<id> or data attributes.
        Returns a list of unique ID strings.
        """
        ids = self.driver.execute_script(r"""
        var ids = new Set();
        // Links containing /grants/ or /funders/
        document.querySelectorAll('a[href*="/grants/"], a[href*="/funders/"]').forEach(function(a) {
            var m = a.href.match(/\/(grants|funders)\/(\d+)/);
            if (m) ids.add(m[2]);
        });
        // data-grant-id or data-id attributes
        document.querySelectorAll('[data-grant-id], [data-id]').forEach(function(el) {
            var v = el.getAttribute('data-grant-id') || el.getAttribute('data-id');
            if (v) ids.add(v);
        });
        return Array.from(ids);
        """)
        return ids or []

    # ------------------------------------------------------------------
    # Main save orchestration
    # ------------------------------------------------------------------

    def save_matches(self):
        """
        Try DOM clicking first.  If no elements found, fall back to
        network-capture + API-replay approach.
        """
        print("\n" + "="*60)
        print("🎯 STARTING AUTO-SAVE")
        print("="*60 + "\n")

        # Scroll to load more matches
        self.scroll_to_load_more()

        # ---------- Attempt 1: confirmed CSS selector from Selenium recording ----------
        print("🔍 Looking for Save buttons (.save-button-container > .btn)...")
        css_btns = self.driver.find_elements(By.CSS_SELECTOR, ".save-button-container > .btn")
        elements = [el for el in css_btns if el.is_displayed()]

        # ---------- Attempt 2: JS deep scan fallback ----------
        if not elements:
            print("   CSS selector found nothing — falling back to JS deep scan...")
            if DEBUG_MODE:
                self._debug_dump_all_elements()
            elements = self._find_save_elements_js()

        if elements:
            print(f"✓ Found {len(elements)} Save elements via JS scan")
            self._save_via_dom_clicks(elements)
        else:
            print("⚠️  No Save elements found via DOM scan.")
            print("   Switching to network-capture mode...\n")
            self._save_via_network_capture()

    def _save_via_dom_clicks(self, initial_elements):
        """Click Save elements found by JS scan, re-fetching each iteration."""
        to_save = self.max_saves if self.max_saves else len(initial_elements)

        print(f"\n📊 Will save up to {to_save} matches")
        print(f"   Delay between saves: {self.delay_min}–{self.delay_max}s (randomized)\n")
        input("Press ENTER to start saving (or Ctrl+C to cancel)...")
        print()

        failures = 0

        while self.saved_count < to_save:
            try:
                elements = self._find_save_elements_js()
                if not elements:
                    print("   No more Save elements on page.")
                    break

                el = elements[0]
                idx = f"[{self.saved_count + 1}/{to_save}]"
                print(f"{idx} 💾 Saving match...", end='', flush=True)

                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", el)
                time.sleep(random.uniform(0.3, 0.8))

                # Click via JS (most reliable across React portals)
                self.driver.execute_script("arguments[0].click();", el)
                self.saved_count += 1
                failures = 0
                print(f" ✓ Saved! (Total: {self.saved_count})")

                time.sleep(random.uniform(0.4, 0.8))

                if self.saved_count < to_save:
                    self._random_delay()

            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
                break
            except StaleElementReferenceException:
                print(" (stale, retrying...)")
                time.sleep(0.5)
                continue
            except Exception as e:
                failures += 1
                print(f" ✗ Error: {e}")
                if failures >= 5:
                    print("   Too many consecutive DOM failures — switching to network capture.")
                    self._save_via_network_capture()
                    return
                time.sleep(1)
                continue

        self._print_summary()

    def _save_via_network_capture(self):
        """
        Fallback: ask user to save one grant manually, capture the HTTP
        request, extract all grant IDs, then replay for each.
        """
        template = self._capture_save_request()
        if not template:
            return

        # Try to figure out the grant ID used in the captured request
        body_str = template.get('body') or template.get('url', '')
        url_str = template.get('url', '')
        combined = url_str + ' ' + str(body_str)

        import re
        # Look for numeric IDs in the URL/body
        id_candidates = re.findall(r'\b(\d{4,})\b', combined)
        if not id_candidates:
            print("⚠️  Could not extract a grant ID from the captured request.")
            print(f"   URL:  {url_str}")
            print(f"   Body: {str(body_str)[:200]}")
            manual_id = input("   Enter the grant ID you just saved: ").strip()
            id_candidates = [manual_id] if manual_id else []

        if not id_candidates:
            print("❌ No grant ID to work with. Exiting.")
            return

        saved_id = id_candidates[0]
        print(f"   Saved grant ID from capture: {saved_id}")

        # Get all grant IDs on the page
        all_ids = self._extract_grant_ids_from_page()
        print(f"   Found {len(all_ids)} grant/funder IDs on page")

        # Remove the already-saved one
        remaining = [gid for gid in all_ids if gid != saved_id]
        if not remaining:
            print("⚠️  No additional grant IDs found. The page might load them dynamically.")
            print("   Try scrolling down first and re-running.")
            return

        to_save = self.max_saves if self.max_saves else len(remaining)
        remaining = remaining[:to_save]

        print(f"\n📊 Will replay save for {len(remaining)} grants")
        print(f"   Delay between saves: {self.delay_min}–{self.delay_max}s (randomized)\n")
        input("Press ENTER to start (or Ctrl+C to cancel)...")
        print()

        for i, gid in enumerate(remaining, 1):
            try:
                idx = f"[{i}/{len(remaining)}]"
                print(f"{idx} 💾 Saving grant {gid}...", end='', flush=True)

                ok = self._replay_save_request(template, gid, saved_id)
                if ok:
                    self.saved_count += 1
                    print(f" ✓ (Total: {self.saved_count})")
                else:
                    print(f" ✗ request failed")

                if i < len(remaining):
                    self._random_delay()

            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
                break
            except Exception as e:
                print(f" ✗ Error: {e}")
                continue

        self._print_summary()

    def _print_summary(self):
        print("\n" + "="*60)
        print(f"✅ COMPLETE - Saved {self.saved_count} matches")
        print("="*60 + "\n")
        
    def run(self):
        """Main execution flow."""
        try:
            self.setup_driver()

            # Step 1 — log in
            self.login_prompt()

            # Step 2 — project selection (skip if already set via CLI)
            if not self.project_url:
                projects = self.fetch_active_projects()
                if not projects:
                    projects = {"(enter URL manually)": ""}
                self.project_url = select_project_gui(projects)
                if not self.project_url:
                    print("\n❌ No project selected. Exiting.")
                    return
            else:
                print(f"\n🌐 Project set from command line: {self.project_url}")

            # Step 3 — navigate to the chosen project and install interceptor
            print(f"\n🌐 Navigating to: {self.project_url}")
            self.driver.get(self.project_url)
            time.sleep(random.uniform(2.0, 3.5))

            # Click the Matches tab (confirmed working selector from Selenium recording)
            try:
                matches_tab = WebDriverWait(self.driver, PAGE_LOAD_TIMEOUT).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#matches-nav-tab > .name"))
                )
                matches_tab.click()
                print("   ✓ Navigated to Matches tab")
                time.sleep(random.uniform(1.5, 2.5))
            except (TimeoutException, NoSuchElementException):
                print("   (Matches tab not found — may already be on matches page)")
            print("   Installing network interceptor...")
            self._install_network_interceptor()
            print(f"\n📋 Configuration:")
            print(f"   Project URL : {self.project_url}")
            print(f"   Max saves   : {self.max_saves or 'ALL'}")
            print(f"   Delay range : {self.delay_min}–{self.delay_max}s (randomized)")
            print(f"   Auto-scroll : {AUTO_SCROLL}\n")

            # Step 4 — save
            self.save_matches()

            print("\n✓ All done! Press ENTER to close browser...")
            input()

        except KeyboardInterrupt:
            print("\n\n⚠️  Script interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.driver:
                print("\n🔒 Closing browser...")
                self.driver.quit()


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Instrumentl Auto-Save Matches")
    parser.add_argument(
        "--project-id", default=None,
        help="Instrumentl project ID (digits from URL, e.g. 326636)"
    )
    parser.add_argument(
        "--project-url", default=None,
        help="Full Instrumentl project URL (overrides --project-id)"
    )
    parser.add_argument(
        "--max-saves", type=int, default=None,
        help="Maximum number of matches to save (default: all)"
    )
    args = parser.parse_args()

    # Build project URL from CLI args if provided
    cli_project_url = None
    if args.project_url:
        cli_project_url = args.project_url
    elif args.project_id:
        cli_project_url = (
            f"https://www.instrumentl.com/projects/{args.project_id}#/matches"
        )

    if not cli_project_url:
        # Interactive mode — show banner and ask for confirmation
        print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     Instrumentl Auto-Save Matches Script                ║
    ║                                                          ║
    ║  ⚠️  WARNING: Use at your own risk!                     ║
    ║     This may violate Terms of Service                   ║
    ╚══════════════════════════════════════════════════════════╝
        """)
        print("\n⚠️  IMPORTANT:")
        print("   • This script automates clicking 'Save' on matches")
        print("   • You must be logged in to Instrumentl")
        print("   • Use reasonable delays to avoid rate limiting")
        print("   • Your account could be banned for automation")

        response = input("\nDo you want to continue? (yes/no): ").strip().lower()
        if response != 'yes':
            print("\n❌ Cancelled by user")
            return

    saver = InstrumentlAutoSaver(
        max_saves=args.max_saves if args.max_saves is not None else MAX_MATCHES_TO_SAVE,
        delay_min=DELAY_MIN,
        delay_max=DELAY_MAX,
    )

    if cli_project_url:
        saver.project_url = cli_project_url

    saver.run()


if __name__ == "__main__":
    main()
