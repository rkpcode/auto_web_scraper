"""
Colab Secrets Debug Script
Run this in Colab to verify your secrets are properly configured.
"""

print("=" * 60)
print("🔍 COLAB SECRETS DIAGNOSTIC")
print("=" * 60)

# Step 1: Check if secrets are accessible
print("\n1️⃣ Checking Colab Secrets...")
try:
    from google.colab import userdata
    print("   ✅ google.colab.userdata imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import: {e}")
    print("   ⚠️  Are you running this in Google Colab?")
    exit(1)

# Step 2: Try to get BUNNY_API_KEY
print("\n2️⃣ Checking BUNNY_API_KEY...")
try:
    api_key = userdata.get('BUNNY_API_KEY')
    if api_key:
        print(f"   ✅ Found: {api_key[:10]}...{api_key[-10:]}")
        print(f"   📏 Length: {len(api_key)} characters")
    else:
        print("   ❌ Secret exists but is empty!")
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("   💡 Solution: Add 'BUNNY_API_KEY' in Colab Secrets (🔑 icon)")

# Step 3: Try to get BUNNY_LIBRARY_ID
print("\n3️⃣ Checking BUNNY_LIBRARY_ID...")
try:
    library_id = userdata.get('BUNNY_LIBRARY_ID')
    if library_id:
        print(f"   ✅ Found: {library_id}")
    else:
        print("   ❌ Secret exists but is empty!")
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("   💡 Solution: Add 'BUNNY_LIBRARY_ID' in Colab Secrets (🔑 icon)")

# Step 4: Set environment variables
print("\n4️⃣ Setting environment variables...")
import os

try:
    os.environ['BUNNY_API_KEY'] = userdata.get('BUNNY_API_KEY')
    os.environ['BUNNY_LIBRARY_ID'] = userdata.get('BUNNY_LIBRARY_ID')
    print("   ✅ Environment variables set")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Step 5: Verify environment variables
print("\n5️⃣ Verifying environment variables...")
if 'BUNNY_API_KEY' in os.environ and os.environ['BUNNY_API_KEY']:
    print(f"   ✅ BUNNY_API_KEY: {os.environ['BUNNY_API_KEY'][:10]}...")
else:
    print("   ❌ BUNNY_API_KEY not set in environment")

if 'BUNNY_LIBRARY_ID' in os.environ and os.environ['BUNNY_LIBRARY_ID']:
    print(f"   ✅ BUNNY_LIBRARY_ID: {os.environ['BUNNY_LIBRARY_ID']}")
else:
    print("   ❌ BUNNY_LIBRARY_ID not set in environment")

# Step 6: Test BunnyUploader initialization
print("\n6️⃣ Testing BunnyUploader initialization...")
try:
    import sys
    sys.path.append('/content/auto_web_scraper/video_engine')
    
    from core.uploader import BunnyUploader
    uploader = BunnyUploader()
    print("   ✅ BunnyUploader initialized successfully!")
    print(f"   📦 Library ID: {uploader.library_id}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "=" * 60)
print("✅ DIAGNOSTIC COMPLETE")
print("=" * 60)

# Summary
print("\n📋 SUMMARY:")
print("If all checks passed ✅, your Colab is ready!")
print("If any checks failed ❌, follow the solutions above.")
print("\n💡 Common Issues:")
print("1. Forgot to add secrets → Click 🔑 icon, add both secrets")
print("2. Forgot to enable 'Notebook access' → Toggle it ON")
print("3. Typo in secret names → Must be exact: BUNNY_API_KEY, BUNNY_LIBRARY_ID")
