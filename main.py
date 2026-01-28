import os
import random
import requests
import google.generativeai as genai
import edge_tts
import asyncio
from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]
MODE = os.environ.get("VIDEO_MODE", "Short") # Default to Short

genai.configure(api_key=GEMINI_KEY)

async def generate_content():
    # 1. READ TOPIC
    with open("topics.txt", "r") as f:
        topics = f.readlines()
    if not topics:
        print("No topics left!")
        return
    current_topic = topics[0].strip()
    
    # 2. GENERATE SCRIPT (Thriller Style)
    model = genai.GenerativeModel('gemini-pro')
    prompt = f"""
    You are a horror narrator. Write a script for a {MODE} video about: '{current_topic}'.
    Rules:
    - No intro (Start immediately with a hook).
    - Scary, suspenseful tone.
    - Max 150 words.
    - Do not include scene directions like [Intro], just the spoken text.
    """
    response = model.generate_content(prompt)
    script_text = response.text.replace("*", "")
    
    # 3. GENERATE AUDIO (Edge TTS)
    print("Generating Audio...")
    voice = "en-US-ChristopherNeural" # Deep male voice
    communicate = edge_tts.Communicate(script_text, voice)
    await communicate.save("voice.mp3")
    
    # 4. GET VISUALS (Pexels)
    print("Downloading Video...")
    search_query = "scary dark forest fog" # Generic spooky fallback
    headers = {"Authorization": Pexels_KEY}
    url = f"https://api.pexels.com/videos/search?query={search_query}&per_page=3&orientation={'portrait' if MODE=='Short' else 'landscape'}"
    r = requests.get(url, headers=headers)
    video_data = r.json()
    
    video_clips = []
    for video in video_data['videos']:
        video_file = video['video_files'][0]['link']
        v_content = requests.get(video_file).content
        with open(f"temp_{video['id']}.mp4", "wb") as f:
            f.write(v_content)
        clip = VideoFileClip(f"temp_{video['id']}.mp4")
        video_clips.append(clip)

    # 5. EDITING
    print("Editing...")
    audio = AudioFileClip("voice.mp3")
    
    # Loop video clips to match audio duration
    final_clips = []
    current_duration = 0
    while current_duration < audio.duration:
        for clip in video_clips:
            if current_duration >= audio.duration: break
            # Resize for shorts if needed
            if MODE == "Short":
                clip = clip.resize(height=1920)
                clip = clip.crop(x1=1166.6/2 - 540, y1=0, width=1080, height=1920)
            
            final_clips.append(clip)
            current_duration += clip.duration
            
    final_video = concatenate_videoclips(final_clips)
    final_video = final_video.set_audio(audio)
    final_video = final_video.subclip(0, audio.duration)
    
    output_file = "final_video.mp4"
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24)
    
    return output_file, current_topic, script_text

def upload_to_youtube(file_path, title, description):
    print("Uploading to YouTube...")
    # Load credentials from the JSON string stored in secrets
    import json
    creds_dict = json.loads(YOUTUBE_TOKEN_VAL)
    creds = Credentials.from_authorized_user_info(creds_dict)
    
    youtube = build('youtube', 'v3', credentials=creds)
    
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["shorts", "horror", "thriller", "scary"],
                "categoryId": "24" # Entertainment
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        },
        media_body=MediaFileUpload(file_path)
    )
    response = request.execute()
    print(f"Uploaded! Video ID: {response['id']}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    video_path, topic, script = loop.run_until_complete(generate_content())
    
    # Generate Title/Desc with AI
    upload_to_youtube(video_path, f"{topic} #shorts", script)
