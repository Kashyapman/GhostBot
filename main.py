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
import edge_tts
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

SFX_MAP = {
    "scream": "scream.mp3", "screaming": "scream.mp3", "shout": "scream.mp3",
    "knock": "knock.mp3", "banging": "knock.mp3",
    "footsteps": "footsteps.mp3", "walking": "footsteps.mp3", "running": "footsteps.mp3",
    "thud": "thud.mp3", "slam": "thud.mp3", "fell": "thud.mp3",
    "whisper": "whisper.mp3", "voice": "whisper.mp3", "hear": "whisper.mp3",
    "static": "static.mp3", "glitch": "static.mp3"
}

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
    
    # --- MULTI-CAST SCRIPT ---
    prompt_text = f"""
    You are a horror radio drama director. Write a script for a YouTube Short about: '{topic}'.
    
    OUTPUT FORMAT: JSON ONLY.
    {{
        "lines": [
            {{ "role": "narrator", "text": "It was 1954..." }},
            {{ "role": "victim", "text": "Wait! Who is that?" }},
            {{ "role": "demon", "text": "You... are... mine." }}
        ]
    }}

    ROLES:
    1. "narrator": Serious, documentary style.
    2. "victim": Panicked, fast.
    3. "demon": Deep, distorted.
    
    Max 130 words.
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

async def generate_dynamic_voice(script_data, filename="voice.mp3"):
    print(f"🎙️ Generating High-Quality Audio...")
    clips = []
    
    for i, line in enumerate(script_data.get("lines", [])):
        text = line["text"]
        role = line.get("role", "narrator")
        
        # --- AUDIO ENGINEERING ---
        # We use Edge-TTS but with specific pitch/rate shifts to separate characters.
        if role == "victim":
            voice_id = "en-US-GuyNeural"
            rate = "+20%" 
            pitch = "+5Hz"
        elif role == "demon":
            voice_id = "en-US-ChristopherNeural"
            rate = "-30%"   # Slow down massively
            pitch = "-20Hz" # Deepen massively
        else: # Narrator
            voice_id = "en-US-ChristopherNeural"
            rate = "-5%"
            pitch = "-5Hz"
            
        temp_file = f"temp_voice_{i}.mp3"
        communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
        await communicate.save(temp_file)
        
        if os.path.exists(temp_file):
            clip = AudioFileClip(temp_file)
            clips.append(clip)
            # Add pause
            clips.append(AudioClip(lambda t: 0, duration=0.2))

    if clips:
        final_audio = concatenate_audioclips(clips)
        final_audio.write_audiofile(filename)
        # Cleanup
        for i in range(len(script_data["lines"])):
            try: os.remove(f"temp_voice_{i}.mp3")
            except: pass
    else:
        print("❌ Audio Generation Failed")

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
    
    # 4. VOICE (Stable Edge-TTS)
    await generate_dynamic_voice(script_data, "voice.mp3")
    
    # 5. VISUALS (Fixed Static Issue)
    print("🎬 Downloading Multiple Clips...")
    search_query = "mystery investigation dark horror cinematic"
    headers = {"Authorization": PEXELS_KEY}
    orientation = 'portrait' if MODE == 'Short' else 'landscape'
    # Request 8 clips to ensure we have enough for fast cuts
    url = f"https://api.pexels.com/videos/search?query={search_query}&per_page=8&orientation={orientation}"
    
    r = requests.get(url, headers=headers)
    video_clips = []
    if r.status_code == 200:
        video_data = r.json()
        if video_data.get('videos'):
            for i, video in enumerate(video_data['videos']):
                target = video['video_files'][0] 
                with open(f"temp_{i}.mp4", "wb") as f:
                    f.write(requests.get(target['link']).content)
                try: 
                    clip = VideoFileClip(f"temp_{i}.mp4")
                    # Force clip to be 4 seconds max for fast pacing
                    if clip.duration > 4: clip = clip.subclip(0, 4)
                    video_clips.append(clip)
                except: pass

    if not video_clips: return None, None

    # 6. MIXING (Fixed Volume Issue)
    print("✂️ Mixing Audio Layers...")
    try:
        # Boost Voice Volume to 150%
        voice_clip = AudioFileClip("voice.mp3").volumex(1.5)
        
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
            # Lower Music Volume to 15% (Was 25%)
            music_clip = music_clip.subclip(0, voice_clip.duration).volumex(0.15)
            audio_layers.append(music_clip)
            
        sfx_clips = add_smart_sfx(voice_clip, full_script_text)
        audio_layers.extend(sfx_clips)
        
        final_audio = CompositeAudioClip(audio_layers)

        final_clips = []
        current_duration = 0
        clip_index = 0
        
        # Loop through downloaded clips to fill time
        while current_duration < voice_clip.duration:
            if clip_index >= len(video_clips): clip_index = 0 # Loop clips if we run out
            
            clip = video_clips[clip_index]
            
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
            
            # Trim clip if it goes over audio duration
            remaining_time = voice_clip.duration - current_duration
            if clip.duration > remaining_time:
                clip = clip.subclip(0, remaining_time)
            
            final_clips.append(clip)
            current_duration += clip.duration
            clip_index += 1
        
        final_video = concatenate_videoclips(final_clips, method="compose")
        final_video = final_video.set_audio(final_audio)
        
        output_file = "final_video.mp4"
        final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, preset="medium")
        
        voice_clip.close()
        for clip in video_clips: clip.close()
        for i in range(8): # Clean up all temp files
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
