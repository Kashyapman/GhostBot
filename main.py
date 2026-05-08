import os
import random
import time
import json
import glob
import requests
import urllib.parse
import base64
import numpy as np
import cv2

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFilter

from transformers import pipeline
from google import genai
from google.genai import types
from moviepy.editor import *
from moviepy.video.fx.all import colorx, loop
from moviepy.audio.fx.all import audio_loop
from faster_whisper import WhisperModel
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from neural_voice import VoiceEngine
import meta_upload

# ================== CONFIG ==================
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
YOUTUBE_TOKEN_VAL = os.environ.get("YOUTUBE_TOKEN_JSON")

# TITANIUM PIPELINE & ASSET KEYS
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")

CHANNEL_HANDLE = "@TheGlitchArchive"
TOPICS_FILE = "topics.txt"

# Video Settings
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
IMAGE_TRANSITION_TIME = 3.0 

if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

SFX_MAP = {
    "knock": "knock.mp3",
    "bang": "knock.mp3",
    "scream": "scream.mp3",
    "yell": "scream.mp3",
    "step": "footsteps.mp3",
    "run": "footsteps.mp3",
    "static": "static.mp3",
    "glitch": "static.mp3",
    "breath": "whisper.mp3",
    "whisper": "whisper.mp3",
    "thud": "thud.mp3"
}

# ================== ANTI BAN ==================
def anti_ban_sleep():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        sleep_seconds = random.randint(300, 600)
        print(f"🕵️ Anti-Ban Sleep: {sleep_seconds//60} minutes")
        time.sleep(sleep_seconds)

# ================== MEMORY SYSTEM ==================
def get_past_topics():
    if not os.path.exists(TOPICS_FILE):
        return ""
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = f.read().splitlines()
    return "\n".join(topics[-100:])

def save_new_topic(case_name):
    try:
        with open(TOPICS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{case_name}\n")
        print(f"💾 Saved '{case_name}' to memory bank.")
    except Exception as e:
        print(f"⚠️ Failed to save topic to memory: {e}")

# ================== GLOBAL SOTA INTELLIGENCE ==================
def get_top_free_openrouter_models(limit=3):
    print("🔍 Scouting OpenRouter for the best creative & structured SOTA models...")
    default_models = ["meta-llama/llama-3.3-70b-instruct:free", "qwen/qwen-3.6-plus:free", "mistralai/mistral-large:free"]
    
    SOTA_REWARD_MATRIX = {
        "meta-llama/llama-3.3-70b-instruct:free": 99, 
        "qwen/qwen-3.6-plus:free": 98,                 
        "mistralai/mistral-large:free": 97,            
        "deepseek/deepseek-r1:free": 95,               
        "nvidia/nemotron-3-super:free": 94,
        "google/gemma-4-31b-instruct:free": 90
    }
    
    if not OPENROUTER_KEY:
        return default_models

    try:
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        if response.status_code != 200:
            return default_models
            
        models_data = response.json().get('data', [])
        free_models = [m['id'] for m in models_data if (m.get('pricing', {}).get('prompt') == '0' and m.get('pricing', {}).get('completion') == '0') or ':free' in m['id']]
                
        if not free_models: return default_models

        def get_model_reward(m_id):
            m_lower = m_id.lower()
            for known_model, score in SOTA_REWARD_MATRIX.items():
                if known_model in m_lower: return score
            score = 50
            if "instruct" in m_lower: score += 20
            if "llama-3" in m_lower: score += 15
            elif "qwen" in m_lower: score += 15
            elif "mistral" in m_lower: score += 10
            return score

        best_models = sorted(free_models, key=get_model_reward, reverse=True)[:limit]
        print(f"🌟 Task-Optimized SOTA Cascade Locked: {best_models}")
        return best_models
    except Exception as e:
        return default_models

def ask_llm(system_instruction, prompt, sota_models):
    strict_prompt = prompt + "\n\nCRITICAL RULE: Return ONLY the exact requested text. Do not include introductory conversational text."
    if OPENROUTER_KEY:
        for sota_model in sota_models:
            headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
            payload = {"model": sota_model, "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": strict_prompt}]}
            try:
                r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=45)
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content'].strip()
                else:
                    time.sleep(4) 
            except Exception as e:
                time.sleep(4)

    try:
        client = genai.Client(api_key=GEMINI_KEY)
        config = types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.7)
        response = client.models.generate_content(model="gemini-2.5-flash", contents=strict_prompt, config=config)
        return response.text.strip()
    except Exception as e:
        return ""

