"""
Gradio App for Video Scraper Pipeline (HF Spaces Compatible)
Two-Phase Model: Discovery (Harvester) + Processing (Workers)

Features:
- Non-blocking UI using threading
- Live stats refresh every 5 seconds
- Supabase (PostgreSQL) for persistent state
- Optimized for HF Spaces (16GB RAM limit)
"""
import gradio as gr
import sys
import os
from pathlib import Path
import threading
import time
import subprocess

# Add video_engine to path
sys.path.insert(0, str(Path(__file__).parent / "video_engine"))

# Ensure Playwright is installed on HF Spaces
if os.getenv("SPACE_ID") and not os.path.exists("/home/user/.cache/ms-playwright"):
    print("🔧 Installing Playwright Chromium...")
    subprocess.run(["playwright", "install", "chromium"], check=True)

# FIX for Gradio Auth on HF Spaces: Prevent requests from routing localhost through HF proxies
os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"

from database_supabase import db
from harvester import harvest_and_save
from pipeline_runner import process_video
from config import MAX_WORKERS, DEFAULT_MAX_PAGES, UPLOAD_PROVIDER
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================================
# GLOBAL STATE (Thread-safe)
# ============================================================================
class PipelineState:
    """Thread-safe state management for Gradio UI."""
    def __init__(self):
        self.discovery_running = False
        self.processing_running = False
        self.backfill_running = False
        self.discovery_stats = {}
        self.processing_stats = {'completed': 0, 'failed': 0}
        self.lock = threading.Lock()
    
    def set_discovery_running(self, running):
        with self.lock:
            self.discovery_running = running
    
    def set_processing_running(self, running):
        with self.lock:
            self.processing_running = running
            
    def set_backfill_running(self, running):
        with self.lock:
            self.backfill_running = running
    
    def update_discovery_stats(self, stats):
        with self.lock:
            self.discovery_stats = stats
    
    def update_processing_stats(self, completed, failed):
        with self.lock:
            self.processing_stats = {'completed': completed, 'failed': failed}
    
    def get_state(self):
        with self.lock:
            return {
                'discovery_running': self.discovery_running,
                'processing_running': self.processing_running,
                'backfill_running': self.backfill_running,
                'discovery_stats': self.discovery_stats.copy(),
                'processing_stats': self.processing_stats.copy()
            }


state = PipelineState()


# ============================================================================
# PHASE A: DISCOVERY (Background Thread)
# ============================================================================
def run_discovery_background(website_url, max_pages, start_page=1):
    """Run harvester in background thread."""
    try:
        state.set_discovery_running(True)
        print(f"[DISCOVERY] Starting: {website_url}, max_pages={max_pages}, start_page={start_page}")
        
        # Run harvester
        stats = harvest_and_save(website_url, method='pagination', max_pages=max_pages, start_page=start_page)
        state.update_discovery_stats(stats)
        
        print(f"[DISCOVERY] Complete: {stats}")
    except Exception as e:
        print(f"[DISCOVERY] Error: {e}")
        state.update_discovery_stats({'error': str(e)})
    finally:
        state.set_discovery_running(False)
        # CRITICAL: Close any browser instances to free RAM
        print("[DISCOVERY] Cleanup complete")


def start_discovery(website_url, max_pages, start_page):
    """Start discovery phase (non-blocking)."""
    if state.discovery_running:
        return "⚠️ Discovery already running. Please wait..."
    
    if not website_url:
        return "❌ Please enter a website URL"
    
    # Start background thread
    thread = threading.Thread(
        target=run_discovery_background,
        args=(website_url, int(max_pages), int(start_page)),
        daemon=True
    )
    thread.start()
    
    return f"🔍 Discovery started for: {website_url} (Page {start_page}-{int(start_page)+int(max_pages)-1})\nCheck stats below for progress..."


