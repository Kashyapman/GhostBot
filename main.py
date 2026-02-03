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
import asyncio
import torch
import soundfile as sf
import numpy as np
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
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

# --- FILES ---
TOPICS_FILE = "topics.txt"
LONG_QUEUE_FILE = "long_form_queue.txt"

# --- THE "DEEP VOICE" MASTER PROMPT ---
# This ensures the actor stays the same (The voice you liked).
BASE_VOICE = "A very deep, slow, monotonic male voice. The tone is terrifying, high-quality, and close to the microphone."

SFX_MAP = {
    "scream": "scream.mp3", "screaming": "scream.mp3", "shout": "scream.mp3",
    "knock": "knock.mp3", "banging": "knock.mp3",
    "footsteps": "footsteps.mp3", "walking": "footsteps.mp3", "running": "footsteps.mp3",
    "thud": "thud.mp3", "slam": "thud.mp3", "fell": "thud.mp3",
    "whisper": "whisper.mp3", "voice": "whisper.mp3", "hear": "whisper.mp3",
    "static": "static.mp3", "glitch": "static.mp3"
}

# --- GLOBAL AI MODELS (Load once to save time) ---
print("⏳ Loading Parler-TTS (This may take 2-3 mins)...")
device = "cpu" # GitHub Actions doesn't have GPU, so we force CPU
model = ParlerTTSForConditionalGeneration.from_pretrained("parler-tts/parler-tts-mini-v1").to(device)
tokenizer = AutoTokenizer.from_pretrained("parler-tts/parler-tts-mini-v1")
print("✅ AI Loaded.")

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

def generate_script_data(topic):
    print(f"Asking AI Director about: {topic} ({MODE} Mode)...")
    url = get_dynamic_model_url()
    headers = {'Content-Type': 'application/json'}
    
    # --- EMOTION-AWARE PROMPT ---
    prompt_text = f"""
    You are a horror director. Write a script for a YouTube Short about: '{topic}'.
    
    OUTPUT FORMAT: JSON ONLY.
    {{
        "lines": [
            {{ "text": "It was 1954...", "emotion": "neutral" }},
            {{ "text": "But the room was EMPTY!", "emotion": "fear" }},
            {{ "text": "He was never seen again.", "emotion": "ominous" }}
        ]
    }}

    RULES:
    1. "neutral" = The standard deep narration.
    2. "fear" = Urgent, slightly faster (but keep deep voice).
    3. "ominous" = Very slow, whispering.
    4. Max 100 words (Keep it short because AI generation is slow).
    """
    
    data = { "contents": [{ "parts": [{"text": prompt_text}] }] }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result:
                raw = result['candidates'][0]['content']['parts'][0]['text']
                clean_json = raw.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_json)
    except Exception as e:
        print(f"Gemini Error: {e}")
    return None

def generate_metadata(topic, script_text):
    print("📈 Generating Viral Metadata (SEO)...")
    url = get_dynamic_model_url()
    headers = {'Content-Type': 'application/json'}
    
    prompt_text = f"""
    You are a YouTube SEO Expert. Topic: '{topic}'. Script: '{script_text[:150]}...'.
    
    OUTPUT FORMAT: JSON ONLY.
    {{
      "title": "Viral Clickbait Title (Use ALL CAPS for 1 word)",
      "description": "3 sentences with hashtags.",
      "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
    }}
    """
    
    data = { "contents": [{ "parts": [{"text": prompt_text}] }] }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result:
                raw = result['candidates'][0]['content']['parts'][0]['text']
                clean_json = raw.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_json)
    except Exception as e:
        print(f"Metadata Error: {e}")
    
    return {
        "title": f"The Mystery of {topic}",
        "description": f"A short documentary about {topic}.",
        "tags": ["mystery", "scary", "horror"]
    }

def generate_parler_audio(script_data, filename="voice.wav"):
    print(f"🎙️ Generating High-Fidelity Audio (Parler-TTS)...")
    final_audio_list = []
    sample_rate = model.config.sampling_rate

    for i, line in enumerate(script_data.get("lines", [])):
        text = line["text"]
        emotion = line.get("emotion", "neutral")
        
        # --- THE CHARACTER LOCK ---
        # We start with the BASE_VOICE (The Deep Guy) and append the emotion.
        # This keeps the identity consistent.
        if emotion == "fear":
            description = BASE_VOICE + " He is speaking with urgency and slight panic."
        elif emotion == "ominous":
            description = BASE_VOICE + " He is whispering very slowly."
        else:
            description = BASE_VOICE + " He is narrating calmly."

        print(f"   Generating Line {i+1}: {emotion}...")
        
        # Parler Generation Logic
        input_ids = tokenizer(description, return_tensors="pt").input_ids.to(device)
        prompt_input_ids = tokenizer(text, return_tensors="pt").input_ids.to(device)
        
        generation = model.generate(input_ids=input_ids, prompt_input_ids=prompt_input_ids)
        audio_arr = generation.cpu().numpy().squeeze()
        final_audio_list.append(audio_arr)
        
        # Add slight pause between lines (0.3s silence)
        silence = np.zeros(int(sample_rate * 0.3))
        final_audio_list.append(silence)

    # Stitch it all together
    full_audio = np.concatenate(final_audio_list)
    sf.write(filename, full_audio, sample_rate)
    print("✅ Full Voiceover Ready.")

