import os
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

def generate_gemini_script(topic):
    """
    Directly hits the Gemini API URL, bypassing the buggy Python library.
    """
    print(f"Asking Gemini about: {topic}...")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    prompt_text = f"""
    You are a horror narrator. Write a script for a {MODE} video about: '{topic}'.
    Rules:
    - No intro (Start immediately with a hook).
    - Scary, suspenseful tone.
    - Max 150 words.
    - Do not include scene directions like [Intro] or *sound effects*, just the spoken text.
    - Do not use markdown (no **bold** or # headers).
    """
    
    data = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        # Check if the key is wrong or quota is full
        if response.status_code != 200:
            print(f"❌ Gemini API Error: {response.status_code} - {response.text}")
            # Fallback to a simpler model if Flash fails
            print("Trying fallback model (Gemini Pro)...")
            url_fallback = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
            response = requests.post(url_fallback, headers=headers, json=data)
            
        if response.status_code == 200:
            result = response.json()
            # Extract text safely
            script = result['candidates'][0]['content']['parts'][0]['text']
            return script.replace("*", "").strip()
        else:
            print("Both models failed.")
            return None
            
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

async def main_pipeline():
    # 1. READ TOPIC
    try:
        with open("topics.txt", "r") as f:
            topics = f.readlines()
        if not topics:
            print("No topics left in topics.txt! Using fallback.")
            current_topic = "The mystery of the dark forest" 
        else:
            current_topic = topics[0].strip()
    except FileNotFoundError:
        print("topics.txt not found! Using fallback.")
        current_topic = "The mystery of the deep ocean"

    # 2. GENERATE SCRIPT (New Direct Method)
    script_text = generate_gemini_script(current_topic)
    
    if not script_text:
        print("CRITICAL: Could not generate script. Stopping.")
        return None, None, None

    print("Script generated successfully.")
    
    # 3. GENERATE AUDIO (Edge TTS)
    print("Generating Audio...")
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(script_text, voice)
    await communicate.save("voice.mp3")
    
    # 4. GET VISUALS (Pexels)
    print("Downloading Video...")
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
                # Pick a mid-quality video to save bandwidth
                video_files.sort(key=lambda x: x['width'], reverse=True)
                target_video = video_files[0]['link']
                
                v_content = requests.get(target_video).content
                temp_name = f"temp_{i}.mp4"
                with open(temp_name, "wb") as f:
                    f.write(v_content)
                
                try:
                    clip = VideoFileClip(temp_name)
                    video_clips.append(clip)
                except Exception as e:
                    print(f"Skipping bad video file: {e}")
    else:
        print(f"Pexels Error: {r.text}")
        return None, None, None

    if not video_clips:
        print("No valid video clips found!")
        return None, None, None

    # 5. EDITING
    print("Editing...")
    try:
        audio = AudioFileClip("voice.mp3")
        final_clips = []
        current_duration = 0
        
        while current_duration < audio.duration:
            for clip in video_clips:
                if current_duration >= audio.duration: break
                
                if MODE == "Short":
                    clip = clip.resize(height=1920)
                    clip = clip.crop(x1=1166.6/2 - 540, y1=0, width=1080, height=1920)
                else:
                    clip = clip.resize(height=1080)

                final_clips.append(clip)
                current_duration += clip.duration
                
        final_video = concatenate_videoclips(final_clips, method="compose")
        final_video = final_video.set_audio(audio)
        final_video = final_video.subclip(0, audio.duration)
        
        output_file = "final_video.mp4"
        final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, preset="ultrafast")
        
        # Cleanup
        audio.close()
        for clip in video_clips: clip.close()
        for i in range(len(video_clips)):
            if os.path.exists(f"temp_{i}.mp4"): os.remove(f"temp_{i}.mp4")
            
        return output_file, current_topic, script_text
        
    except Exception as e:
        print(f"Editing Failed: {e}")
        return None, None, None

def upload_to_youtube(file_path, title, description):
    if not file_path: return
        
    print("Uploading to YouTube...")
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
                    "tags": ["shorts", "horror", "mystery", "scary"],
                    "categoryId": "24" 
                },
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        )
        response = request.execute()
        print(f"Uploaded! Video ID: {response.get('id')}")
    except Exception as e:
        print(f"Upload failed: {str(e)}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        video_path, topic, script = loop.run_until_complete(main_pipeline())
        if video_path:
            upload_to_youtube(video_path, f"{topic} #shorts", script)
    except Exception as e:
        print(f"Critical Error: {e}")
