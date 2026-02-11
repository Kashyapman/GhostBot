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

def get_dynamic_model_url():
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
    print("🧠 Initializing Kokoro AI...")
    model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
    voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"
    model_filename = "kokoro-v0_19.onnx"
    voices_filename = "voices.json"

    if not os.path.exists(model_filename):
        r = requests.get(model_url); open(model_filename, "wb").write(r.content)
    if not os.path.exists(voices_filename):
        r = requests.get(voices_url); open(voices_filename, "wb").write(r.content)

    return Kokoro(model_filename, voices_filename)

def master_audio(file_path):
    """Studio-grade audio mastering for human-friendly warmth."""
    try:
        sound = AudioSegment.from_file(file_path)
        # Low Pass Filter at 3500Hz removes digital 'hiss' for a chesty human sound
        sound = sound.low_pass_filter(3500) 
        sound = compress_dynamic_range(sound, threshold=-20.0, ratio=4.0)
        sound = normalize(sound)
        sound.export(file_path, format="wav")
    except: pass

def generate_script_data(mode):
    print(f"🧠 AI Human Director Mode: {mode}")
    url = get_dynamic_model_url()
    
    # --- CHAOS ENGINE: 3 Layers of Randomization for Uniqueness ---
    scenarios = ["a discovery", "a warning", "a secret", "a glitch", "a memory"]
    locations = ["empty playground", "your own bathroom", "late-night subway", "abandoned server room", "foggy highway"]
    fears = ["eyes where they shouldn't be", "sounds that mimic you", "missing time", "objects moving slightly"]
    
    perspective = random.choice(scenarios)
    place = random.choice(locations)
    trigger = random.choice(fears)

    if mode == "STORY":
        topic_prompt = f"A story about {perspective} in a {place} involving {trigger}."
    else:
        topic_prompt = f"A mind-bending human fact about how our brain perceives {trigger} in a {place}."

    prompt_text = f"""
    You are an award-winning cinematic writer. Write a Short script for: {topic_prompt}
    
    ### QUALITY PROTOCOLS:
    1. **Personal Connection:** Use 'You' or 'I'. Speak as if telling a secret to a friend.
    2. **Uniqueness:** Avoid cliches like 'scary ghosts'. Focus on psychological 'Uncanny Valley' vibes.
    3. **Pacing:** One line per sentence. No filler.
    
    ### JSON STRUCTURE:
    {{
        "title": "A GRIPPING HOOK TITLE",
        "description": "Short and viral.",
        "tags": ["mystery", "creepy", "shorts"],
        "lines": [
            {{ "role": "narrator", "text": "Line 1 (The Hook)", "visual_keyword": "cinematic moody portrait" }},
            {{ "role": "narrator", "text": "Line 2 (The Tension)", "visual_keyword": "abstract dark movement" }},
            {{ "role": "narrator", "text": "Line 3 (The Twist)", "visual_keyword": "eerie close up" }}
        ]
    }}
    """
    
    try:
        r = requests.post(url, json={ "contents": [{ "parts": [{"text": prompt_text}] }] })
        raw = r.json()['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw.replace("```json", "").replace("```", "").strip())
    except: return None

def main_pipeline():
    # Detect Time: Morning/Day = STORY, Night = FACT
    mode = "STORY" if 4 <= datetime.now().hour < 16 else "FACT"
    script_data = generate_script_data(mode)
    if not script_data: return
    
    kokoro = setup_kokoro()
    final_clips = []
    
    for i, line in enumerate(script_data["lines"]):
        # Voice Logic: British male for authority and warmth
        audio, sr = kokoro.create(line["text"], voice="bm_lewis", speed=0.95, lang="en-gb")
        wav_file = f"temp_{i}.wav"
        sf.write(wav_file, audio, sr)
        master_audio(wav_file)
        
        audio_clip = AudioFileClip(wav_file)
        # Natural breath pause
        pause = AudioClip(lambda t: 0, duration=0.2)
        audio_clip = concatenate_audioclips([audio_clip, pause])
        
        video_file = f"vid_{i}.mp4"
        if download_specific_visual(line["visual_keyword"], video_file, audio_clip.duration):
            try:
                clip = VideoFileClip(video_file).subclip(0, audio_clip.duration)
                # Ensure 9:16 vertical quality
                clip = clip.resize(height=1920).crop(x1=clip.w/2 - 540, width=1080, height=1920)
                clip = clip.set_audio(audio_clip).fadein(0.5).fadeout(0.5)
                final_clips.append(clip)
            except: pass

    if final_clips:
        print("✂️ Assembling high-quality master...")
        final_video = concatenate_videoclips(final_clips, method="compose")
        final_video.write_videofile("final_video.mp4", codec="libx264", audio_codec="aac", fps=24)
        upload_to_youtube("final_video.mp4", script_data)

def download_specific_visual(keyword, filename, min_duration):
    """Picks from top 5 random results to ensure visual variety."""
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=5&orientation=portrait"
    try:
        r = requests.get(url, headers=headers).json()
        if not r['videos']: return False
        # Quality fix: random choice from results so different videos appear for same topic
        best_v = random.choice(r['videos'])
        link = best_v['video_files'][0]['link']
        open(filename, "wb").write(requests.get(link).content)
        return True
    except: return False

def upload_to_youtube(file_path, metadata):
    try:
        creds = Credentials.from_authorized_user_info(json.loads(YOUTUBE_TOKEN_VAL))
        youtube = build('youtube', 'v3', credentials=creds)
        youtube.videos().insert(
            part="snippet,status",
            body={ 
                "snippet": { 
                    "title": metadata['title'], 
                    "description": metadata['description'], 
                    "categoryId": "24",
                    "tags": metadata.get('tags', [])
                }, 
                "status": { "privacyStatus": "public", "selfDeclaredMadeForKids": False } 
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        ).execute()
        print("✅ Production Complete: Uploaded.")
    except Exception as e: print(f"❌ Upload Error: {e}")

if __name__ == "__main__":
    main_pipeline()
