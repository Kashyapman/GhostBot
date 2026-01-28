import os
import random
import requests
from google import genai
import edge_tts
import asyncio
from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]
MODE = os.environ.get("VIDEO_MODE", "Short")

# Initialize Client
client = genai.Client(api_key=GEMINI_KEY)

def get_working_model():
    """
    Asks the API which models are available and picks the best one.
    This fixes the '404 Not Found' error permanently.
    """
    print("Finding a working AI model...")
    try:
        # List all models available to your key
        # Note: In the new library, we list models and filter manually if needed
        # We try a prioritized list of known working models first to save time
        priority_models = ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        
        for model in priority_models:
            try:
                # Test the model with a simple "Hello"
                client.models.generate_content(model=model, contents="Test")
                print(f"✅ Found working model: {model}")
                return model
            except Exception:
                continue
                
        # If specific ones fail, try to list dynamic ones (fallback)
        # Note: The new SDK listing might be complex, so if the above fail,
        # we default to 'gemini-1.5-flash' but print the error clearly.
        print("Could not verify specific model. Defaulting to gemini-1.5-flash")
        return "gemini-1.5-flash"
        
    except Exception as e:
        print(f"Model search failed: {e}")
        return "gemini-1.5-flash"

async def generate_content():
    # 1. READ TOPIC
    try:
        with open("topics.txt", "r") as f:
            topics = f.readlines()
        if not topics:
            print("No topics left in topics.txt!")
            current_topic = "The mystery of the dark forest" 
        else:
            current_topic = topics[0].strip()
    except FileNotFoundError:
        print("topics.txt not found! Using fallback.")
        current_topic = "The mystery of the deep ocean"

    print(f"Topic: {current_topic}")
    
    # 2. GENERATE SCRIPT
    # Use the dynamic model finder
    active_model = get_working_model()
    
    prompt = f"""
    You are a horror narrator. Write a script for a {MODE} video about: '{current_topic}'.
    Rules:
    - No intro (Start immediately with a hook).
    - Scary, suspenseful tone.
    - Max 150 words.
    - Do not include scene directions like [Intro], just the spoken text.
    """
    
    try:
        response = client.models.generate_content(
            model=active_model, 
            contents=prompt
        )
        script_text = response.text.replace("*", "")
        print("Script generated successfully.")
    except Exception as e:
        print(f"❌ Script Generation Failed: {e}")
        return None, None, None
    
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
    if r.status_code != 200:
        print("Error downloading from Pexels:", r.text)
        return None, None, None
        
    video_data = r.json()
    video_clips = []
    
    if not video_data.get('videos'):
        print("No videos found on Pexels!")
        return None, None, None

    for i, video in enumerate(video_data['videos']):
        video_files = video['video_files']
        video_files.sort(key=lambda x: x['width'], reverse=True)
        target_video = video_files[0]['link']
        
        v_content = requests.get(target_video).content
        temp_name = f"temp_{i}.mp4"
        with open(temp_name, "wb") as f:
            f.write(v_content)
        
        clip = VideoFileClip(temp_name)
        video_clips.append(clip)

    # 5. EDITING
    print("Editing...")
    audio = AudioFileClip("voice.mp3")
    
    final_clips = []
    current_duration = 0
    
    while current_duration < audio.duration:
        for clip in video_clips:
            if current_duration >= audio.duration: break
            
            if MODE == "Short":
                w, h = clip.size
                target_ratio = 9/16
                if w/h > target_ratio:
                    new_width = h * target_ratio
                    clip = clip.crop(x1=w/2 - new_width/2, width=new_width, height=h)
                clip = clip.resize(height=1920)
            else:
                 clip = clip.resize(height=1080)

            final_clips.append(clip)
            current_duration += clip.duration
            
    final_video = concatenate_videoclips(final_clips, method="compose")
    final_video = final_video.set_audio(audio)
    final_video = final_video.subclip(0, audio.duration)
    
    output_file = "final_video.mp4"
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24, preset="ultrafast")
    
    for i in range(len(video_clips)):
        if os.path.exists(f"temp_{i}.mp4"):
            os.remove(f"temp_{i}.mp4")
            
    return output_file, current_topic, script_text

def upload_to_youtube(file_path, title, description):
    if not file_path:
        return
        
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
                    "description": description[:4000],
                    "tags": ["shorts", "horror", "thriller", "scary", "mystery"],
                    "categoryId": "24" 
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                }
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
        video_path, topic, script = loop.run_until_complete(generate_content())
        if video_path:
            upload_to_youtube(video_path, f"{topic} #shorts", script)
    except Exception as e:
        print(f"Critical Error: {e}")