def add_smart_sfx(voice_clip, script_full_text):
    clean_text = re.sub(r'[^\w\s]', '', script_full_text).lower()
    words = clean_text.split()
    total_words = len(words)
    sfx_clips = []
    if total_words < 5: return []
    for index, word in enumerate(words):
        if word in SFX_MAP:
            sfx_path = os.path.join("sfx", SFX_MAP[word])
            if os.path.exists(sfx_path):
                est_time = (index / total_words) * (voice_clip.duration * 0.9)
                sfx = AudioFileClip(sfx_path).set_start(est_time).volumex(0.6)
                sfx_clips.append(sfx)
    return sfx_clips

def manage_topics():
    selected_topic = None
    if not os.path.exists(TOPICS_FILE): open(TOPICS_FILE, 'w').close()
    if not os.path.exists(LONG_QUEUE_FILE): open(LONG_QUEUE_FILE, 'w').close()

    if MODE == "Long":
        with open(LONG_QUEUE_FILE, 'r') as f:
            long_candidates = [l.strip() for l in f.readlines() if l.strip()]
        if long_candidates:
            selected_topic = long_candidates[0]
            with open(LONG_QUEUE_FILE, 'w') as f:
                for t in long_candidates[1:]: f.write(t + "\n")
            return selected_topic
            
    with open(TOPICS_FILE, 'r') as f:
        new_candidates = [l.strip() for l in f.readlines() if l.strip()]
    if new_candidates:
        selected_topic = new_candidates[0]
        with open(TOPICS_FILE, 'w') as f:
            for t in new_candidates[1:]: f.write(t + "\n")
        if MODE == "Short":
            with open(LONG_QUEUE_FILE, 'a') as f:
                f.write(selected_topic + "\n")
        return selected_topic

    return "The Unknown"

async def main_pipeline():
    print("🛡️ Engaging Anti-Ban Protocols...")
    sleep_seconds = random.randint(300, 1500) 
    print(f"😴 Humanizing: Waiting {sleep_seconds // 60} minutes...")
    await asyncio.sleep(sleep_seconds)

    # 1. TOPIC
    current_topic = manage_topics()
    print(f"🎬 Processing Topic: {current_topic}")

    # 2. SCRIPT
    script_data = generate_script_data(current_topic)
    if not script_data: return None, None
        
    full_script_text = " ".join([l["text"] for l in script_data["lines"]])
    print(f"📝 Script Preview: {full_script_text[:50]}...")
    
    # 3. METADATA
    metadata = generate_metadata(current_topic, full_script_text)
    
    # 4. VOICE (The New Parler Engine)
    generate_parler_audio(script_data, "voice.wav")
    
    # 5. VISUALS
    print("🎬 Downloading Video...")
    search_query = "mystery investigation dark document classified"
    headers = {"Authorization": PEXELS_KEY}
    orientation = 'portrait' if MODE == 'Short' else 'landscape'
    clip_count = 3 if MODE == 'Short' else 6 
    url = f"https://api.pexels.com/videos/search?query={search_query}&per_page={clip_count}&orientation={orientation}"
    
    r = requests.get(url, headers=headers)
    video_clips = []
    if r.status_code == 200:
        video_data = r.json()
        if video_data.get('videos'):
            for i, video in enumerate(video_data['videos']):
                target = video['video_files'][0] 
                with open(f"temp_{i}.mp4", "wb") as f:
                    f.write(requests.get(target['link']).content)
                try: video_clips.append(VideoFileClip(f"temp_{i}.mp4"))
                except: pass

    if not video_clips: return None, None

    # 6. MIXING
    print("✂️ Mixing Audio Layers...")
    try:
        voice_clip = AudioFileClip("voice.wav")
        
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
            
        sfx_clips = add_smart_sfx(voice_clip, full_script_text)
        audio_layers.extend(sfx_clips)
        
        final_audio = CompositeAudioClip(audio_layers)

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
            
        return output_file, metadata
        
    except Exception as e:
        print(f"❌ Editing Failed: {e}")
        return None, None

def upload_to_youtube(file_path, metadata):
    if not file_path: return
    print("🚀 Uploading to YouTube...")
    try:
        creds_dict = json.loads(YOUTUBE_TOKEN_VAL)
        creds = Credentials.from_authorized_user_info(creds_dict)
        youtube = build('youtube', 'v3', credentials=creds)
        
        title = metadata['title']
        if MODE == "Short" and "#shorts" not in title.lower():
            title += " #shorts"
            
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title[:100], 
                    "description": metadata['description'][:4500],
                    "tags": metadata['tags'], 
                    "categoryId": "24" 
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
        video_path, metadata = loop.run_until_complete(main_pipeline())
        if video_path and metadata: 
            upload_to_youtube(video_path, metadata)
    except Exception as e:
        print(f"Critical Error: {e}")
