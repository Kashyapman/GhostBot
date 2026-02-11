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
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]
MODE = "Short"

# --- FILES ---
TOPICS_FILE = "topics.txt"

SFX_MAP = {
    "scream": "scream.mp3", "screaming": "scream.mp3", "shout": "scream.mp3",
    "knock": "knock.mp3", "banging": "knock.mp3",
    "footsteps": "footsteps.mp3", "walking": "footsteps.mp3", "running": "footsteps.mp3",
    "thud": "thud.mp3", "slam": "thud.mp3", "fell": "thud.mp3",
    "whisper": "whisper.mp3", "voice": "whisper.mp3", "hear": "whisper.mp3",
    "static": "static.mp3", "glitch": "static.mp3"
}

def get_dynamic_model_url():
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"

def master_audio(file_path):
    print("🎚️ Mastering Audio (Bass Boost + Compression)...")
    try:
        sound = AudioSegment.from_file(file_path)
        bass = sound.low_pass_filter(150)
        sound = sound.overlay(bass.apply_gain(-2))
        sound = compress_dynamic_range(sound, threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
        sound = normalize(sound)
        sound.export(file_path, format="mp3")
    except Exception as e:
        print(f"⚠️ Audio Mastering Skipped: {e}")

def generate_script_data(topic):
    print(f"🧠 AI Director Visualizing: {topic}...")
    url = get_dynamic_model_url()
    headers = {'Content-Type': 'application/json'}
    
    # --- UPGRADED PROMPT: VISUAL KEYWORDS ---
    prompt_text = f"""
    You are a Horror Movie Director. Write a script for a YouTube Short about: '{topic}'.
    
    CRITICAL: For every single line of dialogue, you MUST provide a specific 2-3 word "visual_keyword" that describes what we should see.
    
    OUTPUT FORMAT: JSON ONLY.
    {{
        "lines": [
            {{ 
                "role": "narrator", 
                "text": "Imagine a clock that ticks backwards.", 
                "visual_keyword": "antique clock ticking fast" 
            }},
            {{ 
                "role": "victim", 
                "text": "Wait, why is the door open?", 
                "visual_keyword": "creepy open door dark hallway" 
            }},
            {{ 
                "role": "demon", 
                "text": "I have been waiting.", 
                "visual_keyword": "scary shadow figure silhouette" 
            }}
        ]
    }}

    ROLES:
    1. "narrator": Serious, deep.
    2. "victim": Panicked, fast.
    3. "demon": Distorted, slow.
    
    Max 140 words. Keep visual keywords simple for stock footage search.
    """
    
    data = { "contents": [{ "parts": [{"text": prompt_text}] }] }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result:
                raw = result['candidates'][0]['content']['parts'][0]['text']
                # Clean code blocks
                clean_json = raw.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_json)
    except Exception as e:
        print(f"Gemini Error: {e}")
    return None

def generate_metadata(topic, script_text):
    print("📈 Generating Viral Metadata...")
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
    except: pass
    return {"title": f"{topic} #shorts", "description": "Subscribe.", "tags": ["horror"]}

async def generate_audio_per_line(line_data, index):
    text = line_data["text"]
    role = line_data.get("role", "narrator")
    filename = f"temp_audio_{index}.mp3"
    
    # Character Settings
    voice_id = "en-US-ChristopherNeural"
    rate = "-5%"
    pitch = "-2Hz"
    
    if role == "victim":
        rate = "+25%" 
        pitch = "+2Hz"
    elif role == "demon":
        rate = "-20%"   
        pitch = "-15Hz" 
        
    communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
    await communicate.save(filename)
    return filename

def download_specific_visual(keyword, filename, duration_needed):
    print(f"🎥 Searching Pexels for: '{keyword}'...")
    headers = {"Authorization": PEXELS_KEY}
    # We search for 'portrait' orientation
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=3&orientation=portrait"
    
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            videos = r.json().get('videos', [])
            if not videos:
                # Fallback to generic horror if specific keyword fails
                print(f"⚠️ No results for '{keyword}', falling back...")
                url = f"https://api.pexels.com/videos/search?query=horror abstract&per_page=3&orientation=portrait"
                r = requests.get(url, headers=headers)
                videos = r.json().get('videos', [])

            if videos:
                # Try to find a video that is close to the needed duration
                best_video = videos[0]
                video_link = best_video['video_files'][0]['link']
                
                with open(filename, "wb") as f:
                    f.write(requests.get(video_link).content)
                return True
    except Exception as e:
        print(f"Pexels Error: {e}")
    return False

