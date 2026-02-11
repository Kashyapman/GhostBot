import os
import random
import time
import json
import soundfile as sf
import requests
import numpy as np
import PIL.Image
from datetime import datetime
import pytz # You might need to add pytz to requirements.txt if not there, or use standard datetime

# --- FIX FOR PILLOW ERROR ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ----------------------------

from moviepy.editor import *
from moviepy.audio.fx.all import audio_loop
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from kokoro_onnx import Kokoro
from huggingface_hub import hf_hub_download
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]

# --- FILES ---
TOPICS_FILE = "topics.txt"

def anti_ban_sleep():
    sleep_seconds = random.randint(300, 2700)
    print(f"🕵️ Anti-Ban: Sleeping for {sleep_seconds // 60} minutes...")
    time.sleep(sleep_seconds)

def get_dynamic_model_url():
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"

def setup_kokoro():
    print("🧠 Initializing Kokoro AI...")
    if not os.path.exists("kokoro-v0_19.onnx"):
        hf_hub_download(repo_id="hexgrad/Kokoro-82M", filename="kokoro-v0_19.onnx", local_dir=".")
    if not os.path.exists("voices.json"):
        hf_hub_download(repo_id="hexgrad/Kokoro-82M", filename="voices.json", local_dir=".")
    return Kokoro("kokoro-v0_19.onnx", "voices.json")

def master_audio(file_path):
    try:
        sound = AudioSegment.from_file(file_path)
        bass = sound.low_pass_filter(150)
        sound = sound.overlay(bass.apply_gain(-3))
        sound = compress_dynamic_range(sound, threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
        sound = normalize(sound)
        sound.export(file_path, format="mp3")
    except: pass

def get_time_based_mode():
    # Get current hour (UTC)
    current_hour = datetime.now().hour
    # If it's between 04:00 and 12:00 UTC, it's "Morning Upload"
    if 4 <= current_hour < 16:
        return "STORY" # Horror/Urban Legend
    else:
        return "FACT" # Paradox/Science

def generate_script_data(mode):
    print(f"🧠 AI Director Mode: {mode}")
    url = get_dynamic_model_url()
    headers = {'Content-Type': 'application/json'}
    
    if mode == "STORY":
        topic_prompt = "A terrifying 2-sentence horror story or urban legend."
        style = "Scary, suspenseful, narrative."
    else:
        topic_prompt = "A mind-blowing scientific paradox, dark history fact, or glitch in the matrix."
        style = "Educational, fast-paced, shocking."

    prompt_text = f"""
    You are a Viral Content Creator. Write a script for a YouTube Short about: {topic_prompt}
    Style: {style}
    
    CRITICAL INSTRUCTIONS:
    1. The first visual keyword MUST be visually striking (e.g., "explosion", "screaming face", "galaxy zooming") to act as a thumbnail hook.
    2. The Title must be Clickbait (ALL CAPS, Question, or Warning).
    
    OUTPUT FORMAT: JSON ONLY.
    {{
        "title": "SCARY TITLE HERE #shorts",
        "description": "Engaging description with hashtags.",
        "tags": ["viral", "shorts", "horror", "facts"],
        "lines": [
            {{ 
                "role": "narrator", 
                "text": "Did you know you are already dead?", 
                "visual_keyword": "skeleton skull dark" 
            }},
             {{ 
                "role": "victim", 
                "text": "Wait, what do you mean?", 
                "visual_keyword": "confused man looking at mirror" 
            }}
        ]
    }}
    
    ROLES: "narrator" (Deep Voice), "victim" (Panicked), "demon" (Slow/Distorted).
    Max 130 words.
    """
    
    data = { "contents": [{ "parts": [{"text": prompt_text}] }] }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            raw = result['candidates'][0]['content']['parts'][0]['text']
            clean_json = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)
    except Exception as e:
        print(f"Gemini Error: {e}")
    return None

def generate_audio_per_line(line_data, index, kokoro_engine):
    text = line_data["text"]
    role = line_data.get("role", "narrator")
    filename = f"temp_audio_{index}.wav"
    
    voice_id = "bm_lewis" # Default Narrator (Deep British)
    speed = 0.9
    
    if role == "victim":
        voice_id = "am_michael" # American Fast
        speed = 1.2
    elif role == "demon":
        voice_id = "bm_lewis"
        speed = 0.6 # Extremely Slow & Scary
    
    audio, sample_rate = kokoro_engine.create(text, voice=voice_id, speed=speed, lang="en-gb")
    sf.write(filename, audio, sample_rate)
    return filename

def download_specific_visual(keyword, filename, duration):
    print(f"🎥 Visual Search: '{keyword}'")
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=3&orientation=portrait"
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            videos = r.json().get('videos', [])
            if not videos: return False
            
            # Pick the video with best quality/duration match
            best_video = videos[0] 
            link = best_video['video_files'][0]['link']
            
            with open(filename, "wb") as f:
                f.write(requests.get(link).content)
            return True
    except: pass
    return False

def main_pipeline():
    # anti_ban_sleep() # Uncomment this later if needed

    # 1. Determine Content Mode (Story vs Fact)
    mode = get_time_based_mode()
    
    # 2. Generate Script & Metadata
    script_data = generate_script_data(mode)
    if not script_data: return None, None
    
    kokoro = setup_kokoro()
    final_clips = []
    
    print(f"🎬 Title: {script_data['title']}")
    
    for i, line in enumerate(script_data["lines"]):
        # Audio
        wav_file = generate_audio_per_line(line, i, kokoro)
        master_audio(wav_file) # Convert/Process to optimized audio
        
        audio_clip = AudioFileClip(wav_file)
        # Add pause
        pause = AudioClip(lambda t: 0, duration=0.1)
        audio_clip = concatenate_audioclips([audio_clip, pause])
        
        # Video
        video_file = f"temp_video_{i}.mp4"
        if download_specific_visual(line["visual_keyword"], video_file, audio_clip.duration):
            try:
                clip = VideoFileClip(video_file)
                if clip.duration < audio_clip.duration:
                    clip = clip.loop(duration=audio_clip.duration)
                else:
                    clip = clip.subclip(0, audio_clip.duration)
                
                # Resize/Crop to 9:16
                clip = clip.resize(height=1920)
                if clip.w < 1080: clip = clip.resize(width=1080)
                clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)
                
                clip = clip.set_audio(audio_clip)
                final_clips.append(clip)
            except: pass

    if not final_clips: return None, None
    
    print("✂️ Rendering...")
    final_video = concatenate_videoclips(final_clips, method="compose")
    
    # Background Music (Optional)
    # You can add the music logic back here if you have mp3s
    
    output_file = "final_video.mp4"
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24)
    
    return output_file, script_data

def upload_to_youtube(file_path, metadata):
    if not file_path: return
    print("🚀 Uploading...")
    try:
        creds_dict = json.loads(YOUTUBE_TOKEN_VAL)
        creds = Credentials.from_authorized_user_info(creds_dict)
        youtube = build('youtube', 'v3', credentials=creds)
        
        body = {
            "snippet": {
                "title": metadata['title'], 
                "description": metadata['description'],
                "tags": metadata['tags'], 
                "categoryId": "24" 
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
        }
        
        youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        ).execute()
        print("✅ Upload Success!")
    except Exception as e:
        print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    v, m = main_pipeline()
    if v and m: upload_to_youtube(v, m)