# ============================================================================
# PHASE B: PROCESSING (Background Thread)
# ============================================================================
def run_processing_background(max_workers):
    """Run video processing in background thread."""
    try:
        state.set_processing_running(True)
        print(f"[PROCESSING] Starting with {max_workers} workers")
        
        # Reset stale statuses
        stale_count = db.reset_stale_statuses()
        if stale_count > 0:
            print(f"[PROCESSING] Reset {stale_count} stale videos")
        
        # Get pending URLs (including completed videos on other providers)
        import config
        pending_urls = db.get_pending_videos(current_provider=config.UPLOAD_PROVIDER)
        
        if not pending_urls:
            print("[PROCESSING] No pending URLs")
            return
        
        print(f"[PROCESSING] Processing {len(pending_urls)} videos")
        
        # Process concurrently
        completed = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_video, url): url for url in pending_urls}
            
            for future in as_completed(futures):
                if getattr(config, "STOP_PROCESSING", False):
                    print("[PROCESSING] Stop requested! Cancelling unstarted tasks...")
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    break
                try:
                    future.result()
                    completed += 1
                except Exception:
                    failed += 1
                
                # Update stats periodically
                state.update_processing_stats(completed, failed)
        
        if getattr(config, "STOP_PROCESSING", False):
            print(f"[PROCESSING] Stopped. {completed} succeeded, {failed} failed, remainder cancelled.")
        else:
            print(f"[PROCESSING] Complete: {completed} succeeded, {failed} failed")
    except Exception as e:
        print(f"[PROCESSING] Error: {e}")
    finally:
        state.set_processing_running(False)


def start_processing():
    """Start processing phase (non-blocking)."""
    if state.processing_running:
        return "⚠️ Processing already running. Please wait..."
    
    import config
    config.STOP_PROCESSING = False  # Reset stop signal on start
    
    # Check if there are pending videos (including completed videos on other providers)
    pending_count = len(db.get_pending_videos(current_provider=config.UPLOAD_PROVIDER))
    if pending_count == 0:
        return "❌ No pending videos to process. Run discovery first."
    
    # Start background thread
    thread = threading.Thread(
        target=run_processing_background,
        args=(MAX_WORKERS,),
        daemon=True
    )
    thread.start()
    
    return f"🚀 Processing started for {pending_count} videos with {MAX_WORKERS} workers...\nCheck stats below for progress..."


def stop_processing():
    """Stop processing phase (non-blocking)."""
    if not state.processing_running:
        return "⚠️ Processing is not currently running."
    
    import config
    config.STOP_PROCESSING = True
    return "🛑 Stop signal sent! Active worker tasks will finish their current video download/upload step, and then the pipeline will stop gracefully."


def change_upload_provider(provider):
    """Dynamically switch the upload provider in config."""
    import config
    prov = provider.strip().lower()
    if prov == "streamwish":
        prov = "seekstreaming"
    config.UPLOAD_PROVIDER = prov
    return f"🔄 Active upload provider successfully changed to: {prov.upper()}!"


def run_ui_maintenance():
    """Run database maintenance: clean failed videos and reset stuck tasks."""
    try:
        deleted = db.clean_failed_videos()
        reset = db.reset_stale_statuses()
        return f"✅ Maintenance Complete!\n- Removed {deleted} failed videos.\n- Reset {reset} stuck/zombie tasks to PENDING."
    except Exception as e:
        return f"❌ Maintenance failed: {str(e)}"
        
def run_db_migration():
    """Manually run database migration to add missing columns."""
    try:
        from database_supabase import db
        with db.get_cursor() as cursor:
            # 1. Terminate other connections to release any active locks
            try:
                cursor.execute("""
                    SELECT pg_terminate_backend(pid) 
                    FROM pg_stat_activity 
                    WHERE pid <> pg_backend_pid() 
                      AND usename = current_user;
                """)
                terminated = cursor.rowcount
                print(f"[MIGRATION] Terminated {terminated} other database connections to release locks.")
            except Exception as lock_err:
                print(f"[MIGRATION] Could not terminate other connections: {lock_err}")
                
            # 2. Run the ALTER TABLE statement
            cursor.execute("""
                ALTER TABLE videos 
                ADD COLUMN IF NOT EXISTS upload_provider TEXT,
                ADD COLUMN IF NOT EXISTS upload_id TEXT,
                ADD COLUMN IF NOT EXISTS doodstream_id TEXT,
                ADD COLUMN IF NOT EXISTS seekstreaming_id TEXT,
                ADD COLUMN IF NOT EXISTS lulustream_id TEXT,
                ADD COLUMN IF NOT EXISTS title TEXT,
                ADD COLUMN IF NOT EXISTS description TEXT,
                ADD COLUMN IF NOT EXISTS unique_id TEXT,
                ADD COLUMN IF NOT EXISTS metadata_synced BOOLEAN DEFAULT FALSE
            """)
            
            # 3. Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON videos(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON videos(created_at)")
            
        return "✅ Database migration ran successfully! All missing columns (including metadata_synced) have been added after releasing active locks."
    except Exception as e:
        return f"❌ Database migration failed: {str(e)}"

