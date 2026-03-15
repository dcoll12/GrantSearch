"""
fetch_website_urls.py
=====================
Fetch website URLs for ALL saved grants from Instrumentl using the API
to get grant slugs, then a logged-in browser session to read each
"View website" link.

    python fetch_website_urls.py

Reads:  config.json            (API credentials — written by Streamlit app)
Writes: website_url_cache.json (grant_id → url, read by Streamlit app automatically)
        saved_grants.json      (Website URL updated in-place if file exists)

Browser login credentials — set in a .env file or as environment variables:
    INSTRUMENTL_EMAIL=you@example.com
    INSTRUMENTL_PASSWORD=yourpassword

Resume-safe: already-cached grants are skipped automatically.
"""

import json
import os
import sys
import time
import pathlib

CONFIG_FILE = pathlib.Path("config.json")
CACHE_FILE  = pathlib.Path("website_url_cache.json")
SAVED_FILE  = pathlib.Path("saved_grants.json")

PAGE_TIMEOUT  = 15   # seconds to wait for grant page elements
DELAY_BETWEEN = 1.0  # seconds between pages


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_api_credentials():
    cfg = _load_json(CONFIG_FILE, {})
    key_id  = cfg.get("api_key_id", "").strip()
    key_prv = cfg.get("api_private_key", "").strip()
    if not key_id or not key_prv:
        print("⚠️  API credentials not found in config.json.")
        print("   Connect to the API in the Streamlit app first (sidebar → Connect).")
        sys.exit(1)
    return key_id, key_prv


# ---------------------------------------------------------------------------
# Fetch all grants via API
# ---------------------------------------------------------------------------

def _fetch_all_grants(api_key_id, api_private_key):
    """Use the Instrumentl API to get every saved grant with its slug."""
    import requests

    session = requests.Session()
    session.auth = (api_key_id, api_private_key)
    session.headers.update({"Accept": "application/json"})

    BASE = "https://api.instrumentl.com/v1"
    grants = []
    cursor = None
    page   = 1

    print("Fetching grants from Instrumentl API…")
    while True:
        params = {"page_size": 50}
        if cursor:
            params["cursor"] = cursor

        resp = session.get(f"{BASE}/saved_grants", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        batch = data.get("saved_grants", [])
        if not batch:
            break

        # saved_grants returns a grant_id; fetch full record for slug
        for saved in batch:
            gid = saved.get("grant_id")
            if not gid:
                continue
            try:
                r = session.get(f"{BASE}/grants/{gid}", timeout=30)
                if r.status_code == 200:
                    grants.append(r.json())
                time.sleep(0.15)
            except Exception:
                pass

        meta = data.get("meta", {})
        print(f"  Page {page}: {len(batch)} saved grants (total so far: {len(grants)})")
        if not meta.get("has_more"):
            break
        cursor = meta.get("cursor")
        page  += 1

    return grants


# ---------------------------------------------------------------------------
# Browser setup
# ---------------------------------------------------------------------------

def _setup_driver():
    from selenium.webdriver.firefox.service import Service
    from selenium.webdriver.firefox.options import Options
    from selenium import webdriver

    options = Options()
    # Uncomment to run without a visible window:
    # options.add_argument("--headless")

    if os.name == "nt" and not options.binary_location:
        candidates = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Mozilla Firefox\firefox.exe"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                options.binary_location = p
                break

    try:
        from webdriver_manager.firefox import GeckoDriverManager
        service = Service(GeckoDriverManager().install())
    except ImportError:
        service = Service()

    driver = webdriver.Firefox(service=service, options=options)
    driver.maximize_window()
    return driver


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def _login(driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    email    = os.environ.get("INSTRUMENTL_EMAIL", "").strip()
    password = os.environ.get("INSTRUMENTL_PASSWORD", "").strip()

    if not email or not password:
        print("\n⚠️  INSTRUMENTL_EMAIL / INSTRUMENTL_PASSWORD not set in .env")
        email    = input("   Instrumentl email: ").strip()
        password = input("   Instrumentl password: ").strip()

    driver.get("https://www.instrumentl.com/login")
    wait = WebDriverWait(driver, 20)

    email_field = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input[type='email'], input[name='email']")
    ))
    email_field.clear()
    email_field.send_keys(email)

    pwd = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
    pwd.clear()
    pwd.send_keys(password)
    pwd.send_keys(Keys.RETURN)

    wait.until(EC.url_changes("https://www.instrumentl.com/login"))
    time.sleep(2)
    print("  ✓ Logged in\n")


# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------

def _get_website_url(driver, slug):
    """Navigate to instrumentl.com/grants/{slug} and return the funder website URL."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    driver.get(f"https://www.instrumentl.com/grants/{slug}")
    wait = WebDriverWait(driver, PAGE_TIMEOUT)

    for attempt in range(2):
        try:
            el = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".grant-website-url"))
            )
            href = el.get_attribute("href") or ""
            if href and "instrumentl.com" not in href and "streamlit.app" not in href:
                return href
        except TimeoutException:
            pass

        if attempt == 0:
            try:
                tab = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//a[contains(.,'Funding Opportunity')]")
                    )
                )
                tab.click()
                time.sleep(1.5)
            except TimeoutException:
                break

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    api_key_id, api_private_key = _load_api_credentials()

    # 1. Pull all saved grants from the API
    all_grants = _fetch_all_grants(api_key_id, api_private_key)
    if not all_grants:
        print("No grants returned from API.")
        return

    print(f"\n✓ {len(all_grants)} grant(s) fetched from API")

    # 2. Load existing cache — skip already-done grants
    cache = _load_json(CACHE_FILE, {})

    to_process = [
        g for g in all_grants
        if str(g.get("id", "")) not in cache and g.get("slug")
    ]

    if not to_process:
        print(f"✅ All {len(all_grants)} grant(s) already in cache — nothing to do.")
        _patch_saved_grants(cache)
        return

    print(f"📋 {len(to_process)} grant(s) need website URLs "
          f"({len(all_grants) - len(to_process)} already cached)\n")

    # 3. Browser session
    driver = _setup_driver()
    try:
        _login(driver)

        found = 0
        for i, grant in enumerate(to_process, 1):
            gid  = str(grant.get("id", ""))
            slug = grant.get("slug", "")
            name = grant.get("name", slug)

            print(f"[{i}/{len(to_process)}] {name}… ", end="", flush=True)

            url = _get_website_url(driver, slug)

            if url:
                print(f"✓  {url}")
                cache[gid] = url
                found += 1
            else:
                print("✗  not found")
                cache[gid] = ""   # mark as attempted so we don't retry

            # Save after every grant — resume-safe if script is interrupted
            _save_json(CACHE_FILE, cache)

            if i < len(to_process):
                time.sleep(DELAY_BETWEEN)

        print(f"\n✅ Done — found URLs for {found}/{len(to_process)} grant(s)")
        print(f"   website_url_cache.json updated ({len(cache)} total entries)\n")

    finally:
        input("Press ENTER to close the browser… ")
        driver.quit()

    # 4. Patch saved_grants.json if it exists
    _patch_saved_grants(cache)


def _patch_saved_grants(cache):
    """Update Website URL in saved_grants.json using the cache."""
    saved = _load_json(SAVED_FILE, [])
    if not saved:
        return

    updated = 0
    for g in saved:
        gid = str(g.get("Grant ID", ""))
        if gid in cache and cache[gid]:
            if g.get("Website URL") != cache[gid]:
                g["Website URL"] = cache[gid]
                updated += 1

    if updated:
        _save_json(SAVED_FILE, saved)
        print(f"   saved_grants.json updated — {updated} Website URL(s) patched")


if __name__ == "__main__":
    main()
