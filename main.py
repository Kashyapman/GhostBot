import os
import random
import time
import json
import requests
import numpy as np
import PIL.Image

from google import genai
from google.genai import types

from moviepy.editor import *
import moviepy.video.fx.all as vfx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from neural_voice import VoiceEngine


# ================== CONFIG ================== #

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
YOUTUBE_TOKEN_VAL = os.environ.get("YOUTUBE_TOKEN_JSON")

if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# ================== AUDIO ASSETS ================== #

SFX_MAP = {
    "knock": "knock.mp3",
    "bang": "knock.mp3",
    "scream": "scream.mp3",
    "yell": "scream.mp3",
    "step": "footsteps.mp3",
    "run": "footsteps.mp3",
    "static": "static.mp3",
    "glitch": "static.mp3",
    "breath": "whisper.mp3",
    "whisper": "whisper.mp3"
}

BG_MUSIC_FILE = "sfx/creepy_bg_drone.mp3" # Add a low drone track here for best results

# ================== ANTI BAN ================== #

def anti_ban_sleep():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        sleep_seconds = random.randint(300, 900)
        print(f"🕵️ Anti-Ban Sleep: {sleep_seconds//60} minutes")
        time.sleep(sleep_seconds)


# ================== SCRIPT ENGINEERING ================== #

def generate_viral_script():
    print("🧠 Generating Masterpiece Script...")

    client = genai.Client(api_key=GEMINI_KEY)
    models_to_try = ["models/gemini-2.5-pro", "models/gemini-2.5-flash"]

    niche = random.choice([
        "The Reflection That Moved First",
        "A glitch in reality caught on camera",
        "Rules for surviving the night shift",
        "The unsettling thing about the new house",
        "A distress call from an unknown depth"
    ])

    prompt = f"""
You are an elite YouTube Shorts horror storyteller. Your goal is absolute viewer retention.
Write a 6-9 line script about: {niche}

STRICT STORYTELLING RULES:
1. THE HOOK (Line 1): Must violently interrupt scrolling. Raise an immediate, terrifying question.
2. THE ESCALATION (Lines 2-5): Sentences max 8 words. Build psychological dread.
3. THE TWIST/CLIFFHANGER (Last Line): End abruptly on a terrifying realization. Do NOT resolve the story.
4. AI DIRECTING: Assign a specific voice type (e.g., 'deep_narrator', 'panicked_teen', 'creepy_whisper') and a driving emotion for every single line.

Return ONLY valid JSON in this exact format:
{{
  "title": "High curiosity viral title #shorts",
  "description": "Curiosity driven description.",
  "tags": ["horror", "scarystories", "creepy", "viral"],
  "lines": [
    {{
      "voice_type": "deep_narrator",
      "emotion": "ominous",
      "text": "Look closely at the corner of your screen.",
      "visual_keyword": "dark empty room shadowy"
    }}
  ]
}}
"""

    config = types.GenerateContentConfig(
        temperature=1.2,
        top_p=0.95,
        response_mime_type="application/json"
    )

    for model in models_to_try:
        try:
            print(f"Trying {model}...")
            response = client.models.generate_content(model=model, contents=prompt, config=config)

            if not response.text: continue
            data = json.loads(response.text)

            if "lines" in data and len(data["lines"]) >= 6:
                print(f"✅ Master script generated via {model}")
                return data

        except Exception as e:
            print(f"❌ Model error ({model}): {e}")
            continue

    return None


# ================== AUDIO MIXING ================== #

def mix_audio_track(base_audio_clip, text):
    text_lower = text.lower()
    clips_to_mix = [base_audio_clip]

    for k, v in SFX_MAP.items():
        if k in text_lower:
            path = os.path.join("sfx", v)
            if os.path.exists(path):
                try:
                    sfx = AudioFileClip(path).volumex(0.6)
                    if sfx.duration > base_audio_clip.duration:
                        sfx = sfx.subclip(0, base_audio_clip.duration)
                    clips_to_mix.append(sfx)
                except: pass

    return CompositeAudioClip(clips_to_mix)


# ================== VISUALS & EFFECTS ================== #