# ================== PHASE 1: THE WRITER ==================
def generate_viral_script(fallback_sota_models):
    print("🧠 Phase 1: Generating Master Script (Writer)...")
    client = genai.Client(api_key=GEMINI_KEY)
    
    content_pool = [
        "Bizarre Unsolved Disappearances", "Impossible Heists and Robberies",
        "People Who Faked Their Own Deaths", "Real-life Glitches in the Matrix",
        "Bizarre Historical Artifacts That Shouldn't Exist", "Creepy Hijacked TV and Radio Broadcasts"
    ]
    niche = random.choice(content_pool)
    print(f"🎲 Selected Category: {niche}")

    past_topics = get_past_topics()
    avoid_instruction = f"CRITICAL: Do NOT write about these cases:\n{past_topics}\n" if past_topics else ""

    json_template = '''
{
    "case_name": "The Somerton Man",
    "recommended_voice_model": "Charon",
    "lines": [
        {
            "style_instruction": "Hushed, terrified whisper.",
            "acting_text": "He walked into the room... <break time='1.5s'/> and <emphasis level='strong'>vanished</emphasis>.",
            "clean_text": "He walked into the room and vanished."
        }
    ]
}
'''

    prompt = f"""
You are an elite, award-winning True Crime / Mystery Documentary Writer for the YouTube channel "The Glitch Archive".
CATEGORY FOR TODAY: {niche}

MISSION:
Write a highly engaging, high-retention script about a highly specific, obscure, and 100% REAL historical case or anomaly. 
DO NOT invent a fake story. You must use a strictly documented event.
{avoid_instruction}

STRICT PSYCHOLOGICAL PACING & RETENTION RULES:
1. THE PATTERN INTERRUPT (Line 1): Start immediately with the most shocking, impossible, or terrifying fact of the case. NO intros. NO "Welcome back." NO "Have you ever wondered..."
2. THE ESCALATION (Lines 2-6): Rapidly build context. Use short, punchy, active sentences. Reveal the evidence piece by piece.
3. THE IMPOSSIBLE PROBLEM (Lines 7-8): Introduce the detail that baffled investigators, defied physics, or remains unexplained to this day.
4. THE PERFECT LOOP (Final Line): The final sentence must abruptly cut off or ask a haunting question that grammatically flows perfectly back into the first word of the script.

BANNED CLICHÉS & AI-SPEAK (DO NOT USE THESE):
- "Dive into..."
- "A chilling reminder that..."
- "Some say it was..."
- "Will we ever know?"
- "Buckle up..."
- "In the annals of history..."

EXPRESSION TAGS (SSML) FOR VOICE ACTING:
You are directing the Voice Actor. You MUST use SSML tags inside `acting_text`.
- Use <break time="1s"/> or <break time="1.5s"/> for terrifying, suspenseful pauses right before big reveals.
- Use <emphasis level="strong"> for shocking, violent, or critical words.
- Use <prosody rate="slow" pitch="-15%"> [creepy text] </prosody> when whispering dark, creeping details.

TECHNICAL CONSTRAINTS:
- The `clean_text` combined MUST be exactly 130 to 160 words (approx. 50 seconds spoken).
- Limit the script to 8 to 12 total `lines` objects.

Return ONLY valid JSON exactly matching this format:
{json_template}
"""
    
    config = types.GenerateContentConfig(temperature=0.9, top_p=0.95, response_mime_type="application/json")
    
    try:
        response = client.models.generate_content(model="models/gemini-2.5-pro", contents=prompt, config=config)
        data = json.loads(response.text)
        print("✅ Script written successfully with Gemini Pro.")
        return data
    except Exception as e:
        print(f"⚠️ Gemini Pro Quota/Error: {e}")
        if OPENROUTER_KEY:
            headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
            for fallback_model in fallback_sota_models:
                print(f"🔄 Activating Global SOTA Brain ({fallback_model}) for Script Generation...")
                payload = {"model": fallback_model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
                try:
                    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
                    if r.status_code == 200:
                        content = r.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip()
                        print(f"✅ Script written successfully with SOTA Fallback ({fallback_model}).")
                        return json.loads(content)
                except Exception:
                    time.sleep(4)

    print("🚨 Engaging Ultimate Fallback (Gemini Flash)...")
    try:
        flash_config = types.GenerateContentConfig(temperature=0.9, top_p=0.95, response_mime_type="application/json")
        response = client.models.generate_content(model="models/gemini-2.5-flash", contents=prompt, config=flash_config)
        return json.loads(response.text)
    except Exception as flash_e:
        print(f"❌ Ultimate Fallback also failed: {flash_e}")

    return None

# ================== PHASE 3: THE CINEMATOGRAPHER ==================
def generate_cinematographer_prompts(full_script_text, required_images, sota_models):
    json_template = '''
{
  "visuals": [
    {
      "search_query": "Somerton man beach 1948",
      "ai_prompt": "Extreme close-up of a rusted blade resting on a dark mahogany detective's desk under a harsh desk lamp, cinematic 35mm, 8k, vertical"
    }
  ]
}
'''

    prompt = f"""
You are an elite Documentary Cinematographer and Archival Researcher.
Your job is to map perfectly paced, highly varied visual prompts to the voiceover script below.

SCRIPT:
"{full_script_text}"

We need EXACTLY {required_images} visual transitions.

RULE 1: 'search_query' (For Wikipedia - REAL HISTORICAL EVIDENCE)
- MUST be strictly 2 to 4 keywords.
- Focus ONLY on concrete nouns: names, dates, specific locations, or historical objects.
- PROHIBITED: Adjectives, abstract concepts, or full sentences.
- GOOD: "Somerton Man 1948" | BAD: "Creepy man found dead on beach"

RULE 2: 'ai_prompt' (For FLUX.1 High-End B-Roll)
- We are replacing boring flat images with "Diegetic Framing" (physical objects in a physical space).
- INSTEAD OF: "A scary knife."
- USE: "Extreme close-up of a rusted blade resting on a dark mahogany detective's desk under a harsh desk lamp, cinematic 35mm, 8k, vertical."
- VARY THE SHOTS: You MUST alternate between Extreme Close-Ups (macro), Wide Establishing Shots, and Over-the-Shoulder angles to maintain high viewer retention.
- ABSOLUTE BAN ON TEXT: NEVER ask the AI to generate documents with legible writing, signs, or numbers. AI text looks like gibberish. Use "blurred handwriting" or "redacted text" instead.

Return ONLY valid JSON containing EXACTLY {required_images} items in this format:
{json_template}
"""
    
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
    
    for sota_model in sota_models:
        print(f"🎬 Phase 3: Directing {required_images} perfectly-paced visuals using SOTA Brain ({sota_model})...")
        payload = {"model": sota_model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
        try:
            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip()
                data = json.loads(content)
                visuals = data.get("visuals", [])
                
                while len(visuals) < required_images:
                    visuals.append({"search_query": "historical crime evidence", "ai_prompt": "Dark cinematic mystery background, true crime documentary style, volumetric lighting, 35mm photography, 8k resolution, highly detailed, vertical composition"})
                return visuals[:required_images]
        except Exception:
            time.sleep(4)

    print("🚨 Engaging Ultimate Fallback (Gemini Flash) for Visuals...")
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        flash_config = types.GenerateContentConfig(temperature=0.7, response_mime_type="application/json")
        response = client.models.generate_content(model="models/gemini-2.5-flash", contents=prompt, config=flash_config)
        content = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        visuals = data.get("visuals", [])
        while len(visuals) < required_images:
            visuals.append({"search_query": "historical crime evidence", "ai_prompt": "Dark cinematic mystery background, true crime documentary style, volumetric lighting, 35mm photography, 8k resolution, highly detailed, vertical composition"})
        return visuals[:required_images]
    except Exception as flash_e:
        print(f"❌ Ultimate Fallback failed: {flash_e}")
            
    return [{"search_query": "historical mystery evidence", "ai_prompt": "dark cinematic eerie background, volumetric fog, 35mm photography, 8k resolution, vertical composition"} for _ in range(required_images)]


# ================== 4-LAYER TITANIUM PIPELINE ==================
def fetch_archive_image(prompt, filename):
    print(f"🏛️ [1/4] Public Archives Search: {prompt[:40]}...")
    clean_query = " ".join(prompt.replace("photo", "").replace("archive", "").split()[:3])
    wiki_url = "https://en.wikipedia.org/w/api.php"
    wiki_params = {
        "action": "query", "format": "json", "prop": "pageimages",
        "generator": "search", "gsrsearch": clean_query, "gsrlimit": 3, "pithumbsize": 1000 
    }
    headers = {'User-Agent': 'GhostBot/1.0 (Educational History Bot)'}
    
    try:
        response = requests.get(wiki_url, params=wiki_params, headers=headers, timeout=10)
        pages = response.json().get("query", {}).get("pages", {})
        for page_id, page_info in pages.items():
            if "thumbnail" in page_info:
                img_data = requests.get(page_info["thumbnail"]["source"], headers=headers, timeout=15).content
                with open(filename, "wb") as f: f.write(img_data)
                if os.path.getsize(filename) > 1000: return True
    except Exception: pass 

    # 1B: Google CSE Fallback if Wikipedia fails
    if SEARCH_API_KEY and GOOGLE_CSE_ID:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {"q": f"{clean_query} evidence photo", "cx": GOOGLE_CSE_ID, "key": SEARCH_API_KEY, "searchType": "image", "num": 1, "safe": "active"}
            r = requests.get(url, params=params).json()
            if "items" in r:
                img_url = r["items"][0]["link"]
                img_data = requests.get(img_url, headers=headers, timeout=15).content
                with open(filename, "wb") as f: f.write(img_data)
                if os.path.getsize(filename) > 1000: return True
        except Exception: pass

    ia_url = "https://archive.org/advancedsearch.php"
    ia_params = {"q": f'"{clean_query}" AND mediatype:image', "fl": "identifier,format", "rows": 3, "output": "json"}
    try:
        response = requests.get(ia_url, params=ia_params, headers=headers, timeout=10)
        docs = response.json().get("response", {}).get("docs", [])
        for doc in docs:
            identifier = doc.get("identifier")
            if identifier:
                img_data = requests.get(f"https://archive.org/download/{identifier}/{identifier}.jpg", headers=headers, timeout=15).content
                if len(img_data) > 1000: 
                    with open(filename, "wb") as f: f.write(img_data)
                    return True
    except Exception: pass
    return False

def fetch_cloudflare_image(prompt, filename):
    print(f"☁️ [2/4] Cloudflare (FLUX.1): {prompt[:40]}...")
    if not CF_ACCOUNT_ID or not CF_API_TOKEN: return False
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json={"prompt": prompt}, timeout=45)
        if response.status_code == 200:
            if "application/json" in response.headers.get("Content-Type", ""):
                image_b64 = response.json().get("result", {}).get("image")
                if image_b64:
                    with open(filename, "wb") as f: f.write(base64.b64decode(image_b64))
                    return True
            else:
                with open(filename, "wb") as f: f.write(response.content)
                if os.path.getsize(filename) > 1000: return True
    except Exception: pass
    return False

def fetch_pexels_image(prompt, filename):
    print(f"📷 [3/4] Pexels (Stock): {prompt[:40]}...")
    if not PEXELS_KEY: return False
    clean_search = prompt.replace("photorealistic", "").replace("highly detailed", "").strip()
    params = {"query": " ".join(clean_search.split()[:5]), "per_page": 1, "orientation": "portrait"}
    try:
        response = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": PEXELS_KEY}, params=params, timeout=30)
        if response.status_code == 200 and response.json().get("photos"):
            img_data = requests.get(response.json()["photos"][0]["src"]["large2x"], timeout=20).content
            with open(filename, "wb") as f: f.write(img_data)
            if os.path.getsize(filename) > 1000: return True
    except Exception: pass
    return False

def fetch_placeholder_image(keyword, filename):
    try:
        img = PIL.Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30))
        img.save(filename, "JPEG")
        return True
    except Exception: return False

