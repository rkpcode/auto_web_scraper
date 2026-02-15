"""
Hugging Face Spaces - Gradio Interface for Video Scraper
Deploy this on Hugging Face Spaces for web-based scraping
"""
import gradio as gr
import sys
import os
from pathlib import Path

# Add video_engine to path
sys.path.insert(0, str(Path(__file__).parent / "video_engine"))

from video_engine.database import db
from video_engine.harvester import harvest_and_save
from video_engine.main import process_video
from concurrent.futures import ThreadPoolExecutor, as_completed


def scrape_website(website_url, discovery_method, max_pages, max_workers):
    """
    Main scraping function for Gradio interface.
    
    Args:
        website_url: Website to scrape
        discovery_method: auto/sitemap/generic
        max_pages: Maximum pages to crawl
        max_workers: Number of concurrent workers
    
    Returns:
        Status message and statistics
    """
    try:
        # Initialize database
        db._init_db()
        
        # Reset stale statuses
        stale_count = db.reset_stale_statuses()
        status_msg = f"[INFO] Reset {stale_count} stale statuses\n" if stale_count > 0 else ""
        
        # Discover videos
        status_msg += f"[INFO] Discovering videos from: {website_url}\n"
        status_msg += f"[INFO] Method: {discovery_method}, Max pages: {max_pages}\n"
        
        new_count = harvest_and_save(website_url, method=discovery_method, max_pages=int(max_pages))
        status_msg += f"[SUCCESS] Discovered {new_count} new video URLs\n\n"
        
        if new_count == 0:
            status_msg += "[WARNING] No new videos found. Check if website has videos.\n"
            return status_msg, get_stats_table()
        
        # Get pending URLs
        pending_urls = db.get_pending_urls()
        status_msg += f"[INFO] Processing {len(pending_urls)} videos with {max_workers} workers\n\n"
        
        # Process videos
        completed = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=int(max_workers)) as executor:
            futures = {executor.submit(process_video, url): url for url in pending_urls}
            
            for i, future in enumerate(as_completed(futures), 1):
                url = futures[future]
                try:
                    future.result()
                    completed += 1
                    status_msg += f"[OK] [{i}/{len(pending_urls)}] Processed successfully\n"
                except Exception as e:
                    failed += 1
                    status_msg += f"[FAIL] [{i}/{len(pending_urls)}] Error: {str(e)[:50]}\n"
        
        # Final stats
        status_msg += f"\n[COMPLETE] Finished processing!\n"
        status_msg += f"[STATS] Completed: {completed}, Failed: {failed}\n"
        
        return status_msg, get_stats_table()
        
    except Exception as e:
        return f"[ERROR] Fatal error: {str(e)}", get_stats_table()


def get_stats_table():
    """Get database statistics as formatted table."""
    try:
        stats = db.get_stats()
        if not stats:
            return "No videos in database yet."
        
        table = "| Status | Count |\n|--------|-------|\n"
        for status, count in stats.items():
            table += f"| {status} | {count} |\n"
        
        return table
    except:
        return "Unable to fetch statistics."


def view_database():
    """View current database statistics."""
    return get_stats_table()


# Gradio Interface
with gr.Blocks(title="Video Scraper Pipeline", theme=gr.themes.Soft()) as app:
    gr.Markdown("""
    # 🎬 Video Scraper Pipeline
    
    Automatically discover, download, and upload videos to Bunny Stream from any website.
    
    **How it works:**
    1. Enter a website URL
    2. Choose discovery method
    3. Click "Start Scraping"
    4. Videos will be downloaded and uploaded to Bunny Stream
    
    **Note:** Make sure to set `BUNNY_API_KEY` and `BUNNY_LIBRARY_ID` in Hugging Face Spaces secrets.
    """)
    
    with gr.Tab("Scrape Website"):
        with gr.Row():
            with gr.Column():
                website_input = gr.Textbox(
                    label="Website URL",
                    placeholder="https://example.com",
                    info="Enter the website URL to scrape videos from"
                )
                
                discovery_method = gr.Radio(
                    choices=["auto", "sitemap", "generic"],
                    value="auto",
                    label="Discovery Method",
                    info="auto: Try sitemap first, then crawl | sitemap: Sitemap only | generic: Generic crawling"
                )
                
                with gr.Row():
                    max_pages = gr.Slider(
                        minimum=1,
                        maximum=100,
                        value=10,
                        step=1,
                        label="Max Pages to Crawl",
                        info="Maximum number of pages to crawl (for auto/generic methods)"
                    )
                    
                    max_workers = gr.Slider(
                        minimum=1,
                        maximum=4,
                        value=2,
                        step=1,
                        label="Workers",
                        info="Number of concurrent downloads (2 recommended for Spaces)"
                    )
                
                scrape_btn = gr.Button("🚀 Start Scraping", variant="primary", size="lg")
            
            with gr.Column():
                output_log = gr.Textbox(
                    label="Processing Log",
                    lines=20,
                    max_lines=30,
                    interactive=False
                )
                
                stats_output = gr.Markdown(label="Database Statistics")
        
        scrape_btn.click(
            fn=scrape_website,
            inputs=[website_input, discovery_method, max_pages, max_workers],
            outputs=[output_log, stats_output]
        )
    
    with gr.Tab("View Database"):
        gr.Markdown("### Current Database Statistics")
        db_stats = gr.Markdown()
        refresh_btn = gr.Button("🔄 Refresh Statistics")
        
        refresh_btn.click(
            fn=view_database,
            outputs=db_stats
        )
    
    with gr.Tab("Documentation"):
        gr.Markdown("""
        ## 📖 Documentation
        
        ### Setup
        
        1. **Set Environment Variables** in Hugging Face Spaces Settings:
           - `BUNNY_API_KEY`: Your Bunny Stream API key
           - `BUNNY_LIBRARY_ID`: Your Bunny Stream library ID
        
        2. **Discovery Methods:**
           - **Auto**: Tries sitemap first, falls back to crawling
           - **Sitemap**: Only uses sitemap.xml
           - **Generic**: Crawls pages looking for video links
        
        3. **Workers**: Number of concurrent downloads (2 recommended for Spaces)
        
        ### Video Status Flow
        
        ```
        PENDING → EXTRACTING → DOWNLOADING → UPLOADING → COMPLETED
                                                      ↓
                                                   FAILED
        ```
        
        ### Troubleshooting
        
        - **No videos discovered**: Check if website has videos or try different method
        - **Timeout errors**: Some websites block automated access
        - **Database locked**: Refresh the page and try again
        
        ### Limitations
        
        - Hugging Face Spaces has 16GB RAM limit
        - Sessions timeout after inactivity
        - Storage limited to 50GB
        
        ### GitHub Repository
        
        [View Source Code](https://github.com/your-repo/video-scraper)
        """)


if __name__ == "__main__":
    app.launch()
