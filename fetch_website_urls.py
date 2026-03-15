"""
fetch_website_urls.py
=====================
Populate website URLs for saved grants by navigating each Instrumentl grant
page in a logged-in browser session and reading the "View website" link.

Run after saving grants in the Streamlit app:

    python fetch_website_urls.py

Reads:  saved_grants.json   (written by the Streamlit app)
Writes: saved_grants.json   (Website URL field updated in-place)
        website_url_cache.json  (grant_id → url, used by the Results tab)

Credentials: set in a .env file or as environment variables:
    INSTRUMENTL_EMAIL=you@example.com
    INSTRUMENTL_PASSWORD=yourpassword
"""

import json
import os
import re
import time
import pathlib

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SAVED_GRANTS_FILE = pathlib.Path("saved_grants.json")
CACHE_FILE        = pathlib.Path("website_url_cache.json")
PAGE_TIMEOUT      = 15   # seconds to wait for page elements
DELAY_BETWEEN     = 1.0  # seconds between grant pages (be gentle)

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_json(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {} if path == CACHE_FILE else []
    return {} if path == CACHE_FILE else []


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Browser setup
# ---------------------------------------------------------------------------

def _setup_driver():
    from selenium.webdriver.firefox.service import Service
    from selenium.webdriver.firefox.options import Options
    from selenium import webdriver

    options = Options()
    # Keep headless=False so you can intervene if Instrumentl asks for CAPTCHA
    # Uncomment the next line to run without a window:
    # options.add_argument("--headless")

    # Auto-detect Firefox on Windows
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
        service = Service()  # geckodriver must be in PATH

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
        print("\n⚠️  INSTRUMENTL_EMAIL / INSTRUMENTL_PASSWORD not set.")
        print("   Add them to a .env file or set as environment variables.\n")
        email    = input("   Instrumentl email: ").strip()
        password = input("   Instrumentl password: ").strip()

    print("  Logging in…")
    driver.get("https://www.instrumentl.com/login")
    wait = WebDriverWait(driver, 20)

    email_field = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input[type='email'], input[name='email']")
    ))
    email_field.clear()
    email_field.send_keys(email)

    pwd_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
    pwd_field.clear()
    pwd_field.send_keys(password)
    pwd_field.send_keys(Keys.RETURN)

    wait.until(EC.url_changes("https://www.instrumentl.com/login"))
    time.sleep(2)
    print("  ✓ Logged in")


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

    # Try reading .grant-website-url directly (may already be on Funding Opportunity tab)
    for attempt in range(2):
        try:
            el = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".grant-website-url"))
            )
            href = el.get_attribute("href")
            if href and "instrumentl.com" not in href and "streamlit.app" not in href:
                return href
        except TimeoutException:
            pass

        if attempt == 0:
            # Click "Funding Opportunity" tab and retry
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
    grants = _load_json(SAVED_GRANTS_FILE)
    if not grants:
        print("saved_grants.json is empty or missing. Save some grants in the Streamlit app first.")
        return

    cache = _load_json(CACHE_FILE)

    # Find grants that still need a URL
    to_process = [
        g for g in grants
        if not (g.get("Website URL") or "").strip()
        or g.get("Website URL", "").startswith("https://grantsearch.streamlit.app")
    ]

    if not to_process:
        print(f"✅ All {len(grants)} saved grant(s) already have website URLs.")
        return

    print(f"\n📋 {len(to_process)} grant(s) need website URLs (out of {len(grants)} saved)\n")

    driver = _setup_driver()
    try:
        _login(driver)

        for i, grant in enumerate(to_process, 1):
            name  = grant.get("Grant Name", "?")
            gid   = grant.get("Grant ID", "")

            # Extract slug from the Grant URL (instrumentl.com/grants/{slug})
            grant_url = grant.get("Grant URL", "")
            m = re.search(r"instrumentl\.com/grants/([^/?#]+)", grant_url)
            if not m:
                print(f"[{i}/{len(to_process)}] ⚠️  No slug in Grant URL — skipping: {name}")
                continue

            slug = m.group(1)
            print(f"[{i}/{len(to_process)}] {name} ({slug})… ", end="", flush=True)

            url = _get_website_url(driver, slug)

            if url:
                print(f"✓  {url}")
                grant["Website URL"] = url
                if gid:
                    cache[gid] = url
            else:
                print("✗  not found")

            if i < len(to_process):
                time.sleep(DELAY_BETWEEN)

        # Persist results
        _save_json(SAVED_GRANTS_FILE, grants)
        _save_json(CACHE_FILE, cache)

        found = sum(1 for g in to_process if g.get("Website URL"))
        print(f"\n✅ Done — found URLs for {found}/{len(to_process)} grant(s)")
        print(f"   saved_grants.json and website_url_cache.json updated\n")

    finally:
        input("Press ENTER to close the browser… ")
        driver.quit()


if __name__ == "__main__":
    main()
