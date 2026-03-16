import os
import time
import requests

# Load credentials from environment variables (GitHub Secrets)
ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN')
FB_PAGE_ID = os.environ.get('FB_PAGE_ID')
IG_USER_ID = os.environ.get('IG_USER_ID')

def upload_to_facebook(video_path, caption):
    print("📘 Uploading to Facebook Reels...")
    if not ACCESS_TOKEN or not FB_PAGE_ID:
        print("❌ Missing Facebook credentials. Skipping.")
        return

    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos"
    payload = {
        'description': caption,
        'access_token': ACCESS_TOKEN
    }
    
    try:
        with open(video_path, 'rb') as video_file:
            files = {'source': video_file}
            response = requests.post(url, data=payload, files=files)
            
        result = response.json()
        if 'id' in result:
            print(f"✅ Facebook upload successful! Video ID: {result['id']}")
        else:
            print(f"❌ Facebook upload failed: {result}")
    except Exception as e:
        print(f"❌ Facebook upload error: {e}")

def get_temp_public_url(file_path):
    print("☁️ Uploading video to temporary host for Instagram...")
    
    # Method 1: Try file.io first (Bot-friendly, perfect for Meta API)
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.post("https://file.io", files=files, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                public_url = data.get('link')
                print(f"✅ file.io upload successful! URL: {public_url}")
                return public_url
    except Exception as e:
        print(f"⚠️ file.io attempt failed: {e}")

    # Method 2: Fallback to Catbox with a spoofed browser User-Agent
    print("☁️ Falling back to Catbox...")
    try:
        url = "https://catbox.moe/user/api.php"
        data = {'reqtype': 'fileupload'}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': f}
            response = requests.post(url, data=data, files=files, headers=headers)
            
        if response.status_code == 200 and response.text.strip().startswith("http"):
            public_url = response.text.strip()
            print(f"✅ Catbox upload successful! URL: {public_url}")
            return public_url
        else:
            print(f"❌ Temporary upload failed. Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error during temporary upload: {e}")
        return None

def upload_to_instagram(video_url, caption):
    print("📸 Uploading to Instagram Reels...")
    if not ACCESS_TOKEN or not IG_USER_ID:
        print("❌ Missing Instagram credentials. Skipping.")
        return

    # Step 1: Create the media container
    container_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media"
    container_payload = {
        'media_type': 'REELS',
        'video_url': video_url,
        'caption': caption,
        'access_token': ACCESS_TOKEN
    }
    
    container_response = requests.post(container_url, data=container_payload)
    container_data = container_response.json()
    
    if 'id' not in container_data:
        print(f"❌ Failed to create IG container: {container_data}")
        return
        
    creation_id = container_data['id']
    print(f"⏳ Container created (ID: {creation_id}). Waiting for Meta to process...")
    
    # Step 2: Poll until processing is finished
    status_url = f"https://graph.facebook.com/v19.0/{creation_id}"
    status_params = {
        'fields': 'status_code',
        'access_token': ACCESS_TOKEN
    }
    
    while True:
        status_response = requests.get(status_url, params=status_params)
        status_data = status_response.json()
        status = status_data.get('status_code')
        
        if status == 'FINISHED':
            break
        elif status in ['ERROR', 'EXPIRED']:
            print(f"❌ Instagram processing failed: {status}")
            return
            
        print("🔄 Processing... checking again in 10 seconds.")
        time.sleep(10)
        
    # Step 3: Publish the container
    publish_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish"
    publish_payload = {
        'creation_id': creation_id,
        'access_token': ACCESS_TOKEN
    }
    
    publish_response = requests.post(publish_url, data=publish_payload)
    publish_data = publish_response.json()
    
    if 'id' in publish_data:
        print(f"✅ Instagram upload successful! Post ID: {publish_data['id']}")
    else:
        print(f"❌ Instagram publish failed: {publish_data}")
