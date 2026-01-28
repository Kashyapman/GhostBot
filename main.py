import os
import PIL.Image

# --- FIX FOR "ANTIALIAS" ERROR ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ---------------------------------

import random
import requests
import edge_tts
import asyncio
import json
from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]
MODE = os.environ.get("VIDEO_MODE", "Short")

def get_dynamic_model_url():
    """
    Dynamically finds a working model name to prevent 404 errors.
    """
    print("🔍 Scanning for available AI models...")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    
    try:
        response = requests.get(list_url)
        if response.status_code == 200:
            data = response.json()
            for model in data.get('models', []):
                if "generateContent" in model.get('supportedGenerationMethods', []):
                    return f"https://generativelanguage.googleapis.com/v1beta/{model['name']}:generateContent?key={GEMINI_KEY}"
            
    except Exception as e:
        print(f"⚠️ Model scan failed: {e}")

    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"

def generate_gemini_script(topic):
    print(f"Asking AI about: {topic}...")
    url = get_dynamic_model_url()
    headers = {'Content-Type': 'application/json'}
    
    # IMPROVED PROMPT FOR EMOTION
    prompt_text = f"""
    You are a horror narrator. Write a script for a {MODE} video about: '{topic}'.
    Rules:
    - No intro. Start immediately with a hook.
    - Write in SHORT, PUNCHY sentences.
    - Use '...' to indicate dramatic pauses between scary moments.
    - Tone: Deep, slow, ominous.
    - Max 140 words.
    - Plain text only (no markdown).
    """
    
    data = { "contents": [{ "parts": [{"text": prompt_text}] }] }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            try:
                script = result['candidates'][0]['content']['parts'][0]['text']
                return script.replace("*", "").strip()
            except (KeyError, IndexError):
                return None
        return None
    except Exception:
        return None

async def main_pipeline():
    # 1. READ TOPIC (RANDOMIZED FIX)
    try:
        with open("topics.txt", "r") as f:
            topics = [line.strip() for line in f.readlines() if line.strip()]
            
        if not topics:
            print("No topics left! Using fallback.")
            current_topic = "The mystery of the dark forest" 
        else:
            # THIS IS THE FIX: Pick a random one, not the first one
            current_topic = random.choice(topics)
            
    except FileNotFoundError:
        print("topics.txt not found! Using fallback.")
        current_topic = "The mystery of the deep ocean"

    # 2. GENERATE SCRIPT
    script_text = generate_gemini_script(current_topic)
    if not script_text:
        print("CRITICAL: Script generation failed.")
        return None, None, None

    print("📜 Script generated successfully.")
    
    # 3. GENERATE AUDIO (EMOTIONAL TUNING)
    print("🎙️ Generating Audio...")
    # British voice + Slower Rate + Lower Pitch = Scary Documentary Vibe
    voice = "en-GB-RyanNeural" 
    communicate = edge_tts.Communicate(script_text, voice, rate="-10%", pitch="-2Hz")
    await communicate.save("voice.mp3")
    
    # 4. GET VISUALS
    print("🎬 Downloading Video...")
    search_query = "scary dark mystery"
    headers = {"Authorization": PEXELS_KEY}
    orientation = 'portrait' if MODE == 'Short' else 'landscape'
    url = f"https://api.pexels.com/videos/search?query={search_query}&per_page=3&orientation={orientation}"
    
    r = requests.get(url, headers=headers)
    video_clips = []
    
    if r.status_code == 200:
        video_data = r.json()
        if video_data.get('videos'):
            for i, video in enumerate(video_data['videos']):
                video_files = video['video_files']
                video_files.sort(key=lambda x: x['width'], reverse=True)
                target_video = next((v for v in video_files if v['width'] <= 1920), video_files[0])
                
                v_content = requests.get(target_video['link']).content
                temp_name = f"temp_{i}.mp4"
                with open(temp_name, "wb") as f:
                    f.write(v_content)
                
                try:
                    clip = VideoFileClip(temp_name)
                    video_clips.append(clip)
                except Exception:
                    pass
    
    if not video_clips:
        print("❌ No valid video clips found!")
        return None, None, None

    # 5. EDITING
    print("✂️ Editing...")
    try:
        audio = AudioFileClip("voice.mp3")
        final_clips = []
        current_duration = 0
        
        while current_duration < audio.duration:
            for clip in video_clips:
                if current_duration >= audio.duration: break
                
                if MODE == "Short":
                    w, h = clip.size
                    if w > h:
                        clip = clip.crop(x1=w/2 - h*(9/16)/2, width=h*(9/16), height=h)
                    clip = clip.resize(height=1920)
                    clip = clip.resize(width=1080)
                else:
                    clip = clip.resize(height=1080)

                final_clips.append(clip)
                current_duration += clip.duration
                
        final_video = concatenate_videoclips(final_clips, method="compose")
        final_video = final_video.set_audio(audio)
        final_video = final_video.subclip(0, audio.duration)
        
        output_file = "final_video.mp4"
        final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, preset="ultrafast")
        
        audio.close()
        for clip in video_clips: clip.close()
            
        return output_file, current_topic, script_text
        
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
        
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title[:100],
                    "description": description[:4500],
                    "tags": ["shorts", "horror", "mystery"],
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
        video_path, topic, script = loop.run_until_complete(main_pipeline())
        if video_path:
            upload_to_youtube(video_path, f"{topic} #shorts", script)
    except Exception as e:
        print(f"Critical Error: {e}")
