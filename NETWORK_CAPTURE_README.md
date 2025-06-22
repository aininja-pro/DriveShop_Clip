# CreatorIQ Network Capture Tools

This directory contains tools for performing full network capture of CreatorIQ to identify the API endpoints containing post data.

## 🎯 Goal

CreatorIQ uses React virtualized lists that only show ~15 posts in the DOM at any time, even though the full dataset contains 643 posts. We need to find the API endpoint that loads all the post data.

## 🛠 Tools

### 1. `test_network_capture.py`
**Purpose**: Capture ALL network requests made by CreatorIQ during page load and scrolling.

**Usage**:
```bash
python test_network_capture.py
```

**What it does**:
- Loads the CreatorIQ URL in Playwright
- Captures every single network request (no filtering)
- Saves all JSON responses to `data/network_dumps_debug/`
- Logs request URLs, status codes, and content types
- Identifies large JSON responses (potential post data)

### 2. `analyze_network_dumps.py`
**Purpose**: Analyze captured JSON files to identify which one contains the post data.

**Usage**:
```bash
python analyze_network_dumps.py
```

**What it does**:
- Scans all JSON files in network dumps directories
- Analyzes file sizes and content structure
- Identifies files with post/content/media indicators
- Highlights large files (>10KB) that likely contain post data
- Provides summary and next steps

## 📋 Process

1. **Run Network Capture**:
   ```bash
   python test_network_capture.py
   ```
   - Enter your CreatorIQ campaign report URL when prompted
   - Wait for capture to complete (~2-3 minutes)

2. **Analyze Results**:
   ```bash
   python analyze_network_dumps.py
   ```
   - Review the analysis output
   - Look for large JSON files (🔥 or 🎯 indicators)
   - Check files marked with ⭐ (potential post data)

3. **Manual Investigation**:
   - Open the largest JSON files in a text editor
   - Look for arrays with ~643 items (expected post count)
   - Identify the URL pattern for the correct endpoint

4. **Update Scraper**:
   - Once the correct API endpoint is identified, update the scraper to use it directly
   - This will bypass the DOM virtualization issue

## 🔍 What We're Looking For

- **Large JSON responses** (>50KB) that might contain all 643 posts
- **API endpoints** with URLs containing terms like:
  - `/api/campaigns/*/posts`
  - `/api/reports/*/activities`
  - `/api/content/`
  - `/graphql` (if using GraphQL)
- **JSON structure** with arrays containing post objects with fields like:
  - `url`, `caption`, `engagement`, `metrics`, etc.

## 📁 Output Directories

- `data/network_dumps/` - JSON files from integrated scraper
- `data/network_dumps_debug/` - JSON files from standalone test script

## 🚨 Expected Results

We expect to find:
- **30-100 total network requests** during page load and scrolling
- **5-15 JSON responses** saved to disk
- **1-3 large JSON files** containing the actual post data
- **The correct API endpoint URL** to use for direct data access

## 🔧 Troubleshooting

**No JSON files captured?**
- Check if the CreatorIQ URL is correct and accessible
- Verify you're logged into CreatorIQ in your browser
- Try running with a different URL or campaign

**Only small JSON files?**
- The post data might be loaded on initial page load, not during scrolling
- Check the very first few captured requests
- Look for GraphQL endpoints or batch API calls

**Analysis shows no potential post files?**
- Manually examine the largest files regardless of content indicators
- The post data structure might not match our search terms
- Look for any arrays with 600+ items 