# Grant Matcher - All Results Version

## What Changed

I've modified your grant matcher to help you extract **ALL** matches for your project, not just 39.

### Key Changes:

1. **Lower Default Minimum Score**: Changed from `0.1` (10%) to `0.01` (1%)
   - Your original 39 results were ALL the grants scoring above 10% similarity
   - Most grants score between 1-10%, which is still relevant

2. **Default to ALL Matches**: Changed `top_matches` default from `100` to `0`
   - Setting `top_matches = 0` means "return ALL matches above the minimum score"
   - You can still set a specific number if you want only the top N matches

3. **Better Status Messages**: Added detailed scoring information
   - Shows total grants analyzed vs. matches found
   - Displays score range of your matches
   - Prints statistics to console

4. **Helpful UI Guidance**: Added an info box explaining:
   - How to get all matches (set top matches to 0)
   - Why you might want to lower the minimum score
   - That even low scores (2-5%) can be relevant matches

## How to Get All Matches

### In the Application:

1. **Step 4: Matching Settings**
   - Set **Top Matches** to `0` (this means "ALL matches")
   - Set **Min Score** to `0.01` (this is 1% - captures most grants)
   - Alternatively, try even lower like `0.005` (0.5%) to cast a wider net

2. **Click "RUN MATCHING"**

3. **Review Results**
   - You should now see many more matches
   - Check the console output for score statistics
   - Sort through results - even low-scoring grants might be relevant

### Understanding Match Scores:

- **0.10-0.50**: Very strong match - high keyword/concept overlap
- **0.05-0.10**: Good match - decent alignment with your documents  
- **0.02-0.05**: Moderate match - some relevant keywords/concepts
- **0.01-0.02**: Weak match - minimal but potentially relevant overlap
- **Below 0.01**: Very weak - likely not relevant

### Why You Were Only Getting 39 Results:

Your original settings were:
- `min_match_score = 0.1` (10%)
- This filtered out any grant with less than 10% similarity

The issue is that **most grants naturally score between 1-10%** because:
- Grant descriptions use varied terminology
- Your documents may not use exact same keywords
- TF-IDF scoring is conservative by design

**39 grants scoring above 10% is actually a sign your documents are working well!**

## Recommendations:

1. **Start with**: 
   - Min Score: `0.01`
   - Top Matches: `0`

2. **Review all results** and see the score distribution

3. **If you get too many results** (e.g., 500+):
   - Increase min score to `0.02` or `0.03`
   - Or set a reasonable top_matches number (e.g., 200)

4. **Export to Excel/CSV** and filter there:
   - You can sort by match score
   - Apply your own relevance criteria
   - Use Excel's filtering features

## Technical Note:

The matching algorithm uses TF-IDF (Term Frequency-Inverse Document Frequency) cosine similarity. This is a standard text similarity measure where:
- **1.0** = identical documents (impossible with different sources)
- **0.3+** = very high similarity (rare for different documents)
- **0.05-0.10** = normal good match
- **0.01-0.05** = weak but potentially relevant match
- **0.0** = no common meaningful words

Don't expect scores above 0.2-0.3 unless grants literally copy text from your documents!

## Files Included:

- `grant_matcher_all_results.py` - Modified version with lower thresholds
- `CHANGES.md` - This file

## Running the Fixed Version:

```bash
python grant_matcher_all_results.py
```

Make sure you have all the same dependencies installed as before.
