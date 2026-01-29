import os
import PIL.Image

# --- FIX FOR PILLOW ERROR ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ----------------------------

import random
import requests
import json
import re
import soundfile as sf
import numpy as np
from kokoro_onnx import Kokoro
from moviepy.editor import *
from moviepy.audio.fx.all import audio_loop
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]
MODE = os.environ.get("VIDEO_MODE", "Short")

# --- KOKORO VOICE SETTINGS ---
# 'bm_lewis' is a deep, calm American male voice perfect for horror.
# 'am_adam' is another option.
VOICE_ID = "bm_lewis" 

SFX_MAP = {
    "scream": "scream.mp3", "screaming": "scream.mp3", "shout": "scream.mp3",
    "knock": "knock.mp3", "banging": "knock.mp3",
    "footsteps": "footsteps.mp3", "walking": "footsteps.mp3", "running": "footsteps.mp3",
    "thud": "thud.mp3", "slam": "thud.mp3", "fell": "thud.mp3",
    "whisper": "whisper.mp3", "voice": "whisper.mp3", "hear": "whisper.mp3"
}

def download_kokoro_model():
    """
    Downloads the Kokoro model files (ONNX + Voices) automatically.
    This is the 'Deep Research' magic - running a high-end AI locally.
    """
    print("🧠 Downloading Kokoro AI Model...")
    
    files = {
        "kokoro-v0_19.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
        "voices.json": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"
    }
    
    for filename, url in files.items():
        if not os.path.exists(filename):
            print(f"   Downloading {filename}...")
            r = requests.get(url, stream=True)
            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
    print("✅ Model Ready.")

def get_dynamic_model_url():
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    try:
        response = requests.get(list_url)
        if response.status_code == 200:
            data = response.json()
            for model in data.get('models', []):
                if "generateContent" in model.get('supportedGenerationMethods', []):
                    return f"https://generativelanguage.googleapis.com/v1beta/{model['name']}:generateContent?key={GEMINI_KEY}"
    except: pass
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"

def generate_script(topic):
    print(f"Asking AI Director about: {topic}...")
    url = get_dynamic_model_url()
    headers = {'Content-Type': 'application/json'}
    
    max_words = "140" if MODE == "Short" else "300"
    
    # NOTE: Kokoro doesn't need SSML tags. It needs natural punctuation.
    prompt_text = f"""
    You are a horror audio director. Write a script for a {MODE} video about: '{topic}'.
    
    CRITICAL: Write in PLAIN TEXT. No XML. No SSML.
    INSTRUCTION: Use natural punctuation (...) for pauses.
    INSTRUCTION: Include these words naturally for SFX: 'knock', 'scream', 'footsteps', 'whisper'.
    
    Tone: Deep, ominous, slow.
    Max {max_words} words.
    """
    
    data = { "contents": [{ "parts": [{"text": prompt_text}] }] }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result:
                raw = result['candidates'][0]['content']['parts'][0]['text']
                return raw.replace("*", "").strip()
    except Exception as e:
        print(f"Gemini Error: {e}")
    return None

def add_smart_sfx(voice_clip, script_text):
    clean_text = re.sub(r'[^\w\s]', '', script_text).lower()
    words = clean_text.split()
    total_words = len(words)
    sfx_clips = []
    
    if total_words < 5: return []
    
    for index, word in enumerate(words):
        if word in SFX_MAP:
            sfx_path = os.path.join("sfx", SFX_MAP[word])
            if os.path.exists(sfx_path):
                # 0.9 factor to prevent SFX from playing after voice ends
                est_time = (index / total_words) * (voice_clip.duration * 0.9)
                sfx = AudioFileClip(sfx_path).set_start(est_time).volumex(0.6)
                sfx_clips.append(sfx)
    return sfx_clips

