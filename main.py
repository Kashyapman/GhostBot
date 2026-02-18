import os
import random
import time
import json
import requests
import numpy as np
import PIL.Image
from datetime import datetime

# --- NEW GOOGLE GEN AI SDK ---
from google import genai
from google.genai import types
# -----------------------------

from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pydub import AudioSegment
from neural_voice import VoiceEngine 

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]

if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# --- SFX MAPPING ---
SFX_MAP = {
    "knock": "knock.mp3", "bang": "knock.mp3",
    "scream": "scream.mp3", "yell": "scream.mp3",
    "step": "footsteps.mp3", "run": "footsteps.mp3",
    "static": "static.mp3", "glitch": "static.mp3",
    "breath": "whisper.mp3", "whisper": "whisper.mp3"
}

def anti_ban_sleep():
    """Random sleep to prevent YouTube spam detection."""
    # Only sleep in production (GitHub Actions), not during testing
    if os.environ.get("GITHUB_ACTIONS") == "true":
        sleep_seconds = random.randint(300, 900) 
        print(f"🕵️ Anti-Ban: Sleeping for {sleep_seconds // 60} minutes...")
        time.sleep(sleep_seconds)

def get_available_models(client):
    """
    Scans for usable models. Crucial for avoiding 404s.
    Returns a list of valid model names like 'models/gemini-1.5-flash'
    """
    print("   🔍 Diagnosing available models for your API Key...")
    valid_models = []
    try:
        # List all models
        for m in client.models.list():
            # Check if it supports content generation
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
    except Exception as e:
        print(f"   ⚠️ Diagnosis Warning: {e}")
        # Fallback list if the list() call fails
        return ["models/gemini-1.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-pro"]

    # Sort: Flash models first (cheaper/faster)
    valid_models.sort(key=lambda x: 0 if 'flash' in x.lower() else 1)
    
    print(f"   ✅ Valid Models Found: {valid_models}")
    return valid_models

def generate_viral_script():
    print("🧠 Director: Writing Script (Business Mode)...")
    
    client = genai.Client(api_key=GEMINI_KEY)
    
    # 1. GET VALID MODELS
    # We ask the API "What can I use?" instead of guessing
    models_to_try = get_available_models(client)
    
    if not models_to_try:
        print("   ❌ No models found. Using Hardcoded Fallbacks.")
        models_to_try = ["models/gemini-1.5-flash", "models/gemini-1.5-pro-latest"]

    niches = [
        "The 'Fake' Human (Uncanny Valley)", "Deep Sea Thalassophobia", 
        "The Backrooms Level 0", "Rules for Night Shift Security", 
        "Glitch in the Matrix", "The Hum (Sound)", "Dead Internet Theory"
    ]
    niche = random.choice(niches)

    prompt = f"""
    Write a cinematic, TERRIFYING YouTube Short story about: {niche}.
    
    ### AUDIO INSTRUCTIONS (CRITICAL):
    You MUST use Bark Audio tags in the text:
    - [gasps] for fear
    - [sighs] for resignation
    - [laughs] for creepy moments
    - ... for pauses
    
    ### JSON FORMAT:
    {{
        "title": "SCARY CLICKBAIT TITLE #shorts",
        "description": "Viral description.",
        "tags": ["horror", "shorts"],
        "lines": [
            {{ "role": "narrator", "text": "Stop. ... Don't look behind you.", "visual_keyword": "dark hallway" }},
            {{ "role": "victim", "text": "[gasps] No! NO! I hear it breathing!", "visual_keyword": "shadow monster" }},
            {{ "role": "demon", "text": "It is... too late.", "visual_keyword": "black screen fading" }}
        ]
    }}
    """
    
    # Config: Force JSON
    config = types.GenerateContentConfig(
        safety_settings=[types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="BLOCK_NONE"
        )],
        response_mime_type="application/json"
    )
    
    # 2. ROBUST GENERATION LOOP
    for model_name in models_to_try:
        try:
            print(f"   Attempting generation with {model_name}...")
            
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            
            if not response.text:
                raise ValueError("Empty response received")

            # Parse JSON
            return json.loads(response.text)
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # RATE LIMIT (429): Don't wait 60s. Switch model immediately.
            if "429" in error_msg or "quota" in error_msg:
                print(f"   ⚠️ Rate Limit on {model_name}. Switching model instantly...")
                continue # Skip to next model in loop
                
            # NOT FOUND (404): Just skip
            elif "404" in error_msg or "not found" in error_msg:
                print(f"   ⚠️ {model_name} not compatible. Skipping.")
                continue
                
            # OTHER ERRORS
            else:
                print(f"   ⚠️ Error: {e}")
                continue

    # 3. EMERGENCY FALLBACK (The "Show Must Go On" Logic)
    # If ALL AI models fail, we return a pre-written generic script.
    # This ensures your business never crashes even if Google is down.
    print("❌ All AI Models Failed. Engaging Emergency Backup Script.")
    return {
        "title": "Don't Look Back #shorts",
        "description": "A horror story generated by GhostBot Emergency Protocol.",
        "tags": ["horror", "creepy"],
        "lines": [
            { "role": "narrator", "text": "There is a rule we all know. ... Never look in the mirror at 3 AM.", "visual_keyword": "broken mirror dark" },
            { "role": "victim", "text": "[gasps] I saw something move behind me!", "visual_keyword": "scared eyes closeup" },
            { "role": "narrator", "text": "But by the time you see it... it's already too late.", "visual_keyword": "glitch static" }
        ]
    }