def verify_and_convert_image(filename):
    try:
        with PIL.Image.open(filename) as img:
            img.load() 
            if img.mode in ('RGBA', 'P', 'LA', 'L'): img = img.convert('RGB')
            img.save(filename, format='JPEG', quality=95)
        return True
    except Exception: return False


# ================== PHASE 2 UPGRADE: CONTEXTUAL MATTING ==================
def apply_diegetic_matting(filename):
    """Wraps full-screen images in physical 'documentary' contexts (Polaroids, Shadows, CRT screens)."""
    print(f"🖼️ Phase 2: Applying Contextual Matting to {filename}...")
    try:
        with PIL.Image.open(filename) as img:
            img = img.convert("RGBA")
            target_w, target_h = VIDEO_WIDTH, VIDEO_HEIGHT
            
            bg = PIL.Image.new("RGBA", (target_w, target_h), (12, 12, 15, 255))
            style = random.choice(["polaroid", "cinematic_shadow", "crt_monitor"])
            
            if style == "polaroid":
                img.thumbnail((450, 450), PIL.Image.Resampling.LANCZOS)
                frame_w, frame_h = img.width + 40, img.height + 120
                frame = PIL.Image.new("RGBA", (frame_w, frame_h), (245, 245, 240, 255))
                frame.paste(img, (20, 20))
                angle = random.uniform(-5, 5)
                frame = frame.rotate(angle, expand=True, fillcolor=(0,0,0,0))
                offset_x = (target_w - frame.width) // 2
                offset_y = (target_h - frame.height) // 2
                bg.paste(frame, (offset_x, offset_y), frame)

            elif style == "cinematic_shadow":
                img.thumbnail((600, 800), PIL.Image.Resampling.LANCZOS)
                shadow = PIL.Image.new("RGBA", img.size, (0, 0, 0, 220))
                shadow = shadow.filter(PIL.ImageFilter.GaussianBlur(15))
                offset_x = (target_w - img.width) // 2
                offset_y = (target_h - img.height) // 2
                bg.paste(shadow, (offset_x + 15, offset_y + 15), shadow)
                bg.paste(img, (offset_x, offset_y), img)
                
            elif style == "crt_monitor":
                img.thumbnail((680, 1000), PIL.Image.Resampling.LANCZOS)
                draw = PIL.ImageDraw.Draw(img)
                for y in range(0, img.height, 4):
                    draw.line([(0, y), (img.width, y)], fill=(0, 0, 0, 70), width=1)
                offset_x = (target_w - img.width) // 2
                offset_y = (target_h - img.height) // 2
                bg.paste(img, (offset_x, offset_y), img)

            final_img = bg.convert("RGB")
            final_img.save(filename, format="JPEG", quality=95)
            return True
    except Exception as e:
        print(f"⚠️ Contextual Matting failed: {e}")
        return False

