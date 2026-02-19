# Browser Console Auto-Save Script (Easier Method!)

If you don't want to install Selenium, you can use this simpler method that runs directly in your browser's Developer Console.

## How to Use (5 Easy Steps)

### Step 1: Open Your Project Matches
1. Go to: `https://www.instrumentl.com/projects/336006#/matches`
2. Log in if needed
3. Scroll down to load all the matches you want to save

### Step 2: Open Developer Console
- **Chrome/Edge**: Press `F12` or `Ctrl+Shift+J` (Windows) / `Cmd+Option+J` (Mac)
- **Firefox**: Press `F12` or `Ctrl+Shift+K` (Windows) / `Cmd+Option+K` (Mac)
- **Safari**: Enable Developer menu first, then `Cmd+Option+C`

### Step 3: Paste the Script

Copy and paste this entire script into the console:

```javascript
// ============================================================================
// Instrumentl Auto-Save Console Script
// ============================================================================
// WARNING: Use at your own risk. May violate Terms of Service.
// ============================================================================

(async function() {
    console.log('🎯 Instrumentl Auto-Save Script Starting...\n');
    
    // ===== CONFIGURATION =====
    const CONFIG = {
        delayBetweenSaves: 2000,  // 2 seconds (increase if you get rate limited)
        maxToSave: null,           // null = save all, or set a number like 50
        scrollFirst: true,         // Scroll to load more matches first
        maxScrolls: 10             // Number of times to scroll
    };
    
    // ===== HELPER FUNCTIONS =====
    
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    async function scrollToLoadMore() {
        if (!CONFIG.scrollFirst) return;
        
        console.log('📜 Scrolling to load more matches...');
        let lastHeight = document.body.scrollHeight;
        let scrolls = 0;
        
        while (scrolls < CONFIG.maxScrolls) {
            window.scrollTo(0, document.body.scrollHeight);
            await sleep(2000);
            
            const newHeight = document.body.scrollHeight;
            if (newHeight === lastHeight) {
                console.log(`   ✓ Loaded all matches after ${scrolls} scrolls`);
                break;
            }
            
            lastHeight = newHeight;
            scrolls++;
            console.log(`   Scroll ${scrolls}/${CONFIG.maxScrolls}`);
        }
        
        // Scroll back to top
        window.scrollTo(0, 0);
        await sleep(1000);
    }
    
    function findSaveButtons() {
        // Try different selectors - adjust based on actual page structure
        const selectors = [
            'button:contains("Save")',
            'a:contains("Save")',
            'button[class*="save"]',
            'button[data-action="save"]',
            '[class*="save-button"] button',
            'button[aria-label*="Save"]'
        ];
        
        let buttons = [];
        
        // Try text-based search
        const allButtons = document.querySelectorAll('button, a');
        buttons = Array.from(allButtons).filter(btn => {
            const text = btn.textContent.trim().toLowerCase();
            return text === 'save' || text === 'save grant';
        });
        
        if (buttons.length === 0) {
            console.log('⚠️  Could not find save buttons automatically.');
            console.log('   Inspect the page and update the selector.');
            return null;
        }
        
        return buttons;
    }
    
    function isAlreadySaved(button) {
        const text = button.textContent.toLowerCase();
        const classes = button.className.toLowerCase();
        
        return (
            text.includes('saved') ||
            text.includes('unsave') ||
            classes.includes('saved') ||
            button.disabled
        );
    }
    
    async function clickButton(button) {
        button.scrollIntoView({ behavior: 'smooth', block: 'center' });
        await sleep(500);
        button.click();
    }
    
    // ===== MAIN EXECUTION =====
    
    console.log('⚙️  Configuration:');
    console.log(`   Delay: ${CONFIG.delayBetweenSaves}ms`);
    console.log(`   Max to save: ${CONFIG.maxToSave || 'ALL'}`);
    console.log(`   Scroll first: ${CONFIG.scrollFirst}\n`);
    
    // Scroll to load more
    await scrollToLoadMore();
    
    // Find save buttons
    console.log('🔍 Finding save buttons...');
    const buttons = findSaveButtons();
    
    if (!buttons) {
        console.log('❌ Could not find save buttons. Script stopped.');
        console.log('\n💡 TIP: Inspect a "Save" button and update the selector:');
        console.log('   1. Right-click on a Save button → Inspect');
        console.log('   2. Find the button element in the HTML');
        console.log('   3. Update the findSaveButtons() function');
        return;
    }
    
    const totalFound = buttons.length;
    const toSave = CONFIG.maxToSave ? Math.min(CONFIG.maxToSave, totalFound) : totalFound;
    
    console.log(`\n📊 Found ${totalFound} save buttons`);
    console.log(`   Will save: ${toSave} matches\n`);
    
    // Ask for confirmation
    if (!confirm(`Ready to save ${toSave} matches?\n\nClick OK to continue.`)) {
        console.log('❌ Cancelled by user');
        return;
    }
    
    // Save each match
    let savedCount = 0;
    let skippedCount = 0;
    
    for (let i = 0; i < toSave; i++) {
        const button = buttons[i];
        const progress = `[${i + 1}/${toSave}]`;
        
        try {
            // Check if already saved
            if (isAlreadySaved(button)) {
                console.log(`${progress} ⏭️  Already saved, skipping...`);
                skippedCount++;
                continue;
            }
            
            // Click save
            console.log(`${progress} 💾 Saving...`);
            await clickButton(button);
            savedCount++;
            console.log(`${progress} ✓ Saved! (Total: ${savedCount})`);
            
            // Wait between saves
            if (i < toSave - 1) {
                await sleep(CONFIG.delayBetweenSaves);
            }
            
        } catch (error) {
            console.log(`${progress} ❌ Error: ${error.message}`);
        }
    }
    
    // Summary
    console.log('\n' + '='.repeat(60));
    console.log('✅ COMPLETE');
    console.log(`   Saved: ${savedCount}`);
    console.log(`   Skipped: ${skippedCount}`);
    console.log(`   Total processed: ${savedCount + skippedCount}/${toSave}`);
    console.log('='.repeat(60));
    
})();
```

