# Instrumentl Grant Matcher

A desktop application that matches your organization's documents against grant opportunities from Instrumentl. No coding required!

## Features

- **Easy Setup**: Simple wizard-based interface - just click through the steps
- **Document Support**: Upload PDF, Word, Excel, PowerPoint, CSV, and text files
- **Smart Chunking**: Automatically breaks long documents into 500-word paragraphs for better matching
- **Local Processing**: All matching is done on your computer using TF-IDF text similarity (no AI services required)
- **Instrumentl Integration**: Connects to your Instrumentl account to fetch grant opportunities
- **Export Results**: Save matches to CSV or Excel for further analysis

## Quick Start

### Windows
1. Download and extract the application folder
2. Double-click `RUN_GRANT_MATCHER.bat`
3. First run will automatically install required dependencies

### Mac/Linux
1. Download and extract the application folder
2. Open Terminal and navigate to the folder
3. Run: `chmod +x run_grant_matcher.sh && ./run_grant_matcher.sh`
4. Or double-click `run_grant_matcher.sh` (may need to enable "Open with Terminal")

## Requirements

- **Python 3.8 or higher** - Download from [python.org](https://www.python.org/downloads/)
- **Instrumentl API Access** - Get your API key from your Instrumentl account

### Python Dependencies (auto-installed)
- pdfplumber
- pypdf
- python-docx
- python-pptx
- openpyxl
- pandas

## How to Use

### Step 1: API Setup
1. Log into your Instrumentl account
2. Go to **Integrations > API**
3. Generate a new API key
4. Copy the **API Key ID** and **Private Key** into the application
5. Click "Test Connection" to verify

### Step 2: Upload Documents
1. Click "Add Files" to upload individual documents
2. Or click "Add Folder" to add all supported files from a folder
3. Supported formats:
   - PDF (.pdf)
   - Word (.docx, .doc)
   - Excel (.xlsx, .xls)
   - PowerPoint (.pptx, .ppt)
   - CSV (.csv)
   - Text (.txt, .md)

### Step 3: Fetch Grants
1. Choose what to fetch:
   - **Saved Grants**: Grants already saved to your projects
   - **All Available Grants**: All grants in your account
2. Click "Fetch Grants from Instrumentl"
3. Wait for the download to complete

### Step 4: Run Matching
1. Adjust settings if needed:
   - **Minimum Match Score**: Lower = more results (default: 0.1)
   - **Maximum Results**: How many top matches to show (default: 20)
2. Click **▶ RUN MATCHING**
3. Wait for processing to complete

### Step 5: Review Results
- View matches ranked by relevance score
- Export to CSV or Excel for sharing or further analysis

## How the Matching Works

The application uses **TF-IDF (Term Frequency-Inverse Document Frequency)** text similarity to find relevant grants:

1. **Document Processing**: Your documents are read and split into ~500-word chunks
2. **Text Extraction**: Key terms are extracted from both your documents and grant descriptions
3. **Vectorization**: Each text is converted to a numerical vector based on word importance
4. **Similarity Scoring**: Cosine similarity measures how closely your documents match each grant
5. **Ranking**: Grants are sorted by match score, highest first

This approach:
- ✅ Works completely offline (no internet needed for matching)
- ✅ No AI services or API costs
- ✅ Fast processing
- ✅ Transparent scoring

## Tips for Better Matches

1. **Include descriptive documents** like mission statements, program descriptions, and past proposals
2. **More documents = better matching** - the system combines all your documents
3. **Lower the minimum score** if you're not getting enough results
4. **Use specific language** that matches grant terminology (funding, nonprofit, community, etc.)

## Troubleshooting

### "Python is not installed"
- Download Python from [python.org](https://www.python.org/downloads/)
- During installation, check "Add Python to PATH"

### "tkinter is not installed"
- **Windows**: Reinstall Python and check "tcl/tk" option
- **Mac**: Install Python from python.org (includes tkinter)
- **Linux**: `sudo apt-get install python3-tk`

### "Connection failed" when testing API
- Verify your API Key ID and Private Key are correct
- Check your Instrumentl account has API access enabled
- Ensure you have internet connection

### "No matches found"
- Lower the minimum match score (try 0.05 or 0.01)
- Add more descriptive documents
- Check that grants were fetched successfully

### Documents won't read
- Ensure files aren't password-protected
- Try converting to a different format (e.g., .docx to .txt)
- Check file isn't corrupted

## File Structure

```
instrumentl_matcher/
├── grant_matcher.py        # Main application
├── requirements.txt        # Python dependencies
├── RUN_GRANT_MATCHER.bat   # Windows launcher
├── run_grant_matcher.sh    # Mac/Linux launcher
├── README.md               # This file
└── config.json             # (created after first use) Saved settings
```

## Support

For issues with:
- **This application**: Contact your system administrator
- **Instrumentl API**: Email api@instrumentl.com
- **Instrumentl platform**: Visit [help.instrumentl.com](https://help.instrumentl.com)

## Privacy & Security

- Your API credentials are stored locally in `config.json`
- All document processing happens on your computer
- No data is sent to external AI services
- Only Instrumentl's API is contacted to fetch grant data

## License

This application is provided as-is for use with Instrumentl's grant management platform.