def get_cinematic_clip(keyword, filename, duration):
    headers = {"Authorization": PEXELS_KEY}
    url = "https://api.pexels.com/videos/search"
    params = {"query": f"{keyword} horror cinematic dark", "per_page": 5, "orientation": "portrait"}

    try:
        r = requests.get(url, headers=headers, params=params)
        data = r.json()

        if data.get("videos"):
            # Pick a random video from top 3 to keep footage fresh
            best = random.choice(data["videos"][:3])
            link = best["video_files"][0]["link"]

            with open(filename, "wb") as f:
                f.write(requests.get(link).content)

            clip = VideoFileClip(filename)

            if clip.duration < duration:
                loops = int(np.ceil(duration / clip.duration)) + 1
                clip = clip.loop(n=loops)

            clip = clip.subclip(0, duration)

            # Standardize resolution
            if clip.h < 1920: clip = clip.resize(height=1920)
            if clip.w < 1080: clip = clip.resize(width=1080)
            clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)

            # POST-PROCESSING: Cinematic Horror Grading
            clip = clip.fx(vfx.colorx, 0.7) # Darken image
            clip = clip.fx(vfx.lum_contrast, lum=-10, contrast=20) # Add gritty contrast
            
            return clip

    except Exception as e:
        print(f"Visual fetch failed: {e}")

    # Fallback eerie red/black pulse if API fails
    return ColorClip(size=(1080, 1920), color=(10, 0, 0), duration=duration)


# ================== MAIN PIPELINE ================== #

def main_pipeline():
    anti_ban_sleep()

    voice_engine = VoiceEngine()
    script = generate_viral_script()
    if not script: return None, None

    print(f"🎬 Title: {script['title']}")
    final_clips = []

    for i, line in enumerate(script["lines"]):
        try:
            # Pass dynamic voice and emotion from AI script
            wav_file = voice_engine.generate_acting_line(
                text=line["text"],
                index=i,
                voice_type=line.get("voice_type", "narrator"),
                emotion=line.get("emotion", "neutral")
            )

            if not wav_file: continue

            audio_clip = AudioFileClip(wav_file)
            final_audio = mix_audio_track(audio_clip, line["text"])

            video_file = f"temp_vid_{i}.mp4"
            # Add 0.5s padding for smooth crossfades
            clip_duration = final_audio.duration + 0.5 
            clip = get_cinematic_clip(line["visual_keyword"], video_file, clip_duration)

            # Sync audio and apply crossfade prep
            clip = clip.set_audio(final_audio)
            
            # Apply fade in/out for smooth transitions between segments
            clip = clip.crossfadein(0.5) if i > 0 else clip

            final_clips.append(clip)

        except Exception as e:
            print(f"Clip error at index {i}: {e}")

    if not final_clips:
        print("❌ No clips generated.")
        return None, None

    print("✂️ Rendering Final Composition...")

    # Compose with crossfades
    final_video = concatenate_videoclips(final_clips, padding=-0.5, method="compose")

    # Add master background music track if available
    if os.path.exists(BG_MUSIC_FILE):
        bg_music = AudioFileClip(BG_MUSIC_FILE).volumex(0.15).loop(duration=final_video.duration)
        final_mixed_audio = CompositeAudioClip([final_video.audio, bg_music])
        final_video = final_video.set_audio(final_mixed_audio)

    output_file = "final_video.mp4"
    final_video.write_videofile(
        output_file,
        codec="libx264",
        audio_codec="aac",
        fps=30, # Upgraded to 30fps for smoother shorts
        preset="fast"
    )

    return output_file, script


# ================== YOUTUBE UPLOAD ================== #

def upload_to_youtube(file_path, metadata):
    if not file_path: return
    print("🚀 Uploading to YouTube...")

    try:
        creds = Credentials.from_authorized_user_info(json.loads(YOUTUBE_TOKEN_VAL))
        youtube = build("youtube", "v3", credentials=creds)

        youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": metadata["title"],
                    "description": metadata["description"],
                    "tags": metadata["tags"],
                    "categoryId": "24"
                },
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        ).execute()

        print("✅ Upload Successful")
    except Exception as e:
        print(f"❌ Upload failed: {e}")

if __name__ == "__main__":
    video_path, metadata = main_pipeline()
    if video_path and metadata:
        upload_to_youtube(video_path, metadata)
