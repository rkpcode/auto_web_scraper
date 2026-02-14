"""
Quick test script to verify Bunny Stream API credentials.
Run this to check if your API key and Library ID are correct.
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BUNNY_API_KEY = os.getenv("BUNNY_API_KEY", "")
BUNNY_LIBRARY_ID = os.getenv("BUNNY_LIBRARY_ID", "")

print("=" * 60)
print("🔍 Bunny Stream API Credentials Test")
print("=" * 60)

# Check if credentials are set
if not BUNNY_API_KEY:
    print("❌ ERROR: BUNNY_API_KEY not found in .env file")
    exit(1)

if not BUNNY_LIBRARY_ID:
    print("❌ ERROR: BUNNY_LIBRARY_ID not found in .env file")
    exit(1)

print(f"\n✅ Credentials loaded from .env:")
print(f"   API Key: {BUNNY_API_KEY[:20]}... (length: {len(BUNNY_API_KEY)})")
print(f"   Library ID: {BUNNY_LIBRARY_ID}")

# Test API connection
print(f"\n🔄 Testing API connection...")
url = f"https://video.bunnycdn.com/library/{BUNNY_LIBRARY_ID}/videos"
headers = {
    "AccessKey": BUNNY_API_KEY,
    "Accept": "application/json"
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    
    print(f"\n📊 Response Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ SUCCESS! API credentials are correct!")
        data = response.json()
        video_count = data.get('totalItems', 0)
        print(f"   Total videos in library: {video_count}")
        
    elif response.status_code == 401:
        print("❌ FAILED: Invalid API Key")
        print("   Solution: Check your API key in Bunny panel")
        print("   Location: Account Settings → API → API Key")
        
    elif response.status_code == 404:
        print("❌ FAILED: Library ID not found")
        print(f"   Library ID '{BUNNY_LIBRARY_ID}' does not exist")
        print("   Solution: Check your Library ID in Stream section")
        
    else:
        print(f"❌ FAILED: Unexpected error (HTTP {response.status_code})")
        print(f"   Response: {response.text[:200]}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ NETWORK ERROR: {e}")
    print("   Check your internet connection")

print("\n" + "=" * 60)
