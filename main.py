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
import re # Added for cleaning SSML
from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]
MODE = os.environ.get("VIDEO_MODE", "Short")

# --- VOICE SETTINGS ---
# We use 'en-US-DavisNeural' because it supports 'terrified' and 'whispering' styles
VOICE_NAME = "en-US-DavisNeural"

def get_dynamic_model_url():
    # ... (Same logic as before to find model) ...
    print("🔍 Scanning for available AI models...")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    try:
        response = requests.get(list_url)
        if response.status_code == 200:
            data = response.json()
            for model in data.get('models', []):
                if "generateContent" in model.get('supportedGenerationMethods', []):
                    return f"https://generativelanguage.googleapis.com/v1beta/{model['name']}:generateContent?key={GEMINI_KEY}"
    except Exception:
        pass
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"

def generate_ssml_script(topic):
    print(f"Asking AI Director about: {topic}...")
    url = get_dynamic_model_url()
    headers = {'Content-Type': 'application/json'}
    
    # --- THE MAGIC PROMPT (SSML INJECTION) ---
    prompt_text = f"""
    You are a horror audio director. Create a script for a {MODE} video about: '{topic}'.
    
    CRITICAL OUTPUT RULE: You must output ONLY valid SSML (Speech Synthesis Markup Language) code.
    
    Use the voice '{VOICE_NAME}'.
    Use these specific styles to create fear:
    - <mstts:express-as style="whispering"> (For scary reveals)
    - <mstts:express-as style="terrified"> (For panic moments)
    - <mstts:express-as style="sad"> (For hopeless moments)
    
    Structure Format:
    <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'>
      <voice name='{VOICE_NAME}'>
        <mstts:express-as style="whispering">
           Start with a scary hook here...
        </mstts:express-as>
        <break time="500ms"/>
        <mstts:express-as style="terrified">
           Reveal the monster or twist here!
        </mstts:express-as>
      </voice>
    </speak>

    Content Rules:
    - Total length: Max 150 words.
    - No markdown formatting (like ```xml). Just the raw XML string.
    """
    
    data = { "contents": [{ "parts": [{"text": prompt_text}] }] }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            try:
                raw_ssml = result['candidates'][0]['content']['parts'][0]['text']
                # Clean up if Gemini adds markdown code blocks
                clean_ssml = raw_ssml.replace("```xml", "").replace("```", "").strip()
                return clean_ssml
            except (KeyError, IndexError):
                return None
        return None
    except Exception:
        return None

async def main_pipeline():
    # 1. READ TOPIC
    try:
        with open("topics.txt", "r") as f:
            topics = [line.strip() for line in f.readlines() if line.strip()]
        if not topics:
            current_topic = "The mystery of the dark forest" 
        else:
            current_topic = random.choice(topics)
    except FileNotFoundError:
        current_topic = "The mystery of the deep ocean"

    # 2. GENERATE SSML SCRIPT
    ssml_script = generate_ssml_script(current_topic)
    if not ssml_script:
        print("CRITICAL: Script generation failed.")
        return None, None, None

    print("📜 SSML Script generated. Directing Audio...")
    
    # 3. GENERATE AUDIO (USING SSML)
    print("🎙️ Generating Emotional Audio...")
    
    # Note: When using SSML, we pass the raw XML string to communicate
    communicate = edge_tts.Communicate(ssml_script, VOICE_NAME)
    await communicate.save("voice.mp3")
    
    # 4. GET VISUALS (Same as before)
    print("🎬 Downloading Video...")
    search_query = "scary dark thriller"
    headers = {"Authorization": PEXELS_KEY}
    orientation = 'portrait' if MODE == 'Short' else 'landscape'
    url = f"[https://api.pexels.com/videos/search?query=](https://api.pexels.com/videos/search?query=){search_query}&per_page=3&orientation={orientation}"
    
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
            
        # For metadata, we need a plain text version of the title/desc
        # We'll just use the Topic + generic tags since parsing the SSML for text is complex
        return output_file, current_topic, f"A thriller story about {current_topic}"
        
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
                    "tags": ["shorts", "horror", "mystery", "thriller"],
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
        video_path, topic, desc = loop.run_until_complete(main_pipeline())
        if video_path:
            upload_to_youtube(video_path, f"{topic} #shorts", desc)
    except Exception as e:
        print(f"Critical Error: {e}")
