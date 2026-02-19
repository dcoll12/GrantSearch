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

# Your Instrumentl project URL
PROJECT_URL = "https://www.instrumentl.com/projects/336006#/matches"

# How many matches to save (set to None to save ALL visible matches)
MAX_MATCHES_TO_SAVE = None  # or set a number like 50, 100, etc.

# Delay between saves (seconds) - don't set too low or you'll get rate limited
DELAY_BETWEEN_SAVES = 10

# Wait time for page loads (seconds)
PAGE_LOAD_TIMEOUT = 10

# Whether to scroll to load more matches (for infinite scroll)
AUTO_SCROLL = True

# Number of scrolls to perform
MAX_SCROLLS = 10

# ==============================================================================
# SCRIPT
# ==============================================================================

class InstrumentlAutoSaver:
    def __init__(self, project_url, max_saves=None, delay=2):
        self.project_url = project_url
        self.max_saves = max_saves
        self.delay = delay
        self.saved_count = 0
        self.driver = None
        
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
            time.sleep(2)
            
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
        time.sleep(1)
        
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
            time.sleep(0.5)
            
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
        print(f"   Delay between saves: {self.delay}s\n")
        
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
                
                # Wait between saves (rate limiting)
                if idx < to_save:
                    time.sleep(self.delay)
                    
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
    
    print(f"\n📋 Configuration:")
    print(f"   Project URL: {PROJECT_URL}")
    print(f"   Max saves: {MAX_MATCHES_TO_SAVE if MAX_MATCHES_TO_SAVE else 'ALL'}")
    print(f"   Delay: {DELAY_BETWEEN_SAVES}s")
    print(f"   Auto-scroll: {AUTO_SCROLL}")
    
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
        project_url=PROJECT_URL,
        max_saves=MAX_MATCHES_TO_SAVE,
        delay=DELAY_BETWEEN_SAVES
    )
    
    saver.run()


if __name__ == "__main__":
    main()