def add_smart_sfx(audio_clip, text):
    # Simple SFX layer
    text = text.lower()
    for key, file in SFX_MAP.items():
        if key in text:
            sfx_path = os.path.join("sfx", file)
            if os.path.exists(sfx_path):
                sfx = AudioFileClip(sfx_path).volumex(0.6)
                return CompositeAudioClip([audio_clip, sfx])
    return audio_clip

async def main_pipeline():
    # 1. Topic
    if not os.path.exists(TOPICS_FILE): 
        with open(TOPICS_FILE, "w") as f: f.write("The Grandfather Paradox")
    
    with open(TOPICS_FILE, 'r') as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
        
    if not lines:
        current_topic = "The Dark Forest Theory"
    else:
        current_topic = lines[0]
        # Rotate topic to end
        with open(TOPICS_FILE, 'w') as f:
            for t in lines[1:]: f.write(t + "\n")
            f.write(lines[0] + "\n")

    # 2. Script
    script_data = generate_script_data(current_topic)
    if not script_data: return None, None
    
    full_script_text = " ".join([l["text"] for l in script_data["lines"]])
    metadata = generate_metadata(current_topic, full_script_text)

    final_clips = []
    
    # 3. BUILD SCENE BY SCENE
    print("🎬 Assembling Scenes...")
    
    for i, line in enumerate(script_data["lines"]):
        # A. Audio
        audio_file = await generate_audio_per_line(line, i)
        
        # Master Audio Segment
        master_audio(audio_file)
        
        audio_clip = AudioFileClip(audio_file)
        # Add slight pause after line
        pause = AudioClip(lambda t: 0, duration=0.2)
        audio_clip = concatenate_audioclips([audio_clip, pause])
        
        # Add SFX if needed
        audio_clip = add_smart_sfx(audio_clip, line["text"])

        # B. Video (Matched to Audio Duration)
        video_file = f"temp_video_{i}.mp4"
        success = download_specific_visual(line["visual_keyword"], video_file, audio_clip.duration)
        
        if not success:
            # Create Black Clip fallback
            video_clip = ColorClip(size=(1080, 1920), color=(0,0,0), duration=audio_clip.duration)
        else:
            try:
                video_clip = VideoFileClip(video_file)
                # Loop video if shorter than audio
                if video_clip.duration < audio_clip.duration:
                    video_clip = video_clip.loop(duration=audio_clip.duration)
                else:
                    video_clip = video_clip.subclip(0, audio_clip.duration)
                
                # Resize for Shorts
                video_clip = video_clip.resize(height=1920)
                video_clip = video_clip.resize(width=1080) # Center crop handled by resize mostly
                # Force center crop to be safe
                w, h = video_clip.size
                if w > 1080:
                    video_clip = video_clip.crop(x1=w/2 - 540, width=1080, height=1920)
            except:
                video_clip = ColorClip(size=(1080, 1920), color=(0,0,0), duration=audio_clip.duration)

        # Set Audio
        video_clip = video_clip.set_audio(audio_clip)
        final_clips.append(video_clip)

        # Cleanup Temp Files immediately
        # (We keep them in memory as clips, delete files from disk)
        # Note: MoviePy needs the file to exist until write_videofile is called.
        # So we delete them at the very end.

    # 4. Final Mix
    print("✂️ Final Render...")
    final_video = concatenate_videoclips(final_clips, method="compose")
    
    # Background Music
    music_folder = "music"
    if os.path.exists(music_folder):
        m_files = [f for f in os.listdir(music_folder) if f.endswith("mp3")]
        if m_files:
            bg_music = AudioFileClip(os.path.join(music_folder, random.choice(m_files)))
            if bg_music.duration < final_video.duration:
                bg_music = audio_loop(bg_music, duration=final_video.duration)
            bg_music = bg_music.subclip(0, final_video.duration).volumex(0.15)
            
            final_audio = CompositeAudioClip([final_video.audio, bg_music])
            final_video = final_video.set_audio(final_audio)

    output_file = "final_video.mp4"
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac", fps=24)
    
    # Cleanup Files
    for i in range(len(script_data["lines"])):
        try: os.remove(f"temp_audio_{i}.mp3")
        except: pass
        try: os.remove(f"temp_video_{i}.mp4")
        except: pass

    return output_file, metadata

def upload_to_youtube(file_path, metadata):
    if not file_path: return
    print("🚀 Uploading...")
    try:
        creds_dict = json.loads(YOUTUBE_TOKEN_VAL)
        creds = Credentials.from_authorized_user_info(creds_dict)
        youtube = build('youtube', 'v3', credentials=creds)
        
        body = {
            "snippet": {
                "title": metadata['title'], 
                "description": metadata['description'],
                "tags": metadata['tags'], 
                "categoryId": "24" 
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
    loop = asyncio.get_event_loop()
    v, m = loop.run_until_complete(main_pipeline())
    if v and m: upload_to_youtube(v, m)