async def main_pipeline():
    # 0. SETUP KOKORO
    download_kokoro_model()
    kokoro = Kokoro("kokoro-v0_19.onnx", "voices.json")

    # 1. READ TOPIC
    current_topic = "The mystery of the dark forest" 
    try:
        with open("topics.txt", "r") as f:
            lines = f.readlines()
        topics = [line.strip() for line in lines if line.strip()]
        if topics:
            current_topic = topics[0]
            with open("topics.txt", "w") as f:
                for t in topics[1:]: f.write(t + "\n")
            print(f"✅ Selected Topic: {current_topic}")
        else:
            print("⚠️ No topics left! Using fallback.")
    except FileNotFoundError:
        print("⚠️ topics.txt not found! Using fallback.")

    # 2. GENERATE SCRIPT
    script_text = generate_script(current_topic)
    if not script_text: 
        script_text = f"I cannot explain what I saw in {current_topic}. It was beyond human understanding."

    print(f"📝 Script Preview: {script_text[:50]}...")
    
    # 3. GENERATE VOICE (THE KOKORO WAY)
    print("🎙️ Generating High-Fidelity Voice...")
    try:
        # Kokoro generates raw audio samples
        samples, sample_rate = kokoro.create(
            script_text, 
            voice=VOICE_ID, 
            speed=0.9, # 0.9 = Slightly slower/scarier
            lang="en-us"
        )
        # Save as WAV using soundfile
        sf.write("voice.wav", samples, sample_rate)
        print("✅ Audio Generated successfully.")
    except Exception as e:
        print(f"❌ Kokoro Failed: {e}")
        return None, None, None
    
    # 4. GET VISUALS
    print("🎬 Downloading Video...")
    search_query = "scary dark thriller"
    headers = {"Authorization": PEXELS_KEY}
    orientation = 'portrait' if MODE == 'Short' else 'landscape'
    clip_count = 3 if MODE == 'Short' else 5
    url = f"https://api.pexels.com/videos/search?query={search_query}&per_page={clip_count}&orientation={orientation}"
    
    r = requests.get(url, headers=headers)
    video_clips = []
    if r.status_code == 200:
        video_data = r.json()
        if video_data.get('videos'):
            for i, video in enumerate(video_data['videos']):
                video_files = video['video_files']
                video_files.sort(key=lambda x: x['width'], reverse=True)
                target = video_files[0]
                with open(f"temp_{i}.mp4", "wb") as f:
                    f.write(requests.get(target['link']).content)
                try: video_clips.append(VideoFileClip(f"temp_{i}.mp4"))
                except: pass

    if not video_clips: return None, None, None

    # 5. MIXING
    print("✂️ Mixing Audio Layers...")
    try:
        voice_clip = AudioFileClip("voice.wav") # Note: .wav extension
        
        # MUSIC LAYER
        music_folder = "music"
        music_files = []
        if os.path.exists(music_folder):
            music_files = [f for f in os.listdir(music_folder) if f.endswith(".mp3")]
        
        audio_layers = [voice_clip]
        
        if music_files:
            music_path = os.path.join(music_folder, random.choice(music_files))
            music_clip = AudioFileClip(music_path)
            if music_clip.duration < voice_clip.duration:
                music_clip = audio_loop(music_clip, duration=voice_clip.duration + 2)
            music_clip = music_clip.subclip(0, voice_clip.duration).volumex(0.25)
            audio_layers.append(music_clip)
            
        sfx_clips = add_smart_sfx(voice_clip, script_text)
        audio_layers.extend(sfx_clips)
        
        final_audio = CompositeAudioClip(audio_layers)

        # VIDEO STITCHING
        final_clips = []
        current_duration = 0
        while current_duration < voice_clip.duration:
            for clip in video_clips:
                if current_duration >= voice_clip.duration: break
                
                if MODE == "Short":
                    w, h = clip.size
                    if w > h: clip = clip.crop(x1=w/2 - h*(9/16)/2, width=h*(9/16), height=h)
                    clip = clip.resize(height=1920)
                    clip = clip.resize(width=1080)
                else:
                    clip = clip.resize(height=1080)
                    w, h = clip.size
                    if w/h != 16/9:
                         clip = clip.crop(x1=w/2 - (h*16/9)/2, width=h*16/9, height=h)
                         
                final_clips.append(clip)
                current_duration += clip.duration
        
        final_video = concatenate_videoclips(final_clips, method="compose")
        final_video = final_video.set_audio(final_audio)
        final_video = final_video.subclip(0, voice_clip.duration)
        
        output_file = "final_video.mp4"
        final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, preset="medium")
        
        voice_clip.close()
        for clip in video_clips: clip.close()
        for i in range(len(video_clips)): 
            if os.path.exists(f"temp_{i}.mp4"): os.remove(f"temp_{i}.mp4")
            
        return output_file, current_topic, f"Thriller story about {current_topic}"
        
    except Exception as e:
        print(f"❌ Editing Failed: {e}")
        return None, None, None

def upload_to_youtube(file_path, title, description):
    if not file_path: return
    print("🚀 Uploading to YouTube...")
    try:
        creds_dict = json.loads(YOUTUBE_TOKEN_VAL)
        creds = Credentials.from_authorized_user_info(creds_dict)
        youtube = build('youtube', 'v3', credentials=creds)
        tags = ["shorts", "horror"] if MODE == "Short" else ["horror", "thriller", "mystery", "documentary"]
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title[:100], "description": description[:4500],
                    "tags": tags, "categoryId": "24" 
                },
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        )
        response = request.execute()
        print(f"✅ Uploaded! Video ID: {response.get('id')}")
    except Exception as e:
        print(f"❌ Upload failed: {str(e)}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        video_path, topic, desc = loop.run_until_complete(main_pipeline())
        final_title = f"{topic} #shorts" if MODE == "Short" else topic
        if video_path: upload_to_youtube(video_path, final_title, desc)
    except Exception as e:
        print(f"Critical Error: {e}")
