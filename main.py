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

# --- FIX FOR PILLOW ERROR (Common in older MoviePy versions) ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ----------------------------

from moviepy.editor import *
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

def anti_ban_sleep():
    """Random sleep to prevent YouTube spam detection."""
    sleep_seconds = random.randint(300, 2700) # 5 to 45 minutes
    print(f"🕵️ Anti-Ban: Sleeping for {sleep_seconds // 60} minutes...")
    time.sleep(sleep_seconds)

def get_dynamic_model_url():
    """Dynamically finds an available Gemini model supporting generateContent."""
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    try:
        response = requests.get(list_url)
        if response.status_code == 200:
            data = response.json()
            # Prefer newer models if available
            for model in data.get('models', []):
                if "generateContent" in model.get('supportedGenerationMethods', []):
                    # Prefer 1.5 Flash or Pro if available as they are stable
                    if "gemini-1.5-flash" in model['name']:
                        return f"https://generativelanguage.googleapis.com/v1beta/{model['name']}:generateContent?key={GEMINI_KEY}"
            
            # If no specific preference found, take the first valid one
            for model in data.get('models', []):
                if "generateContent" in model.get('supportedGenerationMethods', []):
                    return f"https://generativelanguage.googleapis.com/v1beta/{model['name']}:generateContent?key={GEMINI_KEY}"
    except Exception as e:
        print(f"⚠️ Failed to list models: {e}")
    
    # Fallback default
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
    
