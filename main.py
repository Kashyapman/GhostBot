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
            # Try to find Gemini 1.5 Flash first
            for model in data.get('models', []):
                if "generateContent" in model.get('supportedGenerationMethods', []):
                    if "gemini-1.5-flash" in model['name']:
                        return f"https://generativelanguage.googleapis.com/v1beta/{model['name']}:generateContent?key={GEMINI_KEY}"
            # Fallback to any available generating model
            for model in data.get('models', []):
                if "generateContent" in model.get('supportedGenerationMethods', []):
                    return f"https://generativelanguage.googleapis.com/v1beta/{model['name']}:generateContent?key={GEMINI_KEY}"
    except: pass
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"

def setup_kokoro():
    """Initializes Kokoro TTS from stable Hugging Face links (v0.19)."""
    print("🧠 Initializing Kokoro AI...")
    model_url = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v0_19.onnx"
    voices_url = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices.json"
    model_filename = "kokoro-v0_19.onnx"
    voices_filename = "voices.json"

    if not os.path.exists(model_filename):
        print("   -> Downloading Model...")
        r = requests.get(model_url); open(model_filename, "wb").write(r.content)
    if not os.path.exists(voices_filename):
        print("   -> Downloading Voices...")
        r = requests.get(voices_url); open(voices_filename, "wb").write(r.content)

    return Kokoro(model_filename, voices_filename)

def master_audio(file_path):
    """Studio-grade mastering for a warm, human-friendly chest voice."""
    try:
        sound = AudioSegment.from_file(file_path)
        # Warmth: Low pass filter at 3500Hz removes robotic high-end hiss
        sound = sound.low_pass_filter(3500) 
        sound = compress_dynamic_range(sound, threshold=-20.0, ratio=4.0)
        sound = normalize(sound)
        sound.export(file_path, format="wav")
    except: pass

def get_time_based_mode():
    current_hour = datetime.now().hour
    print(f"🕒 Current UTC Hour: {current_hour}")
    if 4 <= current_hour < 16:
        return "STORY"
    else:
        return "FACT"

def generate_script_data(mode):
    """Generates unique, human-centric scripts using layered chaos seeds."""
    print(f"🧠 AI Human Director Mode: {mode}")
    url = get_dynamic_model_url()
    
    # --- CHAOS ENGINE ---
    scenarios = ["a discovery", "a warning", "a secret", "a glitch", "a memory"]
    locations = ["empty playground", "your own bathroom", "late-night subway", "abandoned room", "foggy highway"]
    fears = ["eyes where they shouldn't be", "mimic sounds", "missing time", "shifting objects"]
    
    selected_topic = f"{random.choice(scenarios)} in a {random.choice(locations)} involving {random.choice(fears)}"

    prompt_text = f"""
    Write a cinematic, human-friendly Short script about: {selected_topic}
    
    ### RULES:
    1. Hook: Start with a personal question or 'You' statement.
    2. Role: Use 'narrator' for 90% of the script to maintain flow.
    3. Content: Focus on psychological 'Uncanny Valley' vibes, not monsters.
    
    ### JSON STRUCTURE:
    {{
        "title": "SCARY CLICKBAIT TITLE",
        "description": "Engaging viral description.",
        "tags": ["creepy", "relatable", "human"],
        "lines": [
            {{ "role": "narrator", "text": "Hook line here...", "visual_keyword": "cinematic moody lighting" }},
            {{ "role": "narrator", "text": "Building suspense...", "visual_keyword": "uncanny dark atmosphere" }},
            {{ "role": "victim", "text": "Impact dialogue line.", "visual_keyword": "shocked reaction" }},
            {{ "role": "narrator", "text": "Final twist.", "visual_keyword": "black screen fading" }}
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
    role = line_data.get("role", "narrator")
    filename = f"temp_audio_{index}.wav"
    
    voice_id = "bm_lewis"
    speed = 0.95 if role == "narrator" else 1.1
    
    audio, sample_rate = kokoro_engine.create(text, voice=voice_id, speed=speed, lang="en-gb")
    sf.write(filename, audio, sample_rate)
    return filename

def download_specific_visual(keyword, filename, min_duration):
    """Picks a random high-quality visual from top 5 search results."""
    print(f"🎥 Visual Search: '{keyword}'")
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=5&orientation=portrait"
    try:
        r = requests.get(url, headers=headers).json()
        if not r.get('videos'): 
             # Fallback if no specific video found
             return download_specific_visual("dark abstract horror", filename, min_duration)
        
        # Randomly pick from top 5 to ensure variety
        best_v = random.choice(r['videos'])
        link = best_v['video_files'][0]['link']
        
        # Sort files by quality to ensure we get a good one (highest resolution first)
        video_files = best_v['video_files']
        video_files.sort(key=lambda x: x['width'] * x['height'], reverse=True)
        link = video_files[0]['link']

        with open(filename, "wb") as f:
            f.write(requests.get(link).content)
        return True
    except Exception as e: 
        print(f"   -> Visual Download Error: {e}")
        return False

def main_pipeline():
    mode = get_time_based_mode()
    script_data = generate_script_data(mode)
    if not script_data: 
        print("❌ Script generation failed.")
        return None, None
    
    kokoro = setup_kokoro()
    final_clips = []
    
    print(f"🎬 Title: {script_data['title']}")
    
    for i, line in enumerate(script_data["lines"]):
        wav_file = generate_audio_per_line(line, i, kokoro)
        master_audio(wav_file)
        
        audio_clip = AudioFileClip(wav_file)
        # Natural Breath Pause (0.2s)
        pause = AudioClip(lambda t: 0, duration=0.2)
        audio_clip = concatenate_audioclips([audio_clip, pause])
        
        video_file = f"temp_video_{i}.mp4"
        if download_specific_visual(line["visual_keyword"], video_file, audio_clip.duration):
            try:
                clip = VideoFileClip(video_file)
                
                # --- BLACK SCREEN FIX: LOOPING LOGIC ---
                if clip.duration < audio_clip.duration:
                    # Calculate how many loops needed to cover audio
                    n_loops = int(np.ceil(audio_clip.duration / clip.duration)) + 1
                    clip = clip.loop(n_loops)
                
                # Trim to exact audio length
                clip = clip.subclip(0, audio_clip.duration)
                
                # Resize and Crop to Vertical 9:16
                clip = clip.resize(height=1920)
                if clip.w < 1080:
                    clip = clip.resize(width=1080)
                clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)
                
                # Apply Audio and Smooth Transitions
                clip = clip.set_audio(audio_clip).fadein(0.4).fadeout(0.4)
                final_clips.append(clip)
            except Exception as e:
                print(f"   -> Clip Processing Error: {e}")

    if not final_clips: 
        print("❌ No valid clips produced.")
        return None, None
    
    print("✂️ Rendering Cohesive Master...")
    final_video = concatenate_videoclips(final_clips, method="compose")
    output_file = "final_video.mp4"
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, preset="fast")
    
    return output_file, script_data

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
    # anti_ban_sleep() # Uncomment for random delays
    v, m = main_pipeline()
    if v and m: upload_to_youtube(v, m)