# ================== PHASE 3 UPGRADE: 2.5D PARALLAX ENGINE ==================
def generate_depth_map(image_path):
    """Uses a lightweight local AI model to figure out what is close and what is far away."""
    print(f"🧠 Phase 3: Generating Depth Map for {image_path}...")
    try:
        depth_estimator = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small", device="cpu")
        img = PIL.Image.open(image_path).convert("RGB")
        prediction = depth_estimator(img)
        depth_path = image_path.replace(".jpg", "_depth.jpg")
        prediction["depth"].save(depth_path)
        return depth_path
    except Exception as e:
        print(f"⚠️ Depth Map Generation Failed: {e}")
        return None

def apply_parallax_effect(t, duration, img_array, depth_array, direction="left"):
    """Distorts the image based on the depth map to create 3D camera movement."""
    max_shift = 30.0 
    progress = t / duration 
    
    if direction == "left": current_shift = max_shift * (1.0 - progress)
    else: current_shift = max_shift * progress
        
    normalized_depth = depth_array / 255.0
    shift_map = normalized_depth * current_shift
    
    h, w = img_array.shape[:2]
    map_x = np.zeros((h, w), np.float32)
    map_y = np.zeros((h, w), np.float32)
    
    for y in range(h):
        map_y[y, :] = y
        map_x[y, :] = np.arange(w) + shift_map[y, :]
        
    distorted_img = cv2.remap(img_array, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return distorted_img

# ================== MAIN CLIP GENERATION ==================
def get_image_clip(search_query, ai_prompt, duration, index):
    img_filename = f"temp_img_{index}.jpg"
    
    # Run the Titanium fetch layer
    success = fetch_archive_image(search_query, img_filename)
    if not success: success = fetch_cloudflare_image(ai_prompt, img_filename)
    if not success: success = fetch_pexels_image(ai_prompt, img_filename)
    if not success: success = fetch_placeholder_image(search_query, img_filename)

    if not verify_and_convert_image(img_filename):
        fetch_placeholder_image(search_query, img_filename)

    # Phase 2: Contextual Matting
    apply_diegetic_matting(img_filename)

    try:
        base_clip = ImageClip(img_filename).resize(height=VIDEO_HEIGHT)
        if base_clip.w < VIDEO_WIDTH: base_clip = base_clip.resize(width=VIDEO_WIDTH)
        base_clip = base_clip.crop(x_center=base_clip.w/2, y_center=base_clip.h/2, width=VIDEO_WIDTH, height=VIDEO_HEIGHT)
        
        # Phase 3: 3D Depth Parallax
        temp_cropped = f"temp_cropped_{index}.jpg"
        base_clip.save_frame(temp_cropped, t=0)
        
        depth_path = generate_depth_map(temp_cropped)
        
        if depth_path:
            img_array = cv2.cvtColor(cv2.imread(temp_cropped), cv2.COLOR_BGR2RGB)
            depth_array = cv2.imread(depth_path, cv2.IMREAD_GRAYSCALE)
            cam_dir = "left" if index % 2 == 0 else "right"
            
            def make_parallax_frame(t):
                return apply_parallax_effect(t, duration, img_array, depth_array, direction=cam_dir)
                
            parallax_clip = VideoClip(make_frame=make_parallax_frame, duration=duration)
            return parallax_clip
        else:
            # Fallback Ken Burns zoom
            zoom = (lambda t: 1 + 0.05 * (t / duration)) if index % 2 == 0 else (lambda t: 1.05 - 0.05 * (t / duration))
            return base_clip.resize(zoom).crop(x_center=VIDEO_WIDTH/2, y_center=VIDEO_HEIGHT/2, width=VIDEO_WIDTH, height=VIDEO_HEIGHT)

    except Exception as e:
        print(f"⚠️ Clip generation failed: {e}")
        return ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 35), duration=duration)

