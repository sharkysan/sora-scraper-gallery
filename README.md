# Sora Library Scraper

A Python application to download images and prompts from your Sora library at https://sora.chatgpt.com/library.

## Features

- Downloads all images from your Sora library
- Extracts and saves prompts for each item
- Organizes downloads into separate folders for images and prompts
- Creates a summary JSON file with all extracted data
- Handles authentication through browser automation

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Note:** If you encounter a `greenlet` build error on Windows:
1. Install Visual C++ Build Tools (if missing)
2. Update pip, setuptools, and wheel: `python -m pip install --upgrade pip setuptools wheel`
3. Try installing greenlet separately first: `pip install greenlet`
4. Then install playwright: `pip install playwright`

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

## Usage

### Basic Usage

```bash
python scraper.py
```

### Custom Output Directory

```bash
python scraper.py --output my_downloads
```

### Limit Number of Images

Process only the first N images:

```bash
python scraper.py --limit 10
# or short form:
python scraper.py -l 10
```

If `--limit` is not specified, all images will be processed.

### Use Persistent Browser Context (Recommended)

Saves your login session and makes the browser look more authentic:

```bash
python scraper.py --persistent
```

This is especially helpful if you're getting "browser not secure" errors.

## How It Works

1. **Launch Browser**: The script opens a Chromium browser window
2. **Navigate to Library**: Automatically goes to https://sora.chatgpt.com/library
3. **Login**: You'll need to log in manually if not already logged in
4. **Extract Content**: Scrolls through your library and extracts all items
5. **Download**: Downloads images and saves prompts with metadata
6. **Organize**: Files are organized in the following structure:
   ```
   downloads/
   ├── images/
   │   ├── item_0001_20231215_123456.jpg
   │   └── item_0002_20231215_123456.png
   ├── prompts/
   │   ├── item_0001_20231215_123456.json
   │   └── item_0002_20231215_123456.json
   └── summary.json
   ```

## Output Format

### Image Files
- Saved in `downloads/images/` directory
- Named as `item_XXXX_YYYYMMDD_HHMMSS.{ext}`
- Supports JPG, PNG, WebP formats

### Prompt Files (JSON)
Each prompt is saved as a JSON file containing:
```json
{
  "id": 1,
  "prompt": "Your prompt text here...",
  "image_url": "https://...",
  "timestamp": "20231215_123456",
  "image_filename": "item_0001_20231215_123456.jpg"
}
```

### Summary File
`summary.json` contains all items with metadata and scrape information.

## Troubleshooting

### "Dieser Browser oder diese App ist unter Umständen nicht sicher" / "This browser or app may not be secure" (Browser not secure error)

This error (from Google sign-in or other services) means the browser is being detected as automated. Try these solutions:

1. **Use persistent browser context** (strongly recommended):
   ```bash
   python scraper.py --persistent
   ```
   This saves your login session and makes the browser look more authentic.

2. **Wait before logging in**: When the browser opens, wait 5-10 seconds before attempting to log in. This helps the browser "warm up" and appear more human-like.

3. **Try manual workaround**: 
   - If Google blocks the automated browser, try logging in with a different method (email instead of Google, or vice versa)
   - Use your regular browser to log in to https://sora.chatgpt.com/library first
   - Then use the persistent context for subsequent runs

4. **Clear browser data and retry**: Delete the `downloads/browser_data` folder and try again with `--persistent`

5. **Try different time**: Sometimes the error is temporary, try again later.

The scraper includes comprehensive stealth techniques to avoid detection, but Google and some sites are very aggressive with automated browser detection. Using `--persistent` is the best solution as it makes the browser look more like a regular user session.

### Browser doesn't open
- Make sure Playwright browsers are installed: `playwright install chromium`

### Can't find library items
- The page structure might have changed
- Check `downloads/page_debug.html` for the current page structure
- You may need to update the selectors in `scraper.py`

### Login issues / Login not visible

**If the login page is not visible or empty (especially on auth.openai.com):**

1. **Wait for page to load**: OpenAI auth pages use React/JavaScript and need time to render (5-10 seconds)
2. **Refresh the page**: If the page is empty, press **F5** to refresh it manually
3. **Check browser console**: Open DevTools (F12) and check for JavaScript errors
4. **Check console output**: The script will show the current URL and whether login elements were found
5. **Screenshot saved**: If login elements aren't found, a screenshot is saved to `downloads/login_debug.png`
6. **Try manual navigation**: Navigate directly to `https://sora.chatgpt.com/library` in the browser if needed
7. **Use persistent context**: Save your session with `--persistent` flag for future runs

**Common issue**: If `https://auth.openai.com/log-in-or-create-account` shows an empty page:
- This is usually because the JavaScript hasn't finished loading
- Wait 5-10 seconds or refresh the page (F5)
- The page should eventually load and show login options

**General login tips:**
- Make sure you complete the login process in the browser window
- The script will wait up to 5 minutes for login
- The browser window should automatically come to front and maximize
- After logging in, the script will detect the redirect to the library page

### Rate limiting
- If you encounter rate limits, wait a few minutes between runs
- The script includes delays to avoid aggressive scraping

## Notes

- This tool uses browser automation and requires manual login
- Downloads are saved locally on your computer
- Make sure you have sufficient disk space for images
- Respect OpenAI's terms of service when using this tool

## License

Use at your own discretion. This tool is not affiliated with OpenAI.

