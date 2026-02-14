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
from database import db


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
        # Default patterns (override for better accuracy)
        video_patterns = [
            r'/video/',
            r'/watch/',
            r'/v/',
            r'/\d{4,}/',  # Numeric IDs
            r'[a-z0-9-]+/$',  # Slugs ending with /
        ]
        
        return any(re.search(pattern, url, re.I) for pattern in video_patterns)
    
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


def harvest_and_save(base_url, method='auto', max_pages=10):
    """
    Convenience function to discover and save URLs.
    
    Args:
        base_url: Website homepage URL
        method: 'auto', 'sitemap', or 'generic'
        max_pages: Maximum pages to crawl (for generic method)
        
    Returns:
        int: Number of new URLs added to database
    """
    if method == 'sitemap':
        harvester = SitemapHarvester(base_url)
    elif method == 'generic':
        harvester = GenericHarvester(base_url)
    else:  # auto
        # Try sitemap first, fallback to generic
        harvester = SitemapHarvester(base_url)
    
    # Discover URLs
    urls = harvester.discover(max_pages=max_pages)
    
    # Save to database
    new_count = harvester.save_to_database(urls)
    
    logger.info(f"[HARVESTER] Added {new_count} new URLs to database")
    return new_count