# ================== PHASE 1 UPGRADES: SOTA ATMOSPHERICS & AUDIO ==================
def fetch_atmospheric_b_roll(duration, filename="temp_atmosphere.mp4"):
    print("🌫️ Phase 1: Fetching Cinematic Atmosphere (Pexels Video)...")
    if not PEXELS_KEY: return False
    atmospheres = ["dust particles black background", "film grain overlay", "rain drops dark glass", "smoke dark background"]
    params = {"query": random.choice(atmospheres), "per_page": 3, "orientation": "portrait"}
    try:
        response = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": PEXELS_KEY}, params=params, timeout=30)
        if response.status_code == 200:
            videos = response.json().get("videos", [])
            if videos:
                video_data = random.choice(videos)
                hd_files = [f for f in video_data.get("video_files", []) if f.get("quality") == "hd"] or video_data.get("video_files", [])
                if hd_files:
                    with open(filename, "wb") as f: f.write(requests.get(hd_files[0]["link"], timeout=45).content)
                    return True
    except Exception: pass
    return False

def fetch_pixabay_audio(script_text, sota_models, filename="temp_bg_music.mp3"):
    print("🎵 Directing Music Supervisor AI to score the scene...")
    if not PIXABAY_KEY: return False
    
    sys_prompt = "You are an elite cinematic Music Supervisor. You ONLY output the exact data requested."
    vibe_prompt = f"""
Read this true crime script and output EXACTLY 2 or 3 keywords to search a stock music library for the perfect background score.

CRITICAL RULES:
1. Use ONLY musical, atmospheric, and instrumental terminology.
2. ABSOLUTELY NO narrative words. Do not use words like 'murder', 'ghost', 'detective', or 'blood'.
3. GOOD EXAMPLES: 'dark ambient drone', 'creepy music box', 'tension strings', 'low horror synth'.

SCRIPT: 
{script_text}
"""
    
    music_query = ask_llm(sys_prompt, vibe_prompt, sota_models).replace('"', '').replace("'", "")
    if not music_query or len(music_query) > 40: music_query = "dark suspense ambient" 
    
    try:
        response = requests.get("https://pixabay.com/api/audio/", params={"key": PIXABAY_KEY, "q": music_query, "per_page": 3}, timeout=15)
        if response.status_code == 200:
            hits = response.json().get("hits", [])
            if hits and hits[0].get("audio"):
                with open(filename, "wb") as f: f.write(requests.get(hits[0]["audio"], timeout=30).content)
                return True
    except Exception: pass
    return False