def run_backfill_background():
    """Background worker for metadata backfill."""
    try:
        state.set_backfill_running(True)
        print("[BACKFILL] Starting metadata backfill in background...")
        
        # Import and run directly to avoid DB connection timeouts that happen in subprocesses
        from video_engine.backfill_metadata import main as backfill_main
        backfill_main()
        
        print("[BACKFILL] ✅ Completed successfully!")
    except Exception as e:
        print(f"[BACKFILL] ❌ Error: {str(e)}")
    finally:
        state.set_backfill_running(False)

def run_metadata_backfill():
    """Start metadata backfill phase (non-blocking)."""
    if state.backfill_running:
        return "⚠️ Backfill is already running in the background. Please wait..."
        
    thread = threading.Thread(
        target=run_backfill_background,
        daemon=True
    )
    thread.start()
    
    return "🔄 Metadata Backfill started in the background!\nYou can safely close this window. Check Hugging Face Space Logs for detailed progress."


# ============================================================================
# DATA EXPLORER REFRESH
# ============================================================================
def get_recent_data():
    """Fetch recent videos for Data Explorer."""
    try:
        videos = db.get_recent_videos(limit=50)
        if not videos:
            return [["No data", "", "", "", "", "", ""]]
        
        # Convert list of dicts to list of lists for Gradio Dataframe
        headers = ["Title", "SeekStreaming", "DoodStream", "LuluStream", "Completed At", "URL", "Description"]
        data = []
        for v in videos:
            data.append([
                v["Title"], 
                v["SeekStreaming"], 
                v["DoodStream"], 
                v["LuluStream"], 
                v["Completed At"], 
                v["URL"], 
                v["Description"]
            ])
        return data
    except Exception as e:
        print(f"Error fetching recent data: {e}")
        return [["Error", str(e), "", "", "", "", ""]]

# ============================================================================
# STATS REFRESH (Called every 5 seconds)
# ============================================================================
def get_live_stats():
    """Get current database stats for dashboard."""
    try:
        db_stats = db.get_stats(provider=None)
        total = db.get_total_count()
        provider_stats = db.get_provider_stats()
        
        current_state = state.get_state()
        
        # Build stats table
        stats_md = "### 📊 Global Database Statistics\n\n"
        stats_md += "### 📊 Database Statistics\n\n"
        stats_md += "| Status | Count |\n|--------|-------|\n"
        
        for status, count in sorted(db_stats.items()):
            stats_md += f"| {status} | {count} |\n"
        
        stats_md += f"| **TOTAL** | **{total}** |\n\n"
        
        # Provider-wise upload stats
        if provider_stats:
            provider_icons = {
                'doodstream': '🟢',
                'seekstreaming': '🔵', 
                'lulustream': '🟣',
                'bunny': '🟠',
                'unknown': '⚪'
            }
            
            stats_md += "### 🏢 Provider-wise Uploads\n\n"
            stats_md += "| Provider | Completed |\n|----------|----------|\n"
            
            total_uploaded = 0
            for provider, count in provider_stats.items():
                icon = provider_icons.get(provider, '⚪')
                stats_md += f"| {icon} {provider.upper()} | {count} |\n"
                total_uploaded += count
            
            stats_md += f"| **TOTAL UPLOADED** | **{total_uploaded}** |\n\n"
        
        # Add phase status
        stats_md += "### 🔄 Pipeline Status\n\n"
        
        if current_state['discovery_running']:
            stats_md += "🔍 **Discovery:** Running...\n\n"
        elif current_state['discovery_stats']:
            stats = current_state['discovery_stats']
            if 'error' in stats:
                stats_md += f"❌ **Discovery:** Error - {stats['error']}\n\n"
            else:
                stats_md += f"✅ **Discovery:** Complete ({stats.get('links_found', 0)} links found, {stats.get('links_added', 0)} new)\n\n"
        
        if current_state['processing_running']:
            proc_stats = current_state['processing_stats']
            stats_md += f"🚀 **Processing:** Running (✅ {proc_stats['completed']} | ❌ {proc_stats['failed']})\n\n"
        
        return stats_md
    except Exception as e:
        return f"❌ Error fetching stats: {str(e)}"


