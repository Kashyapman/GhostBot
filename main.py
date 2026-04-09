import os
import random
import time
import json
import glob
import requests
import urllib.parse
import base64
import numpy as np
import PIL.Image
from google import genai
from google.genai import types
from moviepy.editor import *
from moviepy.video.fx.all import colorx
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

# TITANIUM PIPELINE KEYS
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY")

CHANNEL_HANDLE = "@TheGlitchArchive"
TOPICS_FILE = "topics.txt"

# Video Settings
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
IMAGE_TRANSITION_TIME = 3.0 # Aim for a visual change every 3 seconds

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

# ================== GLOBAL SOTA INTELLIGENCE (CASCADE) ==================
def get_top_free_openrouter_models(limit=3):
    """Task-Optimized SOTA selector prioritizing strict JSON formatting. Returns Top N models for cascading."""
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
        print(f"⚠️ OPENROUTER_API_KEY missing. Defaulting to {default_models}.")
        return default_models

    try:
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        if response.status_code != 200:
            print(f"⚠️ OpenRouter API returned status {response.status_code}. Using defaults.")
            return default_models
            
        models_data = response.json().get('data', [])
        free_models = []
        
        for m in models_data:
            pricing = m.get('pricing', {})
            if (pricing.get('prompt') == '0' and pricing.get('completion') == '0') or ':free' in m['id']:
                free_models.append(m['id'])
                
        if not free_models:
            print("⚠️ No free models found in active list. Using default models.")
            return default_models

        def get_model_reward(m_id):
            m_lower = m_id.lower()
            for known_model, score in SOTA_REWARD_MATRIX.items():
                if known_model in m_lower: 
                    return score
            
            score = 50
            if "instruct" in m_lower: score += 20
            if "chat" in m_lower: score += 10
            if "llama-3" in m_lower: score += 15
            elif "qwen" in m_lower: score += 15
            elif "mistral" in m_lower: score += 10
            
            if "preview" in m_lower or "experimental" in m_lower or "liquid" in m_lower or "test" in m_lower: 
                score -= 40
            return score

        best_models = sorted(free_models, key=get_model_reward, reverse=True)[:limit]
        print(f"🌟 Task-Optimized SOTA Cascade Locked: {best_models}")
        return best_models
        
    except Exception as e:
        print(f"⚠️ Dynamic model scout failed: {e}. Using defaults.")
        return default_models

# ================== LLM HELPER ==================
def ask_llm(system_instruction, prompt, sota_models):
    """A robust helper function that loops through SOTA models until one succeeds."""
    strict_prompt = prompt + "\n\nCRITICAL RULE: Return ONLY the exact requested text. Do not include introductory conversational text like 'Here is the title:' or 'Sure!'"
    
    if OPENROUTER_KEY:
        for sota_model in sota_models:
            headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
            payload = {"model": sota_model, "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": strict_prompt}]}
            try:
                r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=45)
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content'].strip()
                else:
                    print(f"⚠️ OpenRouter ({sota_model}) returned {r.status_code}. Cascading to next model...")
            except Exception as e:
                print(f"⚠️ SOTA LLM error ({sota_model}): {e}")

    # Final Fallback to Gemini Flash
    try:
        print("⚠️ All OpenRouter models busy. Falling back to Gemini Flash...")
        client = genai.Client(api_key=GEMINI_KEY)
        config = types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.7)
        response = client.models.generate_content(model="gemini-2.5-flash", contents=strict_prompt, config=config)
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ Gemini final fallback error: {e}")
        return ""