# ================== META, SUBTITLES & YOUTUBE ==================
def add_sfx(audio_clip, text):
    text_lower = text.lower()
    for k, v in SFX_MAP.items():
        if k in text_lower:
            path = os.path.join("sfx", v)
            if os.path.exists(path):
                try:
                    sfx = AudioFileClip(path).volumex(0.20)
                    return CompositeAudioClip([audio_clip, sfx.subclip(0, min(sfx.duration, audio_clip.duration))])
                except Exception: pass
    return audio_clip

def add_dynamic_subtitles(video_clip, audio_path):
    print("📝 Transcribing audio for word-level subtitles...")
    try:
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio_path, word_timestamps=True)
        subtitle_clips = []
        for segment in segments:
            for word in segment.words:
                clean = word.word.strip().upper()
                if clean:
                    try:
                        txt = TextClip(clean, fontsize=70, color='yellow', stroke_color='black', stroke_width=2, font='Impact', method='caption', size=(video_clip.w * 0.9, None))
                        subtitle_clips.append(txt.set_start(word.start).set_end(word.end).set_position(('center', video_clip.h * 0.70)))
                    except Exception: pass
        return CompositeVideoClip([video_clip] + subtitle_clips)
    except Exception: return video_clip

def upload_to_youtube(file_path, yt_metadata):
    if not file_path: return False
    print("🚀 Uploading to YouTube...")
    try:
        creds = Credentials.from_authorized_user_info(json.loads(YOUTUBE_TOKEN_VAL))
        youtube = build("youtube", "v3", credentials=creds)
        youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {"title": yt_metadata["title"], "description": f"{yt_metadata['description']}\n\nWhat would be your first move? 👇", "tags": yt_metadata["tags"], "categoryId": "24"}, 
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        ).execute()
        return True
    except Exception: return False

