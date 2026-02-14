"""
Test yt-dlp directly on thekamababa.com URLs.
"""
import yt_dlp

test_urls = [
    "https://www.thekamababa.com/sexy-boobed-indian-village-lady-blowjob-sex/",
    "https://www.thekamababa.com/village-couples-first-homemade-porn/"
]

for url in test_urls:
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print('='*60)
    
    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'skip_download': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            print(f"\n[SUCCESS]")
            print(f"Title: {info.get('title', 'N/A')}")
            print(f"Format: {info.get('ext', 'N/A')}")
            print(f"URL: {info.get('url', 'N/A')[:80]}...")
            
    except Exception as e:
        print(f"\n[FAILED] {str(e)}")