# ================== PHASE 1: THE WRITER ==================
def generate_viral_script(fallback_sota_models):
    """Phase 1: Writer module. Tries Gemini Pro first, then cascades through Top 3 OpenRouter models."""
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
            "acting_text": "He walked into the room... <break time='1.5s'/> and <emphasis>vanished</emphasis>.",
            "clean_text": "He walked into the room and vanished."
        }
    ]
}
'''

    prompt = f"""
You are an elite viral YouTube Shorts writer and an Award-Winning Voice Director.
Channel: "The Glitch Archive" (dark, eerie historical true crime/mysteries).
CATEGORY: {niche}

MISSION:
Write a highly engaging, high-retention script about a highly specific, obscure REAL case. 
DO NOT invent a fake story. Use a strictly documented historical event, crime, or widely reported anomaly.
{avoid_instruction}

STRICT STORYTELLING RULES (FOR 100%+ RETENTION):
1. THE HOOK (0-3s): The first sentence MUST drop a bizarre paradox, an impossible fact, or a terrifying anomaly.
2. THE OPEN LOOP: In the second sentence, introduce a mystery or ask a compelling question, but delay the answer until the very end.
3. THE PACING: The script must be exactly 130 to 160 words (roughly 45-55 seconds of spoken audio).
4. THE PERFECT LOOP: The final sentence must end abruptly on a cliffhanger that grammatically and conceptually flows perfectly back into the first sentence.

EXPRESSION TAGS (SSML) FOR VOICE ACTING:
You MUST use SSML tags inside `acting_text` to direct the AI voice.
- Use <break time="1s"/> or <break time="1.5s"/> for terrifying, suspenseful pauses before big reveals.
- Use <emphasis level="strong"> for shocking or violent words.
- Use <prosody rate="slow" pitch="-15%"> [creepy text here] </prosody> when explaining dark, creeping details or a terrifying conclusion.
Keep the `clean_text` completely free of XML/SSML tags.

Return ONLY valid JSON exactly matching this format:
{json_template}
"""
    
    config = types.GenerateContentConfig(temperature=0.9, top_p=0.95, response_mime_type="application/json")
    
    try:
        response = client.models.generate_content(model="models/gemini-2.5-pro", contents=prompt, config=config)
        data = json.loads(response.text)
        print("✅ Script written successfully with Gemini.")
        return data
    except Exception as e:
        print(f"⚠️ Gemini Script Error: {e}")
        
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
                    else:
                        print(f"❌ SOTA Fallback {fallback_model} busy/failed ({r.status_code}). Cascading to next...")
                except Exception as sota_e:
                    print(f"❌ SOTA Fallback error for {fallback_model}: {sota_e}")

    return None

# ================== PHASE 3: THE CINEMATOGRAPHER ==================
def generate_cinematographer_prompts(full_script_text, required_images, sota_models):
    """Phase 3: Visual Directives module that cascades through available top models."""
    json_template = '''
{
  "visuals": [
    {
      "search_query": "1977 Southern Television broadcast real photo",
      "ai_prompt": "A glowing CRT television in a pitch black 1970s living room, glowing harsh static, eerie volumetric fog, cinematic 35mm photography, dark shadows, highly detailed, vertical composition"
    }
  ]
}
'''

    prompt = f"""
You are a Master Cinematographer and Archival Researcher for a True Crime / Mystery YouTube channel.
Your ONLY task is to perfectly map sequential visual prompts to the voiceover script below.

SCRIPT:
"{full_script_text}"

We need EXACTLY {required_images} visual transitions to pace the video perfectly. 
For each of the {required_images} scenes, you must provide:

RULE 1: 'search_query' (For DuckDuckGo Image Search)
- MUST be strictly 3 to 6 keywords. Search engines choke on long sentences.
- Use explicit nouns, years, and historical locations.
- PROHIBITED: Do not use adjectives like "creepy", "mysterious", or "scary".
- Good Example: "Max Headroom WGN broadcast 1987"
- Bad Example: "A creepy mysterious man in a mask on a TV"

RULE 2: 'ai_prompt' (For FLUX.1 High-End AI Generation)
- Must be a Midjourney-level photorealistic prompt.
- You MUST use this exact structural formula:
  [Subject/Action] + [Setting/Background] + [Lighting] + [Camera Specs] + [vertical composition]
- Required Camera Specs to include at the end of every prompt: "cinematic 35mm photography, 8k resolution, highly detailed, vertical composition"
- PROHIBITED: NEVER ask for text, numbers, letters, documents with writing, or signs in the image. AI text looks like gibberish. Use "blank document" or "symbol" instead.

Provide EXACTLY {required_images} items. Return ONLY valid JSON matching this format:
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
                    print("⚠️ Cinematographer array too short. Appending safety fallback.")
                    visuals.append({
                        "search_query": "historical true crime evidence photo archive", 
                        "ai_prompt": "Dark cinematic mystery background, true crime documentary style, volumetric lighting, 35mm photography, 8k resolution, highly detailed, vertical composition"
                    })
                return visuals[:required_images]
            else:
                print(f"❌ Cinematographer API ({sota_model}) returned {response.status_code}. Cascading...")
        except Exception as e:
            print(f"❌ Cinematographer execution error ({sota_model}): {e}")
            
    print("🚨 Generating emergency visual prompts to prevent pipeline crash.")
    return [{
        "search_query": "historical mystery evidence photo archive", 
        "ai_prompt": "dark cinematic eerie background, volumetric fog, 35mm photography, 8k resolution, vertical composition"
    } for _ in range(required_images)]

# ================== 4-LAYER TITANIUM PIPELINE ==================
def fetch_ddg_image(prompt, filename):
    print(f"🔍 [1/4] DuckDuckGo Search: {prompt[:40]}...")
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(prompt, max_results=3))
            for res in results:
                img_url = res.get("image")
                if img_url:
                    try:
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                        img_data = requests.get(img_url, headers=headers, timeout=10).content
                        with open(filename, "wb") as f:
                            f.write(img_data)
                        if os.path.getsize(filename) > 1000:
                            print("✅ DuckDuckGo real historical image successfully downloaded!")
                            return True
                    except:
                        continue 
    except ImportError:
        print("⚠️ duckduckgo-search package not installed. Add it to requirements.txt!")
    except Exception as e:
        print(f"⚠️ DuckDuckGo search failed: {e}")
    return False

def fetch_cloudflare_image(prompt, filename):
    print(f"☁️ [2/4] Cloudflare (FLUX.1): {prompt[:40]}...")
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        print("⚠️ Cloudflare credentials missing. Skipping Cloudflare layer.")
        return False
        
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}
    payload = {"prompt": prompt}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            
            if "application/json" in content_type:
                data = response.json()
                image_b64 = data.get("result", {}).get("image")
                
                if image_b64:
                    with open(filename, "wb") as f:
                        f.write(base64.b64decode(image_b64))
                    print("✅ Cloudflare JSON decoded and image saved!")
                    return True
                else:
                    print(f"⚠️ Cloudflare JSON format unknown.")
                    return False
            else:
                with open(filename, "wb") as f:
                    f.write(response.content)
                if os.path.getsize(filename) > 1000:
                    print("✅ Cloudflare binary image generated successfully!")
                    return True
        else:
            print(f"⚠️ Cloudflare API error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"⚠️ Cloudflare connection error: {e}")
    return False

def fetch_pexels_image(prompt, filename):
    print(f"📷 [3/4] Pexels (Stock): {prompt[:40]}...")
    if not PEXELS_KEY:
        print("⚠️ PEXELS_API_KEY missing. Skipping Pexels layer.")
        return False
        
    url = "https://api.pexels.com/v1/search"
    clean_search = prompt.replace("photorealistic", "").replace("highly detailed", "").strip()
    params = {"query": " ".join(clean_search.split()[:5]), "per_page": 1, "orientation": "portrait"}
    
    try:
        response = requests.get(url, headers={"Authorization": PEXELS_KEY}, params=params, timeout=30)
        if response.status_code == 200 and response.json().get("photos"):
            img_data = requests.get(response.json()["photos"][0]["src"]["large2x"], timeout=20).content
            with open(filename, "wb") as f: f.write(img_data)
            if os.path.getsize(filename) > 1000: 
                print("✅ Pexels stock image successfully downloaded.")
                return True
        else:
            print(f"⚠️ Pexels API returned status: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Pexels connection error: {e}")
    return False

def fetch_placeholder_image(keyword, filename):
    print(f"🚨 [4/4] EMERGENCY: Generating fallback placeholder image...")
    try:
        from PIL import Image
        img = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30))
        img.save(filename, "JPEG")
        print("✅ Placeholder generated successfully.")
        return True
    except Exception as e:
        print(f"❌ Critical failure generating placeholder image: {e}")
        return False

def verify_and_convert_image(filename):
    """Validates and converts incoming API images (PNG/WEBP) to strict RGB JPEGs for MoviePy."""
    try:
        with PIL.Image.open(filename) as img:
            img.load() 
            if img.mode in ('RGBA', 'P', 'LA', 'L'):
                img = img.convert('RGB')
            img.save(filename, format='JPEG', quality=95)
        return True
    except Exception as e:
        print(f"⚠️ Image validation failed: {e}")
        return False

def get_image_clip(search_query, ai_prompt, duration, index):
    """Executes the 4-Layer Titanium fetch cascade based on Cinematographer's prompts."""
    img_filename = f"temp_img_{index}.jpg"
    success = False
    
    success = fetch_ddg_image(search_query, img_filename)
    if not success: success = fetch_cloudflare_image(ai_prompt, img_filename)
    if not success: success = fetch_pexels_image(ai_prompt, img_filename)
    if not success: success = fetch_placeholder_image(search_query, img_filename)

    if not verify_and_convert_image(img_filename):
        print("🚨 Image corrupt or unreadable. Using emergency placeholder.")
        fetch_placeholder_image(search_query, img_filename)

    try:
        clip = ImageClip(img_filename).set_duration(duration).resize(height=VIDEO_HEIGHT)
        if clip.w < VIDEO_WIDTH: clip = clip.resize(width=VIDEO_WIDTH)
        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=VIDEO_WIDTH, height=VIDEO_HEIGHT)
        
        zoom = (lambda t: 1 + 0.05 * (t / duration)) if index % 2 == 0 else (lambda t: 1.05 - 0.05 * (t / duration))
        clip = clip.resize(zoom).crop(x_center=VIDEO_WIDTH/2, y_center=VIDEO_HEIGHT/2, width=VIDEO_WIDTH, height=VIDEO_HEIGHT)
        return clip
    except Exception as e:
        print(f"❌ Error applying MoviePy properties to image: {e}")
        return ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 35), duration=duration)

# ================== META, SUBTITLES & YOUTUBE ==================
def add_sfx(audio_clip, text):
    text_lower = text.lower()
    for k, v in SFX_MAP.items():
        if k in text_lower:
            path = os.path.join("sfx", v)
            if os.path.exists(path):
                try:
                    sfx = AudioFileClip(path).volumex(0.20)
                    if sfx.duration > audio_clip.duration: sfx = sfx.subclip(0, audio_clip.duration)
                    return CompositeAudioClip([audio_clip, sfx])
                except Exception as e:
                    print(f"⚠️ Error adding SFX '{v}': {e}")
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
                        txt = txt.set_start(word.start).set_end(word.end).set_position(('center', video_clip.h * 0.70))
                        subtitle_clips.append(txt)
                    except Exception as e:
                        print(f"⚠️ Failed to render subtitle word '{clean}': {e}")
                        
        print(f"✅ Generated {len(subtitle_clips)} valid word captions!")
        return CompositeVideoClip([video_clip] + subtitle_clips)
    except Exception as e:
        print(f"❌ Whisper Transcription failed entirely: {e}")
        return video_clip

def upload_to_youtube(file_path, yt_metadata):
    if not file_path: return False
    print("🚀 Uploading to YouTube...")
    try:
        creds = Credentials.from_authorized_user_info(json.loads(YOUTUBE_TOKEN_VAL))
        youtube = build("youtube", "v3", credentials=creds)
        full_description = f"{yt_metadata['description']}\n\nWhat would be your first move? 👇"
        
        youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {"title": yt_metadata["title"], "description": full_description, "tags": yt_metadata["tags"], "categoryId": "24"}, 
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        ).execute()
        print("✅ YouTube Upload Successful!")
        return True
    except Exception as e: 
        print(f"❌ YouTube Upload failed: {e}")
        return False

# ================== PHASE 5: THE MARKETER (STRICT CHAIN) ==================
def generate_youtube_metadata(full_script_text, sota_models):
    """Executes a strict 1-to-1 prompt isolation workflow exclusively for YouTube SEO."""
    print("📈 Phase 5: Marketer - Generating YouTube SEO Chain...")
    sys_prompt = "You are an elite YouTube Shorts SEO Strategist. You ONLY output the exact data requested, with absolutely no conversational filler, no greetings, and no markdown blocks."
    
    # Task 1: Generate Title ONLY
    print("   -> Drafting optimized Title...")
    t_prompt = f"Read this short script and write ONE highly viral, click-oriented YouTube Shorts title (under 60 characters). Do not include quotes, hashtags, or introductory text.\nScript: {full_script_text}"
    title = ask_llm(sys_prompt, t_prompt, sota_models).strip('"').replace("'", "")
    if not title or len(title) > 80: title = "They found WHAT?"
    
    # Task 2: Generate Description ONLY (Based on Title)
    print("   -> Drafting optimized Description...")
    d_prompt = f"You have a YouTube Short titled: '{title}'. The script is: '{full_script_text}'. Write a compelling 3-sentence description optimized for the YouTube algorithm. Do not use hashtags or introductory text."
    description = ask_llm(sys_prompt, d_prompt, sota_models)
    if not description: description = "An unsolved mystery that will leave you speechless."
    
    # Task 3: Generate Tags ONLY (Based on Title + Description)
    print("   -> Extracting optimized Tags...")
    tag_prompt = f"You have a YouTube Short titled: '{title}' and described as: '{description}'. Provide exactly 8 highly-searched SEO tags. Return ONLY a comma-separated list of words. Do not use hashtags (#) or introductory text."
    tags_str = ask_llm(sys_prompt, tag_prompt, sota_models)
    tags = [t.strip().replace("#", "") for t in tags_str.split(',')] if tags_str else ["mystery", "shorts", "creepy", "unsolved", "truecrime"]

    title_with_hashtags = f"{title} #shorts #mystery"
    print("✅ YouTube SEO Chain Complete.")
    return {"title": title_with_hashtags, "description": description, "tags": tags}

def generate_platform_captions(yt_metadata, platform, sota_models):
    """Generates strictly isolated platform-specific captions."""
    print(f"🤖 Generating optimized {platform} caption...")
    sys_prompt = f"You are an elite {platform} Social Media Manager. You output ONLY the final caption text with absolutely no introductory words or conversational filler."
    
    if platform == "Instagram":
        prompt = f"Convert this YouTube metadata into a viral Instagram Reels caption.\nTitle: {yt_metadata['title']}\nDescription: {yt_metadata['description']}\nREQUIREMENTS: Include a strong visual hook, a call-to-action to comment, and exactly 6 targeted hashtags. Format nicely with emojis. NO introductory text."
    else: # Facebook
        prompt = f"Convert this YouTube metadata into a highly engaging Facebook Reels caption.\nTitle: {yt_metadata['title']}\nDescription: {yt_metadata['description']}\nREQUIREMENTS: Facebook audiences love storytelling. Make it conversational, ask a highly specific question to drive comments, and use 3 broad hashtags. NO introductory text."
        
    caption = ask_llm(sys_prompt, prompt, sota_models)
    if not caption: caption = f"{yt_metadata['title']}\n\nWhat do you think happened? 👇\n\n#Mystery"
    return caption

# ================== MASTER ORCHESTRATION ==================
def main_pipeline():
    anti_ban_sleep()
    
    try:
        voice_engine = VoiceEngine()
    except Exception as e:
        print(f"❌ VoiceEngine Initialization Error: {e}")
        return None, None, None, None

    # PHASE 0: AWAKEN GLOBAL SOTA BRAIN (CASCADE ARRAY)
    global_sota_models = get_top_free_openrouter_models()

    # PHASE 1: WRITER
    script = generate_viral_script(global_sota_models)
    if not script: 
        print("❌ Script generation returned None. Aborting.")
        return None, None, None, None
        
    print(f"🎬 Case: {script.get('case_name', 'Unknown')}")

    # PHASE 2: RECORDING STUDIO (Audio First)
    print("🎙️ Phase 2: Recording Studio (Generating Voiceover...)")
    audio_clips = []
    full_script_text = ""
    target_voice = script.get("recommended_voice_model", "Charon")

    for i, line in enumerate(script["lines"]):
        clean_text = line.get("clean_text", "")
        full_script_text += clean_text + " "
        
        try:
            wav_file = voice_engine.generate_acting_line(
                acting_text=line.get("acting_text", ""),
                clean_text=clean_text,
                style_instruction=line.get("style_instruction", ""),
                index=i,
                voice_name=target_voice
            )
            if wav_file:
                audio_clip = AudioFileClip(wav_file)
                audio_clip = add_sfx(audio_clip, clean_text)
                audio_clips.append(audio_clip)
        except Exception as e:
            print(f"❌ Error generating audio for line {i}: {e}")

    if not audio_clips: 
        print("❌ No audio clips successfully generated. Aborting.")
        return None, None, None, None
    
    master_voice_clip = concatenate_audioclips(audio_clips)
    total_duration = master_voice_clip.duration
    
    required_images = int(total_duration / IMAGE_TRANSITION_TIME)
    if required_images < 1: required_images = 1
    
    print(f"⏱️ Master Audio Duration: {total_duration:.2f}s | Images Needed: {required_images}")

    # PHASE 3 & 4: CINEMATOGRAPHER & FETCHING 
    visual_directions = generate_cinematographer_prompts(full_script_text, required_images, global_sota_models)
    duration_per_image = total_duration / len(visual_directions)
    
    visual_clips = []
    for i, vis in enumerate(visual_directions):
        img_clip = get_image_clip(vis.get("search_query", ""), vis.get("ai_prompt", ""), duration_per_image, i)
        visual_clips.append(img_clip)

    # FINAL STITCH
    print("✂️ Rendering Final Video with Transitions & Subtitles...")
    try:
        final_video = concatenate_videoclips(visual_clips, method="compose").set_duration(total_duration)
        final_video = final_video.set_audio(master_voice_clip).fx(colorx, 0.85)
    except Exception as e:
        print(f"❌ Final composition stitch failed: {e}")
        return None, None, None, None

    temp_voice_track = "temp_master_voice.wav"
    master_voice_clip.write_audiofile(temp_voice_track, fps=24000, logger=None)
    final_video = add_dynamic_subtitles(final_video, temp_voice_track)

    try:
        watermark = TextClip(
            CHANNEL_HANDLE, fontsize=30, color='white', font='Impact', stroke_color='black', stroke_width=2
        ).set_opacity(0.4).set_position(('center', 150)).set_duration(final_video.duration)
        final_video = CompositeVideoClip([final_video, watermark])
    except Exception as e:
        print(f"⚠️ Error applying watermark layer: {e}")

    output_file = "final_video.mp4"
    print(f"💾 Writing final video file to {output_file}...")
    try:
        final_video.write_videofile(
            output_file, codec="libx264", audio_codec="aac", fps=24, preset="fast", threads=2, logger=None
        )
    except Exception as e:
        print(f"❌ Critical failure during video encoding: {e}")
        return None, None, None, None
    
    try:
        for f in glob.glob("temp_*.wav") + glob.glob("temp_*.jpg"): os.remove(f)
    except Exception as e:
        print(f"⚠️ Minor error during temporary file cleanup: {e}")
        
    return output_file, script, full_script_text, global_sota_models

# ================== ENTRY ==================
if __name__ == "__main__":
    video_path, script_data, full_script_text, global_sota_models = main_pipeline()
    
    if video_path and script_data and global_sota_models:
        
        # PHASE 5: THE MARKETER (Execute SEO Chain)
        yt_metadata = generate_youtube_metadata(full_script_text, global_sota_models)
        
        if upload_to_youtube(video_path, yt_metadata):
            case_name = script_data.get('case_name', 'Unknown Case')
            save_new_topic(case_name)
            
            # Platform Specific Marketing
            fb_caption = generate_platform_captions(yt_metadata, "Facebook", global_sota_models)
            meta_upload.upload_to_facebook(video_path, fb_caption)
            
            ig_caption = generate_platform_captions(yt_metadata, "Instagram", global_sota_models)
            temp_url = meta_upload.get_temp_public_url(video_path)
            if temp_url: 
                meta_upload.upload_to_instagram(temp_url, ig_caption)
            else:
                print("⏭️ Skipping Instagram due to temporary host failure.")
                
    print("🎉 Daily GhostBot execution finished!")