# ================== PHASE 5: THE MARKETER ==================
def generate_youtube_metadata(full_script_text, sota_models):
    sys_prompt = "You are an elite YouTube Shorts SEO Strategist. You ONLY output the exact data requested."
    
    t_prompt = f"""
Read this script and write ONE viral YouTube Shorts title (under 50 characters).
CRITICAL RULES: 
- Create a 'Curiosity Gap'. Do not give away the ending or the main twist. 
- GOOD: "The man who didn't exist" or "They found WHAT in the walls?"
- BAD: "The Somerton Man Mystery Explained"
- No quotes. No hashtags.
Script: {full_script_text}
"""
    title = ask_llm(sys_prompt, t_prompt, sota_models).strip('"').replace("'", "") or "They found WHAT?"
    
    d_prompt = f"Write a compelling 3-sentence description for a YouTube Short titled: '{title}'. The final sentence MUST be a direct, provocative question to the viewer to drive comments. No hashtags."
    description = ask_llm(sys_prompt, d_prompt, sota_models) or "An unsolved mystery that will leave you speechless."
    
    tags_str = ask_llm(sys_prompt, f"Title: '{title}'. Description: '{description}'. Provide exactly 8 highly-searched SEO tags as a comma-separated list. No hashtags.", sota_models)
    tags = [t.strip().replace("#", "") for t in tags_str.split(',')] if tags_str else ["mystery", "shorts", "creepy", "unsolved", "truecrime"]
    return {"title": f"{title} #shorts #mystery", "description": description, "tags": tags}

def generate_platform_captions(yt_metadata, platform, sota_models):
    sys_prompt = f"You are an elite {platform} Social Media Manager. Output ONLY the final caption text."
    
    if platform == "Instagram":
        prompt = f"""
Write a viral Instagram Reels caption for this mystery video.
Title: {yt_metadata['title']}
Description: {yt_metadata['description']}

REQUIREMENTS:
1. First line MUST be an aggressive hook that stops the scroll.
2. Do not summarize the video; tease the scariest part.
3. End with a Call-To-Action telling them to debate in the comments.
4. Exactly 6 trending true-crime/mystery hashtags.
"""
    else: 
        prompt = f"""
Write a highly engaging Facebook Reels caption for this mystery video.
Title: {yt_metadata['title']}
Description: {yt_metadata['description']}

REQUIREMENTS:
1. Tone: Conversational, slightly unnerving.
2. Ask the viewer a direct "What would you do?" style question in the first two lines.
3. Exactly 3 hashtags.
"""
    return ask_llm(sys_prompt, prompt, sota_models) or f"{yt_metadata['title']}\n\nWhat do you think happened? 👇\n\n#Mystery"


