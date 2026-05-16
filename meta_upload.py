"""
meta_upload.py — Social Broadcaster
====================================
Handles Facebook Reels, Instagram Reels publishing.
Uses a 3-tier fallback system (file.io → Catbox → tmpfiles) 
for Instagram's URL-only upload requirement.
"""

import os
import time
import requests

ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
FB_PAGE_ID   = os.environ.get("FB_PAGE_ID")
IG_USER_ID   = os.environ.get("IG_USER_ID")

GRAPH_VERSION = "v19.0"

# ═══════════════════════════════════════════════════════════
#  FACEBOOK REELS
# ═══════════════════════════════════════════════════════════
def upload_to_facebook(video_path: str, caption: str) -> bool:
    print("📘 Uploading to Facebook Reels...")

    if not ACCESS_TOKEN or not FB_PAGE_ID:
        print("❌ Missing Facebook credentials (META_ACCESS_TOKEN / FB_PAGE_ID). Skipping.")
        return False

    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return False

    url     = f"https://graph.facebook.com/{GRAPH_VERSION}/{FB_PAGE_ID}/videos"
    payload = {"description": caption, "access_token": ACCESS_TOKEN}

    try:
        with open(video_path, "rb") as vf:
            rsp = requests.post(url, data=payload, files={"source": vf}, timeout=120)

        result = rsp.json()
        if "id" in result:
            print(f"✅ Facebook upload success! Video ID: {result['id']}")
            return True
        else:
            print(f"❌ Facebook upload failed: {result}")
            return False

    except Exception as e:
        print(f"❌ Facebook upload error: {e}")
        return False


# ═══════════════════════════════════════════════════════════
#  TEMP PUBLIC URL (3-TIER FAILSAFE)
#  Meta requires a public, direct .mp4 link for Instagram.
# ═══════════════════════════════════════════════════════════
def get_temp_public_url(file_path: str) -> str | None:
    print("☁️  Getting temporary public URL for Instagram...")

    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None

    # ── Method 1: file.io (Bot-friendly, single-use) ──
    try:
        with open(file_path, "rb") as f:
            rsp = requests.post(
                "https://file.io",
                files={"file": f},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=90,
            )
        if rsp.status_code == 200:
            data = rsp.json()
            if data.get("success"):
                url = data.get("link")
                print(f"✅ file.io upload success! URL: {url}")
                return url
        print(f"⚠️  file.io returned: {rsp.status_code} — {rsp.text[:200]}")
    except Exception as e:
        print(f"⚠️  file.io failed: {e}")

    # ── Method 2: Catbox fallback ──
    print("☁️  Falling back to Catbox...")
    try:
        with open(file_path, "rb") as f:
            rsp = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": f},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
                timeout=90,
            )
        if rsp.status_code == 200 and rsp.text.strip().startswith("http"):
            url = rsp.text.strip()
            print(f"✅ Catbox upload success! URL: {url}")
            return url
        print(f"❌ Catbox failed. Response: {rsp.text[:200]}")
    except Exception as e:
        print(f"❌ Catbox error: {e}")

    # ── Method 3: Ultimate Failsafe (tmpfiles.org) ──
    print("☁️  Engaging ultimate fallback to tmpfiles.org...")
    try:
        with open(file_path, "rb") as f:
            rsp = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": f},
                timeout=90
            )
        if rsp.status_code == 200:
            data = rsp.json()
            if data.get("status") == "success":
                # tmpfiles returns a viewer link. We must inject '/dl/' to get the raw .mp4 for Meta
                viewer_url = data["data"]["url"]
                direct_url = viewer_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                print(f"✅ tmpfiles upload success! URL: {direct_url}")
                return direct_url
        print(f"❌ tmpfiles failed. Response: {rsp.text[:200]}")
    except Exception as e:
        print(f"❌ tmpfiles error: {e}")

    return None


# ═══════════════════════════════════════════════════════════
#  INSTAGRAM REELS  (3-stage: container → poll → publish)
# ═══════════════════════════════════════════════════════════
def upload_to_instagram(video_url: str, caption: str) -> bool:
    print("📸 Uploading to Instagram Reels...")

    if not ACCESS_TOKEN or not IG_USER_ID:
        print("❌ Missing Instagram credentials (META_ACCESS_TOKEN / IG_USER_ID). Skipping.")
        return False

    # ── Stage 1: Create media container ──
    container_rsp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}/media",
        data={
            "media_type":  "REELS",
            "video_url":   video_url,
            "caption":     caption,
            "access_token": ACCESS_TOKEN,
        },
        timeout=30,
    )
    container_data = container_rsp.json()

    if "id" not in container_data:
        print(f"❌ Failed to create IG container: {container_data}")
        return False

    creation_id = container_data["id"]
    print(f"⏳ Container created (ID: {creation_id}). Waiting for Meta to process...")

    # ── Stage 2: Poll until FINISHED ──
    status_url    = f"https://graph.facebook.com/{GRAPH_VERSION}/{creation_id}"
    status_params = {"fields": "status_code", "access_token": ACCESS_TOKEN}
    max_attempts  = 30      # 30 × 10s = 5 minutes max wait
    attempts      = 0

    while attempts < max_attempts:
        status_rsp  = requests.get(status_url, params=status_params, timeout=15)
        status_data = status_rsp.json()
        status      = status_data.get("status_code")

        if status == "FINISHED":
            print("✅ Meta processing complete.")
            break
        elif status in ("ERROR", "EXPIRED"):
            print(f"❌ Instagram processing failed with status: {status}")
            return False

        attempts += 1
        print(f"🔄 Processing... ({attempts}/{max_attempts}) — checking again in 10s.")
        time.sleep(10)
    else:
        print("❌ Timed out waiting for Instagram to process the video.")
        return False

    # ── Stage 3: Publish ──
    publish_rsp  = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}/media_publish",
        data={"creation_id": creation_id, "access_token": ACCESS_TOKEN},
        timeout=30,
    )
    publish_data = publish_rsp.json()

    if "id" in publish_data:
        print(f"✅ Instagram publish success! Post ID: {publish_data['id']}")
        return True
    else:
        print(f"❌ Instagram publish failed: {publish_data}")
        return False