def add_sfx(audio_clip, text):
    text_lower = text.lower()
    sfx_path = None
    for k, v in SFX_MAP.items():
        if k in text_lower:
            path = os.path.join("sfx", v)
            if os.path.exists(path): sfx_path = path; break
    
    if sfx_path:
        try:
            sfx = AudioFileClip(sfx_path).volumex(0.35)
            if sfx.duration > audio_clip.duration:
                sfx = sfx.subclip(0, audio_clip.duration)
            return CompositeAudioClip([audio_clip, sfx])
        except: pass
    return audio_clip

def get_visual_clip(keyword, filename, duration):
    headers = {"Authorization": PEXELS_KEY}
    url = "https://api.pexels.com/videos/search"
    params = {"query": f"{keyword} horror cinematic", "per_page": 3, "orientation": "portrait"}
    
    try:
        r = requests.get(url, headers=headers, params=params)
        data = r.json()
        if data.get('videos'):
            best = max(data['videos'], key=lambda x: x['width'] * x['height'])
            link = best['video_files'][0]['link']
            with open(filename, "wb") as f:
                f.write(requests.get(link).content)
            
            clip = VideoFileClip(filename)
            if clip.duration < duration:
                loops = int(np.ceil(duration / clip.duration)) + 1
                clip = clip.loop(n=loops)
            
            clip = clip.subclip(0, duration)
            if clip.h < 1920: clip = clip.resize(height=1920)
            if clip.w < 1080: clip = clip.resize(width=1080)
            clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)
            
            return clip
    except: pass
    
    # Fallback Black Screen
    return ColorClip(size=(1080, 1920), color=(0,0,0), duration=duration)

def main_pipeline():
    anti_ban_sleep()
    
    try: voice_engine = VoiceEngine()
    except Exception as e: 
        print(f"❌ Engine Start Error: {e}"); return None, None
    
    script = generate_viral_script()
    if not script: return None, None
    
    print(f"🎬 Title: {script['title']}")
    final_clips = []
    
    for i, line in enumerate(script["lines"]):
        try:
            wav_file = voice_engine.generate_acting_line(line["text"], i, line.get("role", "narrator"))
            if not wav_file: continue
            
            audio_clip = AudioFileClip(wav_file)
            audio_clip = add_sfx(audio_clip, line["text"])
            
            video_file = f"temp_vid_{i}.mp4"
            clip = get_visual_clip(line["visual_keyword"], video_file, audio_clip.duration)
            
            clip = clip.set_audio(audio_clip).fadein(0.2).fadeout(0.2)
            final_clips.append(clip)
        except Exception as e: print(f"⚠️ Clip Error: {e}")
        
    if not final_clips: 
        print("❌ No final clips assembled."); return None, None

    print("✂️ Rendering Final Master...")
    final = concatenate_videoclips(final_clips, method="compose")
    out_file = "final_video.mp4"
    final.write_videofile(out_file, codec="libx264", audio_codec="aac", fps=24, preset="fast")
    return out_file, script

def upload_to_youtube(file_path, metadata):
    if not file_path: return
    print("🚀 Uploading to YouTube...")
    try:
        creds = Credentials.from_authorized_user_info(json.loads(YOUTUBE_TOKEN_VAL))
        youtube = build('youtube', 'v3', credentials=creds)
        youtube.videos().insert(
            part="snippet,status",
            body={ 
                "snippet": { "title": metadata['title'], "description": metadata['description'], "tags": metadata['tags'], "categoryId": "24" },
                "status": { "privacyStatus": "public", "selfDeclaredMadeForKids": False }
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        ).execute()
        print("✅ Success!")
    except Exception as e: print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    v, m = main_pipeline()
    if v and m: upload_to_youtube(v, m)