### Step 4: Press Enter
The script will run and start saving matches automatically.

### Step 5: Wait
Let the script finish. You'll see progress in the console.

---

## Customization

Edit these values at the top of the script:

```javascript
const CONFIG = {
    delayBetweenSaves: 2000,  // Increase if you get rate limited (in milliseconds)
    maxToSave: null,           // Set to a number like 50 to save only first 50
    scrollFirst: true,         // Set to false to skip auto-scrolling
    maxScrolls: 10             // Number of scroll attempts
};
```

---

## Troubleshooting

### "Could not find save buttons"
The page structure may be different. To fix:

1. Right-click on any "Save" button → Inspect
2. Find the button element's HTML
3. Look for unique class names or attributes
4. Update the `findSaveButtons()` function in the script

Example:
```javascript
// If buttons have class "match-save-btn"
buttons = document.querySelectorAll('.match-save-btn');
```

### "Rate limited" or errors
Increase the delay:
```javascript
delayBetweenSaves: 5000,  // 5 seconds instead of 2
```

### Script stops early
Some matches might already be saved, or there's an error. Check the console messages.

---

## Important Notes

⚠️ **Warnings:**
- This automation may violate Instrumentl's Terms of Service
- Your account could be suspended
- Use reasonable delays (2+ seconds)
- Don't run this repeatedly in a short time period

✅ **Advantages over Selenium:**
- No installation required
- Works in any browser
- Easy to modify on the fly
- Can pause/stop anytime

---

## Alternative: Manually with Keyboard

If you don't want to use any scripts:

1. Scroll through matches page
2. Press `Tab` to move between buttons
3. Press `Space` or `Enter` to click Save
4. Repeat (tedious but safest)

---

## Better Solution: Contact Instrumentl

Instead of automating, ask Instrumentl support for:
1. Bulk save feature
2. "Save all matches" button
3. API endpoint for project matches
4. CSV export of matches

Email: hello@instrumentl.com
