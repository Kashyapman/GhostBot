import os
import random
import time
import json
import requests
import numpy as np
import PIL.Image
from datetime import datetime

# --- IMPORT OUR NEW ENGINE ---
from neural_voice import VoiceEngine
# -----------------------------

from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]

# --- FIX FOR PILLOW ERROR ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

SFX_MAP = {
    "knock": "knock.mp3", "bang": "knock.mp3",
    "scream": "scream.mp3", "yell": "scream.mp3",
    "step": "footsteps.mp3", "run": "footsteps.mp3",
    "static": "static.mp3", "glitch": "static.mp3",
    "breath": "whisper.mp3", "whisper": "whisper.mp3"
}

def anti_ban_sleep():
    """Smart Heartbeat to keep GitHub Actions alive."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        sleep_sec = random.randint(120, 480) 
        print(f"🕵️ Anti-Ban: Napping for {sleep_sec}s...")
        # Print heartbeat every 30s
        for i in range(sleep_sec, 0, -30):
            print(f"   ...waking in {i}s")
            time.sleep(min(30, i))

def get_gemini_url():
    # Try Flash first (Faster/Better for creative)
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"

def generate_viral_script():
    print("🧠 Director: Writing Script...")
    url = get_gemini_url()
    
    # --- CHAOS NICHE SELECTOR ---
    niches = [
        "The 'Fake' Human (Uncanny Valley)", "Deep Sea Thalassophobia", "The Backrooms Level 0",
        "Rules for Night Shift Security", "The Rake Encounter", "Dead Internet Theory",
        "Glitch in the Matrix", "Mandela Effect: Cornucopia", "The Hum (Sound)",
        "Skinwalker in the Woods", "POV: Buried Alive", "Don't Look at the Moon"
    ]
    niche = random.choice(niches)

    prompt = f"""
    Write a cinematic, TERRIFYING YouTube Short story about: {niche}.
    
    ### STRICT RULES (GOD TIER):
    1. **NO LISTS:** Do NOT write "The lights flickered. The door opened." 
    2. **CONTINUOUS NARRATIVE:** Write exactly 3 sentences that flow together like a movie scene.
    3. **THE HOOK (0s):** The first sentence must be a direct warning to the viewer.
    
    ### JSON FORMAT:
    {{
        "title": "SCARY CLICKBAIT TITLE #shorts",
        "description": "Viral description.",
        "tags": ["horror", "shorts", "viral"],
        "lines": [
            {{ "text": "If you hear your mom calling you from the basement, do not answer.", "visual_keyword": "dark basement stairs pov horror", "mood": "dread" }},
            {{ "text": "I answered last night, and when I got to the bottom step, I saw my real mom standing outside the window, screaming at me to run.", "visual_keyword": "woman screaming outside window horror", "mood": "panic" }},
            {{ "text": "Now, the thing in the basement is walking up the stairs, and it's wearing my face.", "visual_keyword": "monster shadow walking up stairs", "mood": "dread" }}
        ]
    }}
    """
    
    try:
        r = requests.post(url, json={ "contents": [{ "parts": [{"text": prompt}] }] })
        if r.status_code != 200: return None
        raw = r.json()['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw.replace("```json", "").replace("```", "").strip())
    except: return None

def add_sfx(audio_clip, text):
    """Adds SFX layers intelligently."""
    text_lower = text.lower()
    sfx_path = None
    
    for k, v in SFX_MAP.items():
        if k in text_lower:
            path = os.path.join("sfx", v)
            if os.path.exists(path): sfx_path = path; break
    
    # Ambience fallback (Static)
    if not sfx_path and random.random() < 0.25:
        path = os.path.join("sfx", "static.mp3")
        if os.path.exists(path): sfx_path = path
            
    if sfx_path:
        try:
            sfx = AudioFileClip(sfx_path).volumex(0.35)
            if sfx.duration > audio_clip.duration:
                sfx = sfx.subclip(0, audio_clip.duration)
            return CompositeAudioClip([audio_clip, sfx])
        except: pass
    return audio_clip

def download_visual(keyword, filename, duration):
    print(f"🎥 Visual Search: {keyword}")
    headers = {"Authorization": PEXELS_KEY}
    # Force 'Cinematic' and 'Dark' for consistency
    url = f"https://api.pexels.com/videos/search?query={keyword} cinematic dark horror 4k&per_page=5&orientation=portrait"
    
    try:
        r = requests.get(url, headers=headers).json()
        if not r.get('videos'): return False
        
        # Smart Sort: Pick highest resolution
        best = r['videos'][0]
        for v in r['videos']:
            if v['width'] * v['height'] > best['width'] * best['height']:
                best = v
                
        link = best['video_files'][0]['link']
        with open(filename, "wb") as f:
            f.write(requests.get(link).content)
        return True
    except: return False

def main_pipeline():
    anti_ban_sleep()
    
    # 1. Initialize Neural Voice Engine
    voice_engine = VoiceEngine()
    
    # 2. Generate Story
    script = generate_viral_script()
    if not script: return None, None
    print(f"🎬 Title: {script['title']}")

    final_clips = []
    
    for i, line in enumerate(script["lines"]):
        # A. Neural Voice Generation (God Mode)
        wav_file = voice_engine.generate_acting_line(line["text"], i, line.get("mood", "neutral"))
        
        audio_clip = AudioFileClip(wav_file)
        audio_clip = add_sfx(audio_clip, line["text"])
        
        # B. Video Download & Processing
        video_file = f"temp_vid_{i}.mp4"
        download_visual(line["visual_keyword"], video_file, audio_clip.duration)
        
        try:
            clip = VideoFileClip(video_file)
            # Smart Loop: If video is short, crossfade loop it
            if clip.duration < audio_clip.duration:
                clip = clip.loop(duration=audio_clip.duration)
            clip = clip.subclip(0, audio_clip.duration)
            
            # Vertical 9:16 Crop
            if clip.w > 1080:
                clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)
            elif clip.h < 1920:
                clip = clip.resize(height=1920)
                
            clip = clip.set_audio(audio_clip).fadein(0.2).fadeout(0.2)
            final_clips.append(clip)
        except Exception as e: print(f"⚠️ Clip Error: {e}")
        
    if not final_clips: return None, None

    print("✂️ Rendering Final Master...")
    final = concatenate_videoclips(final_clips, method="compose")
    out_file = "final_video.mp4"
    final.write_videofile(out_file, codec="libx264", audio_codec="aac", fps=24, preset="fast")
    return out_file, script

def upload_to_youtube(file_path, metadata):
    if not file_path: return
    print("🚀 Uploading...")
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
