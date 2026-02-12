import os
import random
import time
import json
import soundfile as sf
import requests
import numpy as np
import PIL.Image
from datetime import datetime
import pytz 

# --- FIX FOR PILLOW ERROR ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ----------------------------

from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from kokoro_onnx import Kokoro
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]

# --- SFX MAPPING (Keyword -> Filename in 'sfx/' folder) ---
# Ensure these files exist in your sfx folder!
SFX_MAP = {
    "knock": "knock.mp3", "banging": "knock.mp3", "tap": "knock.mp3",
    "scream": "scream.mp3", "yell": "scream.mp3", "shriek": "scream.mp3",
    "whisper": "whisper.mp3", "voice": "whisper.mp3",
    "step": "footsteps.mp3", "run": "footsteps.mp3", "walk": "footsteps.mp3",
    "static": "static.mp3", "glitch": "static.mp3", "radio": "static.mp3",
    "boom": "thud.mp3", "fall": "thud.mp3", "slam": "thud.mp3"
}

def anti_ban_sleep():
    """Random sleep to prevent YouTube spam detection."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        sleep_seconds = random.randint(300, 2700)
        print(f"🕵️ Anti-Ban: Sleeping for {sleep_seconds // 60} minutes...")
        time.sleep(sleep_seconds)

def get_dynamic_model_url():
    """Dynamically finds an available Gemini model."""
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    try:
        response = requests.get(list_url)
        if response.status_code == 200:
            data = response.json()
            for model in data.get('models', []):
                if "generateContent" in model.get('supportedGenerationMethods', []):
                    if "gemini-1.5-flash" in model['name']:
                        return f"https://generativelanguage.googleapis.com/v1beta/{model['name']}:generateContent?key={GEMINI_KEY}"
            for model in data.get('models', []):
                if "generateContent" in model.get('supportedGenerationMethods', []):
                    return f"https://generativelanguage.googleapis.com/v1beta/{model['name']}:generateContent?key={GEMINI_KEY}"
    except: pass
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"

def setup_kokoro():
    """Initializes Kokoro TTS with SELF-HEALING download logic."""
    print("🧠 Initializing Kokoro AI...")
    model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
    voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"
    
    model_filename = "kokoro-v0_19.onnx"
    voices_filename = "voices.json"

    # Self-Healing
    if os.path.exists(model_filename):
        if os.path.getsize(model_filename) < 50 * 1024 * 1024:
            print("⚠️ Corrupt model found. Deleting...")
            os.remove(model_filename)

    if not os.path.exists(model_filename):
        print(f"   -> Downloading Model...")
        r = requests.get(model_url, stream=True)
        with open(model_filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

    if not os.path.exists(voices_filename):
        print(f"   -> Downloading Voices...")
        r = requests.get(voices_url, stream=True)
        with open(voices_filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

    return Kokoro(model_filename, voices_filename)

def get_blended_voice(kokoro_engine, primary="bm_lewis", secondary="am_michael", blend_ratio=0.65):
    """Creates a unique 'GhostBot' voice by blending vectors."""
    try:
        with open("voices.json", "r") as f:
            voices = json.load(f)
        v1 = np.array(voices[primary], dtype=np.float32)
        v2 = np.array(voices[secondary], dtype=np.float32)
        return (v1 * blend_ratio) + (v2 * (1.0 - blend_ratio))
    except: return primary

def master_audio(file_path):
    """Cinema Mastering: High Pass 80Hz + Compression."""
    try:
        sound = AudioSegment.from_file(file_path)
        sound = sound.high_pass_filter(80) 
        sound = compress_dynamic_range(sound, threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
        sound = normalize(sound, headroom=1.0)
        sound.export(file_path, format="wav")
    except: pass

def get_time_based_mode():
    current_hour = datetime.now().hour
    if 4 <= current_hour < 16: return "STORY"
    else: return "FACT"

def generate_script_data(mode):
    """VIRAL DIRECTOR: Uses specific high-retention niches."""
    print(f"🧠 AI Viral Director Mode: {mode}")
    url = get_dynamic_model_url()
    
    niches = [
        "Rules Horror (e.g., 'Rules for the Night Shift')",
        "Fake Emergency Broadcasts (e.g., 'Do not look at the moon')",
        "POV: You are being hunted",
        "Glitch in the Matrix (Real life lag)",
        "Deep Sea Thalassophobia",
        "Uncanny Valley (Things that look human but aren't)"
    ]
    selected_niche = random.choice(niches)

    prompt_text = f"""
    You are a Viral TikTok/Shorts Director. Write a script for a **{selected_niche}** video.
    
    ### THE "GLUED" FORMULA (STRICT RULES):
    1. **0:00-0:03 (THE HOOK):** Start IMMEDIATELY with a warning or visual description. NO intros.
       * *Bad:* "One day I was..."
       * *Good:* "If you hear whistling in these woods, it's already too late."
    2. **0:03-0:40 (THE ESCALATION):** Short, punchy sentences. Max 7 words per sentence.
    3. **0:40-0:60 (THE TWIST):** End with a shocking realization or loop.
    
    ### VISUAL INSTRUCTIONS:
    For every line, give me a 'visual_keyword' that is SPECIFIC. 
    * *Bad:* "scary"
    * *Good:* "pov camera running through dark forest flashlight"
    
    ### JSON OUTPUT:
    {{
        "title": "ALL CAPS CLICKBAIT TITLE #shorts",
        "description": "Viral description.",
        "tags": ["horror", "creepy", "viral"],
        "lines": [
            {{ "text": "Don't blink.", "visual_keyword": "extreme close up scared eye" }},
            {{ "text": "They move when you blink.", "visual_keyword": "weeping angel statue moving" }}
        ]
    }}
    """
    
    try:
        r = requests.post(url, json={ "contents": [{ "parts": [{"text": prompt_text}] }] })
        raw = r.json()['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw.replace("```json", "").replace("```", "").strip())
    except: return None

def generate_audio_per_line(line_data, index, kokoro_engine):
    text = line_data["text"]
    filename = f"temp_audio_{index}.wav"
    
    # 1. Voice Blending
    custom_voice = get_blended_voice(kokoro_engine, "bm_lewis", "am_michael", 0.65)
    
    # 2. Dynamic Pacing (Acting)
    speed = 0.95
    if "!" in text: speed = 1.15
    if "..." in text: speed = 0.85
    if "?" in text: speed = 1.05
    
    audio, sample_rate = kokoro_engine.create(text, voice=custom_voice, speed=speed, lang="en-gb")
    sf.write(filename, audio, sample_rate)
    return filename

def add_sfx_layer(audio_clip, text):
    """Scans text for keywords and overlays SFX from sfx/ folder."""
    text_lower = text.lower()
    sfx_file = None
    
    # Check for keywords in SFX_MAP
    for keyword, filename in SFX_MAP.items():
        if keyword in text_lower:
            path = os.path.join("sfx", filename)
            if os.path.exists(path):
                sfx_file = path
                break
    
    # Fallback: 20% chance of random static/ambience if no keyword
    if not sfx_file and random.random() < 0.2:
        path = os.path.join("sfx", "static.mp3")
        if os.path.exists(path):
            sfx_file = path

    if sfx_file:
        try:
            sfx = AudioFileClip(sfx_file)
            # Volume control: SFX shouldn't overpower voice
            sfx = sfx.volumex(0.4) 
            # If SFX is longer than voice, trim it. If shorter, it plays once.
            if sfx.duration > audio_clip.duration:
                sfx = sfx.subclip(0, audio_clip.duration)
            
            return CompositeAudioClip([audio_clip, sfx])
        except Exception as e:
            print(f"⚠️ SFX Error: {e}")
            
    return audio_clip

def download_specific_visual(keyword, filename, min_duration):
    # Enhanced Query for Cinematic look
    enhanced_query = f"{keyword} cinematic 4k vertical horror"
    print(f"🎥 Visual Search: '{enhanced_query}'")
    
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={enhanced_query}&per_page=5&orientation=portrait"
    
    try:
        r = requests.get(url, headers=headers).json()
        if not r.get('videos'): 
             return download_specific_visual("creepy dark atmosphere", filename, min_duration)
        
        # Sort by resolution (Quality)
        best_v = r['videos'][0]
        video_files = best_v['video_files']
        video_files.sort(key=lambda x: x['width'] * x['height'], reverse=True)
        link = video_files[0]['link']

        with open(filename, "wb") as f:
            f.write(requests.get(link).content)
        return True
    except: return False

def main_pipeline():
    anti_ban_sleep()
    
    mode = get_time_based_mode()
    script_data = generate_script_data(mode)
    if not script_data: return None, None
    
    kokoro = setup_kokoro()
    if not kokoro: return None, None

    final_clips = []
    print(f"🎬 Title: {script_data['title']}")
    
    for i, line in enumerate(script_data["lines"]):
        wav_file = generate_audio_per_line(line, i, kokoro)
        master_audio(wav_file) 
        
        audio_clip = AudioFileClip(wav_file)
        
        # --- NEW: ADD SFX ---
        audio_clip = add_sfx_layer(audio_clip, line["text"])
        # --------------------

        # Breath pause
        pause = AudioClip(lambda t: 0, duration=random.uniform(0.1, 0.3))
        audio_clip = concatenate_audioclips([audio_clip, pause])
        
        video_file = f"temp_video_{i}.mp4"
        if download_specific_visual(line["visual_keyword"], video_file, audio_clip.duration):
            try:
                clip = VideoFileClip(video_file)
                if clip.duration < audio_clip.duration:
                    clip = clip.loop(int(np.ceil(audio_clip.duration / clip.duration)) + 1)
                clip = clip.subclip(0, audio_clip.duration)
                
                clip = clip.resize(height=1920)
                if clip.w < 1080: clip = clip.resize(width=1080)
                clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)
                
                clip = clip.set_audio(audio_clip).fadein(0.2).fadeout(0.2)
                final_clips.append(clip)
            except Exception as e: print(e)

    if not final_clips: return None, None
    
    print("✂️ Rendering Final Master...")
    final_video = concatenate_videoclips(final_clips, method="compose")
    output_file = "final_video.mp4"
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, preset="fast")
    
    return output_file, script_data

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