# ============================================================================
# GRADIO INTERFACE
# ============================================================================
with gr.Blocks(title="Video Scraper Pipeline", theme=gr.themes.Soft()) as app:
    app_password = os.getenv("APP_PASSWORD")
    
    with gr.Group(visible=bool(app_password)) as login_group:
        gr.Markdown("# 🔒 Login Required")
        gr.Markdown("Please enter the password to access the Video Scraper Pipeline.")
        pwd_input = gr.Textbox(type="password", label="Password")
        login_btn = gr.Button("Login", variant="primary")
        login_error = gr.Markdown("", visible=False)
        
    with gr.Group(visible=not bool(app_password)) as main_app_group:
        gr.Markdown("""
        # 🎬 Video Scraper Pipeline (Two-Phase Model)
        
        **Phase A:** Discovery - Harvester scans pages and seeds database  
        **Phase B:** Processing - Workers download and sequentially upload videos to **Doodstream, Seekstreaming, and Lulustream**  
        
        **Database:** Supabase (PostgreSQL) - State persists across restarts  
        **Workers:** {workers} (Optimized for HF Spaces 16GB RAM)
        """.format(workers=MAX_WORKERS))
    
        with gr.Tabs():
            with gr.Tab("Dashboard"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("## 🔍 Phase A: Discovery")
                
                        website_input = gr.Textbox(
                            label="Website URL",
                            placeholder="https://example.com",
                            info="Enter the website to scrape videos from"
                        )
                
                        max_pages_slider = gr.Slider(
                            minimum=0,
                            maximum=20,
                            value=0,
                            step=1,
                            label="Max Pages to Crawl (0 = Unlimited)",
                            info="Set to 0 to scrape till the last page (auto-stops when no new links found)"
                        )
                
                        start_page_slider = gr.Slider(
                            minimum=1,
                            maximum=100,
                            value=1,
                            step=1,
                            label="Start Page Number",
                            info="Useful for resuming or skipping initial pages"
                        )
                
                        discovery_btn = gr.Button("🔍 Start Discovery", variant="primary", size="lg")
                        discovery_output = gr.Textbox(label="Discovery Status", lines=3, interactive=False)
                
                        gr.Markdown("---")
                        gr.Markdown("## 🚀 Phase B: Processing")
                
                        gr.Markdown("ℹ️ **Multi-Upload Mode:** Videos will be sequentially uploaded to Doodstream, Seekstreaming, and Lulustream and linked with a unique ID.")
                
                        with gr.Row():
                            processing_btn = gr.Button("🚀 Start Processing", variant="primary", size="lg")
                            stop_btn = gr.Button("🛑 Stop Processing", variant="stop", size="lg")
                        processing_output = gr.Textbox(label="Processing Status", lines=3, interactive=False)
                
                        gr.Markdown("---")
                        gr.Markdown("## 🛠️ Database & Metadata Maintenance")
                        with gr.Row():
                            maintenance_btn = gr.Button("🧹 Clean Failed Videos & Reset Stuck Tasks", variant="stop")
                            backfill_btn = gr.Button("🔄 Run Metadata Backfill (Title/Desc/UUID)", variant="secondary")
                            db_migration_btn = gr.Button("🔧 Run DB Migration", variant="secondary")
                        maintenance_output = gr.Textbox(label="Maintenance / Logs", lines=5, interactive=False)
            
                    with gr.Column(scale=1):
                        gr.Markdown("## 📊 Live Dashboard")
                        stats_display = gr.Markdown(value=get_live_stats())
                
                        refresh_btn = gr.Button("🔄 Refresh Stats")
        
        # Event handlers
        discovery_btn.click(
            fn=start_discovery,
            inputs=[website_input, max_pages_slider, start_page_slider],
            outputs=discovery_output
        )
        
        processing_btn.click(
            fn=start_processing,
            outputs=processing_output
        )
        
        stop_btn.click(
            fn=stop_processing,
            outputs=processing_output
        )
        
        maintenance_btn.click(
            fn=run_ui_maintenance,
            outputs=maintenance_output
        )
        
        backfill_btn.click(
            fn=run_metadata_backfill,
            outputs=maintenance_output
        )
        
        db_migration_btn.click(
            fn=run_db_migration,
            outputs=maintenance_output
        )
        
        refresh_btn.click(
            fn=get_live_stats,
            outputs=stats_display
        )
        
        # Auto-refresh stats every 5 seconds
        timer = gr.Timer(5)
        timer.tick(get_live_stats, outputs=stats_display)
        
        with gr.Tab("Data Explorer"):
            gr.Markdown("## 🗃️ Recently Processed Videos")
            gr.Markdown("View the latest extracted videos, their generated SEO Titles and Descriptions, and the IDs from SeekStreaming, DoodStream, and LuluStream.")
            
            data_grid = gr.Dataframe(
                headers=["Title", "SeekStreaming", "DoodStream", "LuluStream", "Completed At", "URL", "Description"],
                datatype=["str", "str", "str", "str", "str", "str", "str"],
                value=get_recent_data(),
                interactive=False,
                wrap=True
            )
            refresh_data_btn = gr.Button("🔄 Refresh Data", variant="primary")
            refresh_data_btn.click(fn=get_recent_data, outputs=data_grid)
        
        with gr.Tab("Documentation"):
            gr.Markdown("""
                ## 📖 Setup Instructions
            
            ### 1. Environment Variables (HF Spaces Secrets)
            
            - `DATABASE_URL`: Supabase connection string (PostgreSQL)
            - `UPLOAD_PROVIDER`: Selected video upload provider (`doodstream` (default), `seekstreaming`, `lulustream`, or `bunny`)
            - `DOODSTREAM_API_KEY`: DoodStream API key (and optional `DOODSTREAM_BASE_URL`)
            - `SEEKSTREAMING_API_KEY`: SeekStreaming API key (and optional `SEEKSTREAMING_BASE_URL`)
            - `LULUSTREAM_API_KEY`: LuluStream API key (and optional `LULUSTREAM_BASE_URL`)
            - `BUNNY_API_KEY`: Bunny Stream API key (optional)
            - `BUNNY_LIBRARY_ID`: Bunny Stream library ID (optional)
            
            ### 2. How It Works
            
            **Phase A (Discovery):**
            1. Enter website URL
            2. Harvester crawls pages using pagination (?page=n)
            3. Auto-stops when no new links found
            4. Seeds URLs to Supabase database
            
            **Phase B (Processing):**
            1. Fetches PENDING videos from database
            2. Downloads using yt-dlp
            3. Uploads to the selected active provider
            4. Updates status to COMPLETED
            
            ### 3. Memory Management
            
            **HF Spaces Free Tier: 16GB RAM**
            
            - Gradio App: ~1GB
            - Harvester (Playwright): ~800MB
            - Workers (2): ~1GB
            - **Total:** ~2.8GB (Safe)
            
            ⚠️ **CRITICAL:** Discovery and Processing run separately to avoid OOM crashes.
            
            ### 4. Troubleshooting
            
            - **"Too many clients"**: Supabase connection leak. Restart the Space.
            - **Exit Code 137**: Out of Memory. Reduce MAX_WORKERS or run phases separately.
            - **No links found**: Check if website has videos or try different URL.
            
            ### 5. Database Persistence
            
            Supabase ensures your progress is saved even if HF Space restarts. You can resume processing anytime.
            """)
    

    # Login logic
    def verify_login(pwd):
        if pwd == app_password:
            return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
        else:
            return gr.update(), gr.update(), gr.update(value="❌ **Incorrect password**", visible=True)
            
    login_btn.click(
        verify_login,
        inputs=[pwd_input],
        outputs=[login_group, main_app_group, login_error]
    )

if __name__ == "__main__":
    # Initialize database on startup
    print("🔧 Initializing Supabase connection...")
    try:
        db._init_db()
        print("✅ Database ready")
    except Exception as e:
        print(f"❌ Database error: {e}")
    
    app.launch(server_name="0.0.0.0")
