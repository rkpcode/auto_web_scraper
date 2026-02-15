# Interactive Video Scraper

Simple interactive CLI for scraping videos from websites.

## Usage

```bash
python interactive_pipeline.py
```

## Features

- **User-friendly prompts**: Just enter website URL
- **Auto-discovery**: Automatically finds video URLs
- **Confirmation**: Shows discovered URLs before processing
- **Real-time stats**: Displays progress and final statistics
- **Multiple websites**: Process multiple sites in one session

## Example Session

```
============================================================
  VIDEO SCRAPER - Interactive Mode
============================================================

Enter website URL to scrape (or 'quit' to exit):
Example: https://example.com

> viralkand.com

Target: https://viralkand.com

Harvester Options:
1. Auto (try sitemap first, then crawl)
2. Sitemap only
3. Generic crawl

Select method [1-3] (default: 1): 1
Max pages to crawl (default: 10): 20

Method: auto
Max Pages: 20

Starting URL discovery...
============================================================
[HARVESTER] Found sitemap: https://viralkand.com/sitemap.xml
[HARVESTER] Discovery complete: 150 video URLs found
============================================================

Discovered 150 new URLs

Discovered 150 video URLs:
------------------------------------------------------------
1. https://viralkand.com/video-1/
2. https://viralkand.com/video-2/
3. https://viralkand.com/video-3/
4. https://viralkand.com/video-4/
5. https://viralkand.com/video-5/
... and 145 more
------------------------------------------------------------

Proceed with download? [Y/n]: y

Starting pipeline...
============================================================
[Pipeline processing...]
============================================================

Pipeline completed successfully!

Final Statistics:
------------------------------------------------------------
COMPLETED: 145
FAILED: 5
------------------------------------------------------------

All done! ✓

============================================================
Process another website? [Y/n]: n

Exiting...
```

## Options

### Harvester Methods
1. **Auto** (Recommended): Tries sitemap first, falls back to crawling
2. **Sitemap only**: Fast but only works if site has sitemap
3. **Generic crawl**: Slower but more thorough

### Max Pages
- Controls how many pages to crawl (for generic method)
- Default: 10
- Higher = more URLs but slower

## Notes

- URLs are automatically prefixed with `https://` if missing
- Type `quit`, `exit`, or `q` to exit
- Press `Ctrl+C` to interrupt at any time
- All discovered URLs are saved to database
- You can skip processing by answering `n` to confirmation