# ================== MASTER ORCHESTRATION ==================
def main_pipeline():
    anti_ban_sleep()
    try: voice_engine = VoiceEngine()
    except Exception: return None, None, None, None

    global_sota_models = get_top_free_openrouter_models()
    script = generate_viral_script(global_sota_models)
    if not script: return None, None, None, None
        
    if len(script.get("lines", [])) > 12: script["lines"] = script["lines"][:12]

    audio_clips, full_script_text = [], ""
    for i, line in enumerate(script["lines"]):
        clean_text = line.get("clean_text", "")
        full_script_text += clean_text + " "
        try:
            wav_file = voice_engine.generate_acting_line(line.get("acting_text", ""), clean_text, line.get("style_instruction", ""), i, script.get("recommended_voice_model", "Charon"))
            if wav_file: audio_clips.append(add_sfx(AudioFileClip(wav_file), clean_text))
        except Exception: pass

    if not audio_clips: return None, None, None, None
    master_voice_clip = concatenate_audioclips(audio_clips)
    
    required_images = max(1, int(master_voice_clip.duration / IMAGE_TRANSITION_TIME))
    visual_directions = generate_cinematographer_prompts(full_script_text, required_images, global_sota_models)
    duration_per_image = master_voice_clip.duration / len(visual_directions)
    
    visual_clips = [get_image_clip(vis.get("search_query", ""), vis.get("ai_prompt", ""), duration_per_image, i) for i, vis in enumerate(visual_directions)]

    try:
        final_video = concatenate_videoclips(visual_clips, method="compose").set_duration(master_voice_clip.duration).fx(colorx, 0.85)
        
        atm_filename = "temp_atmosphere.mp4"
        if fetch_atmospheric_b_roll(master_voice_clip.duration, atm_filename):
            try:
                atm_clip = VideoFileClip(atm_filename).without_audio()
                atm_clip = loop(atm_clip, duration=master_voice_clip.duration).resize(height=VIDEO_HEIGHT)
                if atm_clip.w < VIDEO_WIDTH: atm_clip = atm_clip.resize(width=VIDEO_WIDTH)
                atm_clip = atm_clip.crop(x_center=atm_clip.w/2, y_center=atm_clip.h/2, width=VIDEO_WIDTH, height=VIDEO_HEIGHT).set_opacity(0.25)
                final_video = CompositeVideoClip([final_video, atm_clip])
            except Exception: pass
                
        final_video = final_video.set_audio(master_voice_clip)
    except Exception: return None, None, None, None

    temp_voice_track = "temp_master_voice.wav"
    master_voice_clip.write_audiofile(temp_voice_track, fps=24000, logger=None)
    final_video = add_dynamic_subtitles(final_video, temp_voice_track)

    try:
        watermark = TextClip(CHANNEL_HANDLE, fontsize=30, color='white', font='Impact', stroke_color='black', stroke_width=2).set_opacity(0.4).set_position(('center', 150)).set_duration(final_video.duration)
        final_video = CompositeVideoClip([final_video, watermark])
    except Exception: pass

    bg_music_filename = "temp_bg_music.mp3"
    if fetch_pixabay_audio(full_script_text, global_sota_models, bg_music_filename):
        try:
            bg_music = audio_loop(AudioFileClip(bg_music_filename).volumex(0.06), duration=final_video.duration)
            final_video = final_video.set_audio(CompositeAudioClip([final_video.audio, bg_music]))
        except Exception: pass

    output_file = "final_video.mp4"
    try: final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, preset="fast", threads=2, logger=None)
    except Exception: return None, None, None, None
    
    try:
        for f in glob.glob("temp_*.wav") + glob.glob("temp_*.jpg") + glob.glob("temp_*.mp4") + glob.glob("temp_*.mp3"): 
            if f != output_file: os.remove(f)
    except Exception: pass
        
    return output_file, script, full_script_text, global_sota_models

if __name__ == "__main__":
    video_path, script_data, full_script_text, global_sota_models = main_pipeline()
    if video_path and script_data and global_sota_models:
        yt_metadata = generate_youtube_metadata(full_script_text, global_sota_models)
        if upload_to_youtube(video_path, yt_metadata):
            save_new_topic(script_data.get('case_name', 'Unknown Case'))
            meta_upload.upload_to_facebook(video_path, generate_platform_captions(yt_metadata, "Facebook", global_sota_models))
            temp_url = meta_upload.get_temp_public_url(video_path)
            if temp_url: meta_upload.upload_to_instagram(temp_url, generate_platform_captions(yt_metadata, "Instagram", global_sota_models))
