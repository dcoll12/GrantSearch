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
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# ==============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# ==============================================================================

# Known projects: { "Display Name": "https://www.instrumentl.com/projects/ID#/matches" }
# Add as many entries as you like; the GUI dropdown will list them all.
# You can also type a brand-new URL directly in the dropdown at runtime.
PROJECTS = {
    "My Project": "https://www.instrumentl.com/projects/336006#/matches",
    # "Another Project": "https://www.instrumentl.com/projects/999999#/matches",
}

# How many matches to save (set to None to save ALL visible matches)
MAX_MATCHES_TO_SAVE = None  # or set a number like 50, 100, etc.

# Random delay range between saves (seconds) - keeps behavior less predictable
# Min should not be set too low or you'll get rate limited
DELAY_MIN = 7
DELAY_MAX = 15

# Wait time for page loads (seconds)
PAGE_LOAD_TIMEOUT = 10

# Whether to scroll to load more matches (for infinite scroll)
AUTO_SCROLL = True

# Number of scrolls to perform
MAX_SCROLLS = 10

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
    def __init__(self, project_url, max_saves=None, delay_min=7, delay_max=15):
        self.project_url = project_url
        self.max_saves = max_saves
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.saved_count = 0
        self.driver = None

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
        
    def login_prompt(self):
        """Navigate to project and wait for user to log in"""
        print(f"\n📱 Opening Instrumentl...")
        self.driver.get(self.project_url)
        
        print("\n" + "="*60)
        print("🔐 PLEASE LOG IN TO INSTRUMENTL")
        print("="*60)
        print("\n1. Log in to your Instrumentl account in the browser")
        print("2. Navigate to your project matches if not already there")
        print("3. Press ENTER in this terminal when ready to start...\n")
        
        input("Press ENTER when logged in and ready: ")
        print("\n✓ Starting auto-save process...\n")
        
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
        
    def find_save_buttons(self):
        """Find all 'Save' buttons on the page"""
        # These selectors might need adjustment based on Instrumentl's actual HTML
        # Common patterns to try:
        
        possible_selectors = [
            "//button[contains(text(), 'Save')]",
            "//a[contains(text(), 'Save')]",
            "//button[contains(@class, 'save')]",
            "//button[@data-action='save']",
            "//button[@aria-label='Save']",
            "//div[contains(@class, 'save-button')]//button",
        ]
        
        buttons = []
        for selector in possible_selectors:
            try:
                found = self.driver.find_elements(By.XPATH, selector)
                if found:
                    print(f"✓ Found {len(found)} buttons with selector: {selector[:50]}...")
                    buttons = found
                    break
            except:
                continue
        
        if not buttons:
            print("⚠️  No save buttons found. The page structure may have changed.")
            print("   Opening browser for manual inspection...")
            input("Press ENTER to continue...")
            
        return buttons
    
    def is_already_saved(self, button):
        """Check if the grant is already saved"""
        # Look for indicators that it's already saved
        try:
            # Check button text
            button_text = button.text.lower()
            if 'saved' in button_text or 'unsave' in button_text or 'remove' in button_text:
                return True
            
            # Check for 'saved' class or attribute
            classes = button.get_attribute('class') or ''
            if 'saved' in classes.lower():
                return True
                
            # Check disabled state
            if not button.is_enabled():
                return True
                
            return False
        except:
            return False
    
    def click_save_button(self, button):
        """Click a save button safely"""
        try:
            # Scroll button into view
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
            time.sleep(random.uniform(0.3, 0.9))
            
            # Try regular click
            try:
                button.click()
            except:
                # Fallback to JavaScript click
                self.driver.execute_script("arguments[0].click();", button)
            
            return True
        except Exception as e:
            print(f"   ⚠️  Error clicking button: {e}")
            return False
    
    def save_matches(self):
        """Main function to save all matches"""
        print("\n" + "="*60)
        print("🎯 STARTING AUTO-SAVE")
        print("="*60 + "\n")
        
        # Scroll to load more matches
        self.scroll_to_load_more()
        
        # Find all save buttons
        print("\n🔍 Looking for save buttons...")
        save_buttons = self.find_save_buttons()
        
        if not save_buttons:
            print("\n❌ No save buttons found. Exiting.")
            return
        
        total_found = len(save_buttons)
        to_save = self.max_saves if self.max_saves else total_found
        
        print(f"\n📊 Found {total_found} matches")
        print(f"   Will save: {min(to_save, total_found)} matches")
        print(f"   Delay between saves: {self.delay_min}–{self.delay_max}s (randomized)\n")
        
        input("Press ENTER to start saving (or Ctrl+C to cancel)...")
        print()
        
        # Save each match
        for idx, button in enumerate(save_buttons[:to_save], 1):
            try:
                # Check if already saved
                if self.is_already_saved(button):
                    print(f"[{idx}/{to_save}] ⏭️  Already saved, skipping...")
                    continue
                
                # Click save
                print(f"[{idx}/{to_save}] 💾 Saving match...", end='')
                
                if self.click_save_button(button):
                    self.saved_count += 1
                    print(f" ✓ Saved! (Total: {self.saved_count})")
                else:
                    print(f" ✗ Failed")
                
                # Wait between saves (randomized to reduce rate-limit risk)
                if idx < to_save:
                    self._random_delay()
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
                break
            except Exception as e:
                print(f"\n⚠️  Error on match {idx}: {e}")
                continue
        
        print("\n" + "="*60)
        print(f"✅ COMPLETE - Saved {self.saved_count} matches")
        print("="*60 + "\n")
        
    def run(self):
        """Main execution flow"""
        try:
            self.setup_driver()
            self.login_prompt()
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

    # --- Project selection GUI ---
    print("\n🖥️  Opening project selector...")
    project_url = select_project_gui(PROJECTS)

    print(f"\n📋 Configuration:")
    print(f"   Project URL: {project_url}")
    print(f"   Max saves: {MAX_MATCHES_TO_SAVE if MAX_MATCHES_TO_SAVE else 'ALL'}")
    print(f"   Delay range: {DELAY_MIN}–{DELAY_MAX}s (randomized)")
    print(f"   Auto-scroll: {AUTO_SCROLL}")

    saver = InstrumentlAutoSaver(
        project_url=project_url,
        max_saves=MAX_MATCHES_TO_SAVE,
        delay_min=DELAY_MIN,
        delay_max=DELAY_MAX
    )
    
    saver.run()


if __name__ == "__main__":
    main()
