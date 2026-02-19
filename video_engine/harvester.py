"""
Harvester Module - Auto-Discovery System
Automatically discovers video URLs from website homepages/sitemaps.

This transforms the pipeline from "Processing Engine" to "Auto-Scraper".
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from core.logger import logger
from video_engine.database_supabase import db
import time
import random
from collections import deque


class BaseHarvester:
    """
    Base class for site-specific harvesters.
    Discovers video page URLs from a website.
    """
    
    def __init__(self, base_url):
        """
        Args:
            base_url: Homepage or category page URL
        """
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.discovered_urls = set()
    
    def discover(self, max_pages=10):
        """
        Discover video URLs from the site.
        
        Args:
            max_pages: Maximum number of pages to crawl
            
        Returns:
            set: Discovered video page URLs
        """
        raise NotImplementedError("Subclasses must implement discover()")
    
    def is_video_page(self, url):
        """
        Check if URL is likely a video page.
        Override in subclass for site-specific logic.
        
        Args:
            url: URL to check
            
        Returns:
            bool: True if likely a video page
        """
        # Viralkand specific pattern: domain.com/post-slug/
        # Check if it's a deep link and not a category
        path = urlparse(url).path
        if not path or path == '/': return False
        
        # If path has a slug and is not excluded by filter_urls, treat as potential video page
        # The filter_urls method handles exclusion of /category/, /tag/, etc.
        return True
    
    def filter_urls(self, urls):
        """
        Filter and deduplicate URLs.
        
        Args:
            urls: List of URLs to filter
            
        Returns:
            set: Filtered unique URLs
        """
        filtered = set()
        
        for url in urls:
            # Skip if not from same domain
            if self.domain not in url:
                continue
            
            # Skip common non-video patterns
            skip_patterns = [
                '/category/', '/tag/', '/author/', '/page/',
                '/search/', '/login/', '/register/', '/contact/',
                '/dmca/', '/terms/', '/privacy/', '/about/',
                '/18-u-s-c/', '/compliance/', '/cookie/',
                '.jpg', '.png', '.gif', '.css', '.js'
            ]
            
            if any(pattern in url.lower() for pattern in skip_patterns):
                continue
            
            # Check if likely a video page
            if self.is_video_page(url):
                filtered.add(url)
        
        return filtered
    
    def save_to_database(self, urls):
        """
        Save discovered URLs to database as PENDING using batch insert.
        
        Args:
            urls: Set of URLs to save
            
        Returns:
            int: Number of new URLs added
        """
        if not urls:
            return 0
        
        logger.info(f"[HARVESTER] Saving {len(urls)} URLs to database (batch mode)...")
        
        # Use batch insert for better performance
        new_count = db.insert_videos_batch(urls, status='PENDING')
        
        logger.info(f"[HARVESTER] Successfully added {new_count} new URLs")
        return new_count


class GenericHarvester(BaseHarvester):
    """
    Generic harvester that works for many sites.
    Crawls homepage and category pages looking for video links.
    """
    
    def discover(self, max_pages=10):
        """
        Discover video URLs using generic crawling logic.
        
        Args:
            max_pages: Maximum pages to crawl
            
        Returns:
            set: Discovered video URLs
        """
        logger.info(f"[HARVESTER] Starting discovery from {self.base_url}")
        
        pages_to_crawl = [self.base_url]
        crawled_pages = set()
        
        while pages_to_crawl and len(crawled_pages) < max_pages:
            current_page = pages_to_crawl.pop(0)
            
            if current_page in crawled_pages:
                continue
            
            try:
                logger.info(f"[HARVESTER] Crawling page {len(crawled_pages)+1}/{max_pages}: {current_page}")
                
                # Fetch page
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                response = requests.get(current_page, headers=headers, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all links
                all_links = []
                for link in soup.find_all('a', href=True):
                    full_url = urljoin(current_page, link['href'])
                    all_links.append(full_url)
                
                # Filter for video pages
                video_urls = self.filter_urls(all_links)
                self.discovered_urls.update(video_urls)
                
                # Find pagination/category pages for further crawling
                pagination_patterns = ['/page/', '?page=', '/category/']
                for link in all_links:
                    if any(pattern in link for pattern in pagination_patterns):
                        if link not in crawled_pages and link not in pages_to_crawl:
                            pages_to_crawl.append(link)
                
                crawled_pages.add(current_page)
                
            except Exception as e:
                logger.error(f"[HARVESTER] Error crawling {current_page}: {e}")
                crawled_pages.add(current_page)  # Mark as crawled to avoid retry
        
        logger.info(f"[HARVESTER] Discovery complete: {len(self.discovered_urls)} video URLs found")
        return self.discovered_urls


class LinkHarvester(BaseHarvester):
    """
    Pagination-based harvester with auto-stop and rate limiting.
    
    Features:
    - Supports ?page=n and /page/n patterns
    - Auto-stops when no new links found (prevents infinite loops)
    - Random delay (2-5s) between pages to avoid IP bans
    - Hard max_pages limit for safety
    """
    
    def discover(self, max_pages=5, start_page=1):
        """
        Discover video URLs using pagination with auto-stop.
        
        Args:
            max_pages: Maximum pages to crawl (default=5, hard limit)
            start_page: Page number to start from (default=1)
        
        Returns:
            set: Discovered video URLs
        """
        import time
        import random
        
        logger.info(f"[HARVESTER] Starting pagination discovery from {self.base_url}")
        logger.info(f"[HARVESTER] Start page: {start_page}, Max pages: {max_pages}")
        
        page_num = start_page
        end_page = start_page + max_pages
        consecutive_zero_pages = 0
        
        while page_num < end_page:
            # URL Construction Logic - Prioritize WordPress style /page/n/
            if '?' in self.base_url:
                current_page_url = f"{self.base_url}&page={page_num}"
            else:
                # viralkand.com usually uses /page/n/
                current_page_url = f"{self.base_url.rstrip('/')}/page/{page_num}/"
            
            try:
                logger.info(f"[HARVESTER] Crawling page {page_num} of {end_page-1}: {current_page_url}")
                
                # CRITICAL: Rotate User-Agent on every page to prevent fingerprinting
                from core.utils import get_random_user_agent
                headers = {
                    'User-Agent': get_random_user_agent(),
                    'Referer': self.base_url,  # Makes it look like human browsing
                    'Connection': 'keep-alive',  # Better performance
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
                response = requests.get(current_page_url, headers=headers, timeout=15)
                
                if response.status_code == 404:
                    logger.info(f"[HARVESTER] Page {page_num} returned 404 - reached end of pagination")
                    break
                elif response.status_code != 200:
                    logger.warning(f"[HARVESTER] Page {page_num} returned status {response.status_code}")
                    # Don't break immediately on other errors, just skip
                    page_num += 1
                    continue
                    
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all links on this page
                all_links = []
                for link in soup.find_all('a', href=True):
                    from urllib.parse import urljoin
                    full_url = urljoin(current_page_url, link['href'])
                    all_links.append(full_url)
                
                # Filter for video pages
                before_count = len(self.discovered_urls)
                video_urls = self.filter_urls(all_links)
                self.discovered_urls.update(video_urls)
                after_count = len(self.discovered_urls)
                
                new_links_found = after_count - before_count
                logger.info(f"✅ Page {page_num}: Found {new_links_found} new video links (Total: {after_count})")
                
                # AUTO-STOP: If no new links found, stop crawling
                if new_links_found == 0:
                    consecutive_zero_pages += 1
                    logger.warning(f"[HARVESTER] No new links on page {page_num} ({consecutive_zero_pages} consecutive zero pages)")
                    
                    if consecutive_zero_pages >= 2:
                        logger.info(f"[HARVESTER] Auto-stopping: 2 consecutive pages with no new links")
                        break
                else:
                    consecutive_zero_pages = 0  # Reset counter
                
                # Rate limiting: Random delay to avoid IP bans
                if page_num < end_page:
                    delay = random.uniform(2.0, 5.0)
                    logger.debug(f"[HARVESTER] Waiting {delay:.1f}s before next page...")
                    time.sleep(delay)
                
                page_num += 1
                
            except Exception as e:
                logger.error(f"[HARVESTER] Error crawling page {page_num}: {e}")
                # Don't break the whole loop on one page error
                page_num += 1
                continue
            

        
        logger.info(f"[HARVESTER] Pagination complete: {len(self.discovered_urls)} total video URLs discovered across {page_num-1} pages")
        return self.discovered_urls


class SitemapHarvester(BaseHarvester):
    """
    Harvester that reads from XML sitemaps.
    Fastest method if sitemap is available.
    """
    
    def discover(self, max_pages=None):
        """
        Discover URLs from sitemap.xml
        
        Returns:
            set: Discovered video URLs
        """
        sitemap_urls = [
            urljoin(self.base_url, '/sitemap.xml'),
            urljoin(self.base_url, '/sitemap_index.xml'),
            urljoin(self.base_url, '/post-sitemap.xml'),
        ]
        
        logger.info(f"[HARVESTER] Trying sitemap discovery...")
        
        for sitemap_url in sitemap_urls:
            try:
                response = requests.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    logger.info(f"[HARVESTER] Found sitemap: {sitemap_url}")
                    
                    soup = BeautifulSoup(response.text, 'xml')
                    
                    # Extract URLs from sitemap
                    urls = []
                    for loc in soup.find_all('loc'):
                        urls.append(loc.text.strip())
                    
                    # Filter for video pages
                    video_urls = self.filter_urls(urls)
                    self.discovered_urls.update(video_urls)
                    
                    logger.info(f"[HARVESTER] Sitemap yielded {len(video_urls)} video URLs")
                    return self.discovered_urls
                    
            except Exception as e:
                logger.debug(f"[HARVESTER] Sitemap {sitemap_url} failed: {e}")
        
        logger.warning(f"[HARVESTER] No sitemap found, falling back to generic crawl")
        # Fallback to generic discovery
        generic = GenericHarvester(self.base_url)
        return generic.discover()


class ViralkandHarvester(BaseHarvester):
    """
    Specialized harvester for viralkand.com using Priority Queue BFS.
    Prioritizes Video Links, then Categories. Skips Tags.
    """
    
    def discover(self, max_pages=10):
        """
        Discover video URLs using a controlled BFS + Priority Queue logic.
        
        Args:
            max_pages: Maximum number of pages to crawl (crawl steps limit)
        
        Returns:
            set: Discovered video URLs
        """
        logger.info(f"[HARVESTER] Starting Viralkand BFS discovery from {self.base_url}")
        
        visited = set()
        # Queue stores URLs to crawl. 
        # We use a deque for efficient pops from left.
        # Initial queue has just the homepage.
        queue = deque([self.base_url])
        
        # Track separately to avoid re-adding existing videos to DB needlessly in this run
        self.discovered_videos = set()
        
        pages_crawled = 0
        
        while queue and pages_crawled < max_pages:
            current_url = queue.popleft()
            
            if current_url in visited:
                continue
            
            try:
                # SAFETY DELAY: 3-7s random sleep to behave like a human
                delay = random.uniform(3.0, 7.0)
                logger.info(f"[HARVESTER] ⏳ Waiting {delay:.1f}s...")
                time.sleep(delay)
                
                logger.info(f"[HARVESTER] 🕸️ Crawling {pages_crawled + 1}/{max_pages}: {current_url}")
                
                # Fetch page
                from core.utils import get_random_user_agent
                headers = {
                    'User-Agent': get_random_user_agent(),
                    'Referer': self.base_url,
                    'Connection': 'keep-alive'
                }
                
                response = requests.get(current_url, headers=headers, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract ALL links
                page_links = []
                for a in soup.find_all('a', href=True):
                    full_url = urljoin(current_url, a['href'])
                    # Basic cleanup
                    full_url = full_url.split('#')[0].split('?')[0] # Remove fragments/queries for cleaner crawling
                    
                    # Ensure domain match
                    if self.domain not in full_url:
                        continue
                        
                    page_links.append(full_url)
                
                # SEPARATE: Video Links vs Category Links
                video_candidates = []
                category_candidates = []
                
                for link in page_links:
                    if self.is_video_page(link):
                        video_candidates.append(link)
                    elif self.is_category_link(link):
                        category_candidates.append(link)
                    elif '/page/' in link:
                         category_candidates.append(link) # Treat pagination like categories (crawl targets)

                # PROCESS 1: Add Video Links (Immediate Reward)
                new_videos = 0
                for v_link in video_candidates:
                    if v_link not in self.discovered_videos:
                        self.discovered_videos.add(v_link)
                        new_videos += 1
                
                logger.info(f"   found {new_videos} new videos, {len(category_candidates)} crawl targets")

                # PROCESS 2: Add Category Links to Queue (Future Reward)
                # Sort unique candidates to keep order deterministic-ish
                for c_link in sorted(list(set(category_candidates))):
                    if c_link not in visited and c_link not in queue:
                        queue.append(c_link)
                
                visited.add(current_url)
                pages_crawled += 1
                
            except Exception as e:
                logger.error(f"[HARVESTER] Error crawling {current_url}: {e}")
                visited.add(current_url) # Mark visited so we don't retry forever
        
        logger.info(f"[HARVESTER] Viralkand discovery complete. Found {len(self.discovered_videos)} videos.")
        return self.discovered_videos

    def is_video_page(self, url):
        """
        Strict logic to identify video pages.
        Format: viralkand.com/video-title-slug/ (Level 1 path)
        """
        # Parse path
        parsed = urlparse(url)
        if parsed.netloc != self.domain:
            return False
            
        path = parsed.path.strip('/')
        if not path: 
            return False
            
        # Blacklist of known non-video prefixes/slugs
        blacklist = [
            'category', 'tag', 'author', 'page', 'search', 'login', 'register',
            'contact', 'about', 'dmca', 'privacy', 'terms', 'cookie', 
            '18-u-s-c', 'compliance', 'uploads', 'wp-content', 'wp-includes'
        ]
        
        parts = path.split('/')
        
        # RULE 1: Video pages are usually at root level (depth 1)
        # viralkand.com/video-slug/ -> matches
        # viralkand.com/category/desi/ -> fails (depth 2)
        if len(parts) > 1:
            return False
            
        slug = parts[0].lower()
        
        # RULE 2: Slug must not contain blacklist keywords
        if any(word in slug for word in blacklist):
            return False
            
        # RULE 3: Extension check (avoid .jpg, .css pages if any)
        if '.' in slug:
             # If it has an extension, it better be .html or .php (rare but possible)
             # but usually these are resource files
             if not (slug.endswith('.html') or slug.endswith('.php')):
                 return False

        return True

    def is_category_link(self, url):
        """
        Identify links that are good for crawling (Categories).
        """
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        # Must be valid path
        if not path:
             # Homepage is a "category" in abstract sense, but already in queue
             return False 
             
        # Explicit Category paths
        if 'category/' in path or 'mms-videos' in path or 'bhabhi' in path:
            return True
        
        # Check for /page/n pattern
        if '/page/' in path:
            return True
            
        return False



def harvest_and_save(base_url, method='auto', max_pages=5, start_page=1):
    """
    Convenience function to discover and save URLs with detailed stats.
    
    Args:
        base_url: Website homepage URL
        method: 'auto', 'sitemap', 'generic', or 'pagination'
        max_pages: Maximum pages to crawl (for pagination/generic methods)
        start_page: Page number to start crawling from (for pagination method)
        
    Returns:
        dict: Statistics with keys:
            - 'pages_scanned': Number of pages crawled
            - 'links_found': Total unique links discovered
            - 'links_added': New links added to database
    """
    if method == 'sitemap':
        harvester = SitemapHarvester(base_url)
    elif method == 'generic':
        harvester = GenericHarvester(base_url)
    elif method == 'pagination':
        harvester = LinkHarvester(base_url)
    elif 'viralkand.com' in base_url or 'thekamababa.com' in base_url:
        harvester = ViralkandHarvester(base_url)
    else:  # auto
        # Try pagination first (best for most sites), fallback to sitemap
        harvester = LinkHarvester(base_url)
    
    # Discover URLs
    if isinstance(harvester, LinkHarvester):
        urls = harvester.discover(max_pages=max_pages, start_page=start_page)
    else:
        urls = harvester.discover(max_pages=max_pages)
    
    # Save to database
    new_count = harvester.save_to_database(urls)
    
    stats = {
        'pages_scanned': max_pages,  # Approximate
        'links_found': len(urls),
        'links_added': new_count
    }
    
    logger.info(f"[HARVESTER] Stats: {stats}")
    return stats