def setup_kokoro():
    """Downloads and initializes the Kokoro TTS model using stable v0.19 files."""
    print("🧠 Initializing Kokoro AI...")
    
    # URL 1: The ONNX Model (v0.19 - Compatible with standard library)
    model_url = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v0_19.onnx"
    # URL 2: The Voices JSON (Required for v0.19 compatibility)
    voices_url = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices.json"
    
    model_filename = "kokoro-v0_19.onnx"
    voices_filename = "voices.json"

    # Download Model if missing
    if not os.path.exists(model_filename):
        print(f"   -> Downloading {model_filename}...")
        try:
            response = requests.get(model_url, stream=True)
            response.raise_for_status()
            with open(model_filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            print(f"❌ Failed to download model: {e}")
            return None
                
    # Download Voices if missing
    if not os.path.exists(voices_filename):
        print(f"   -> Downloading {voices_filename}...")
        try:
            response = requests.get(voices_url, stream=True)
            response.raise_for_status()
            with open(voices_filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            print(f"❌ Failed to download voices: {e}")
            return None

    return Kokoro(model_filename, voices_filename)

def master_audio(file_path):
    """Post-processing to make audio sound like a studio recording."""
    try:
        sound = AudioSegment.from_file(file_path)
        # 1. Subtle Low Pass (Warmth)
        bass = sound.low_pass_filter(150)
        sound = sound.overlay(bass.apply_gain(-3))
        # 2. Compression (Even volume)
        sound = compress_dynamic_range(sound, threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
        # 3. Normalize (Loudness)
        sound = normalize(sound)
        sound.export(file_path, format="wav")
    except Exception as e:
        print(f"⚠️ Audio Mastering skipped: {e}")

def get_time_based_mode():
    """Decides content type based on UTC hour."""
    # GitHub Actions runs on UTC. 
    # 06:00 UTC = Morning | 18:00 UTC = Evening
    current_hour = datetime.now().hour
    print(f"🕒 Current UTC Hour: {current_hour}")
    
    if 4 <= current_hour < 16:
        return "STORY" # Horror/Urban Legend (Morning/Day)
    else:
        return "FACT" # Paradox/Science (Evening/Night)

def generate_script_data(mode):
    """Generates a viral script using Gemini with Chaos Seeds."""
    print(f"🧠 AI Director Mode: {mode}")
    url = get_dynamic_model_url()
    print(f"🔗 Using Model URL: {url.split('?')[0]}") # Log which model is being used
    headers = {'Content-Type': 'application/json'}
    
    # --- CHAOS SEEDS: Forces unique topics every time ---
    if mode == "STORY":
        seeds = ["Mirrors", "Abandoned Hospital", "Night Shift", "Forest", "Driving Alone", "Old Doll", "Phone Call", "Basement", "School at Night", "Elevator Game", "Sleep Paralysis", "The Backrooms"]
        selected_seed = random.choice(seeds)
        topic_prompt = f"A psychological horror story involving '{selected_seed}'."
        style = "Disturbingly realistic, paranoid, suspenseful."
    else:
        seeds = ["Time Travel Paradox", "The Ocean Depth", "Simulation Theory", "Human Brain Glitch", "Ancient Egypt Mystery", "Quantum Physics", "Mandela Effect", "Dark Internet Theory", "Space Anomalies"]
        selected_seed = random.choice(seeds)
        topic_prompt = f"A scientific paradox or dark fact about '{selected_seed}'."
        style = "Fast-paced, mind-bending, shocking."

    prompt_text = f"""
    You are an expert Viral Shorts Director. Write a script for a YouTube Short about: {topic_prompt}
    
    ### STRICT RETENTION RULES:
    1. **The Hook (0-3s):** The first line MUST be a 'Scroll-Stopper'. It must be a terrifying realization, a direct challenge to the viewer, or a visual shock.
    2. **Pacing:** Use "Glued" editing logic. No intro, no "Hello guys." Start immediately in the action.
    3. **Tone:** {style} Make it feel grounded and realistic. Avoid cheesy tropes; focus on uncanny valley or psychological fear.
    4. **Visuals:** The first "visual_keyword" MUST be aggressive (e.g., "scary eyes close up", "explosion", "shadow figure") to grab attention.
    
    ### REQUIRED JSON STRUCTURE:
    {{
        "title": "CLICKBAIT TITLE HERE (ALL CAPS) #shorts",
        "description": "2 sentence description with hashtags.",
        "tags": ["viral", "scary", "creepy", "shorts"],
        "lines": [
            {{ 
                "role": "narrator", 
                "text": "Stop. Don't look behind you.", 
                "visual_keyword": "terrified eyes close up" 
            }},
             {{ 
                "role": "victim", 
                "text": "I heard it breathing... right there.", 
                "visual_keyword": "dark figure in hallway" 
            }}
        ]
    }}
    
    ROLES TO USE: 
    - "narrator" (The authority/storyteller - Deep Voice)
    - "victim" (The person experiencing it - Panicked/Fast)
    - "demon" (The entity - Slow/Distorted)

    Constraint: Keep total script under 130 words. Make it unique. Do not use Markdown formatting.
    """
    
    data = { "contents": [{ "parts": [{"text": prompt_text}] }] }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            # Safety check if candidate exists
            if 'candidates' in result and result['candidates']:
                raw = result['candidates'][0]['content']['parts'][0]['text']
                # Clean up markdown formatting if Gemini adds it
                clean_json = raw.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_json)
        else:
            print(f"Gemini API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Gemini Exception: {e}")
    return None

def generate_audio_per_line(line_data, index, kokoro_engine):
    """Generates audio using Kokoro based on the role."""
    text = line_data["text"]
    role = line_data.get("role", "narrator")
    filename = f"temp_audio_{index}.wav"
    
    # Voice Selection
    voice_id = "bm_lewis" # Default Narrator (Deep British)
    speed = 0.9
    
    if role == "victim":
        voice_id = "am_michael" # American Fast (Panicked)
        speed = 1.2
    elif role == "demon":
        voice_id = "bm_lewis"
        speed = 0.65 # Extremely Slow & Scary
    
    # Generate Audio
    audio, sample_rate = kokoro_engine.create(text, voice=voice_id, speed=speed, lang="en-gb")
    sf.write(filename, audio, sample_rate)
    return filename

def download_specific_visual(keyword, filename, min_duration):
    """Downloads a vertical video from Pexels matching the keyword."""
    print(f"🎥 Visual Search: '{keyword}'")
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=8&orientation=portrait"
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            videos = r.json().get('videos', [])
            if not videos: 
                print("   -> No exact match, trying generic horror...")
                return download_specific_visual("scary dark abstract", filename, min_duration)
            
            # --- CHAOS VISUAL: Pick a random video from top 8 to avoid repetition ---
            # Filter videos that are long enough first
            valid_videos = [v for v in videos if v['duration'] >= min_duration]
            
            if valid_videos:
                # Pick random from valid ones
                best_video = random.choice(valid_videos)
            else:
                # Fallback: Pick random from any (we loop it later)
                best_video = random.choice(videos)
            
            # Get the best quality link
            video_files = best_video['video_files']
            # Sort by resolution (width * height) descending to get high quality
            video_files.sort(key=lambda x: x['width'] * x['height'], reverse=True)
            link = video_files[0]['link']
            
            with open(filename, "wb") as f:
                f.write(requests.get(link).content)
            return True
    except Exception as e:
        print(f"   -> Pexels Error: {e}")
    return False

def main_pipeline():
    # 1. Determine Content Mode (Story vs Fact)
    mode = get_time_based_mode()
    
    # 2. Generate Script & Metadata
    script_data = generate_script_data(mode)
    if not script_data: 
        print("❌ Failed to generate script.")
        return None, None
    
    kokoro = setup_kokoro()
    if not kokoro:
        print("❌ Failed to initialize Kokoro.")
        return None, None

    final_clips = []
    
    print(f"🎬 Title: {script_data['title']}")
    
    for i, line in enumerate(script_data["lines"]):
        # A. Audio Generation
        wav_file = generate_audio_per_line(line, i, kokoro)
        master_audio(wav_file) # Enhance audio
        
        audio_clip = AudioFileClip(wav_file)
        # Add a tiny pause for pacing
        pause = AudioClip(lambda t: 0, duration=0.1)
        audio_clip = concatenate_audioclips([audio_clip, pause])
        
        # B. Video Generation
        video_file = f"temp_video_{i}.mp4"
        # Download visual, passing audio duration to find a good match
        if download_specific_visual(line["visual_keyword"], video_file, audio_clip.duration):
            try:
                clip = VideoFileClip(video_file)
                
                # Loop video if it's shorter than audio
                if clip.duration < audio_clip.duration:
                    clip = clip.loop(duration=audio_clip.duration)
                else:
                    clip = clip.subclip(0, audio_clip.duration)
                
                # Resize/Crop to 9:16 Vertical (1080x1920)
                # First resize to be at least 1920px tall
                if clip.h < 1920:
                     clip = clip.resize(height=1920)
                
                # Center Crop
                clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)
                
                clip = clip.set_audio(audio_clip)
                final_clips.append(clip)
            except Exception as e: 
                print(f"   -> Clip Error: {e}")

    if not final_clips: 
        print("❌ No clips generated.")
        return None, None
    
    print("✂️ Rendering Final Video...")
    final_video = concatenate_videoclips(final_clips, method="compose")
    
    output_file = "final_video.mp4"
    # Using 'fast' preset for speed, crf 23 for balance
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, preset="fast", threads=4)
    
    return output_file, script_data

def upload_to_youtube(file_path, metadata):
    if not file_path: return
    print("🚀 Uploading to YouTube...")
    try:
        creds_dict = json.loads(YOUTUBE_TOKEN_VAL)
        creds = Credentials.from_authorized_user_info(creds_dict)
        youtube = build('youtube', 'v3', credentials=creds)
        
        body = {
            "snippet": {
                "title": metadata['title'], 
                "description": metadata['description'],
                "tags": metadata['tags'], 
                "categoryId": "24" # Entertainment
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
    # Uncomment anti_ban_sleep() when running in production/scheduled mode
    # anti_ban_sleep() 
    
    video_path, meta = main_pipeline()
    if video_path and meta: 
        upload_to_youtube(video_path, meta)
