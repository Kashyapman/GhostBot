import os
import random
import time
import json
import glob
import requests
import numpy as np
import PIL.Image

from google import genai
from google.genai import types

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ColorClip,
    concatenate_videoclips
)
from moviepy.video.fx.all import colorx
from moviepy.audio.fx.all import audio_loop

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from neural_voice import VoiceEngine

# ================== CONFIG ================== #

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]

if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# ================== SFX MAP ================== #

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
    "whisper": "whisper.mp3",
    "thud": "thud.mp3"
}

# ================== ANTI BAN ================== #

def anti_ban_sleep():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        sleep_seconds = random.randint(300, 900)
        print(f"🕵️ Anti-Ban Sleep: {sleep_seconds//60} minutes")
        time.sleep(sleep_seconds)

# ================== SCRIPT GENERATION ================== #

def generate_viral_script():
    print("🧠 Generating High Retention Script...")

    client = genai.Client(api_key=GEMINI_KEY)
    models_to_try = ["models/gemini-2.5-pro", "models/gemini-2.5-flash"]

    niche = random.choice([
        "The Mirror That Blinked",
        "The Thing Under The Bed",
        "The Fake Human Next Door",
        "Unknown Caller at 3AM",
        "The Door That Wasn't There Yesterday"
    ])

    prompt = f"""
You are an elite viral YouTube Shorts horror writer.

TOPIC: {niche}

STRICT RULES:
- First line MUST interrupt scrolling instantly.
- NO LIMIT on script length. Write a complete, highly engaging story.
- Escalate tension throughout. Add micro cliffhangers. End unresolved.
- Psychological horror only.
- Analyze the script's overall vibe and invent a specific descriptive voice model name for it (e.g., "Qwen-Cinematic-DeepMale", "Qwen-Terrified-Female", "Qwen-Distorted-Entity", "Qwen-Standard-Storyteller").
- For EACH line, assign a specific "emotion" (e.g., whispering, terrified, sinister, panicked).

Return ONLY valid JSON in this format:
{{
  "title": "High curiosity viral title #shorts",
  "description": "Curiosity driven description.",
  "tags": ["horror", "shorts", "viral", "scary"],
  "recommended_voice_model": "Qwen-Cinematic-DeepMale",
  "lines": [
    {{
      "emotion": "urgent",
      "text": "Hook line goes here",
      "visual_keyword": "dark hallway portrait"
    }}
  ]
}}
"""

    config = types.GenerateContentConfig(
        temperature=1.1,
        top_p=0.95,
        response_mime_type="application/json"
    )

    for model in models_to_try:
        try:
            print(f"Trying {model}...")
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )

            if not response.text:
                continue

            data = json.loads(response.text)

            if "lines" in data and len(data["lines"]) > 0:
                print(f"✅ Script generated with {model}")
                return data

        except Exception as e:
            print(f"❌ Model error ({model}): {e}")
            continue

    print("⚠️ All AI models failed — using fallback script")
    return {
        "title": "Don't Look Behind You #shorts",
        "description": "Something is standing there.",
        "tags": ["horror", "shorts"],
        "recommended_voice_model": "Qwen-Cinematic-DeepMale",
        "lines": [
            {"emotion": "urgent", "text": "Stop scrolling. Now.", "visual_keyword": "dark hallway portrait"},
            {"emotion": "terrified", "text": "[gasps] Did you hear that?", "visual_keyword": "scared face closeup"}
        ]
    }

# ================== SFX ================== #

def add_sfx(audio_clip, text):
    text_lower = text.lower()
    for k, v in SFX_MAP.items():
        if k in text_lower:
            path = os.path.join("sfx", v)
            if os.path.exists(path):
                try:
                    sfx = AudioFileClip(path).volumex(0.35)
                    if sfx.duration > audio_clip.duration:
                        sfx = sfx.subclip(0, audio_clip.duration)
                    return CompositeAudioClip([audio_clip, sfx])
                except:
                    pass
    return audio_clip

# ================== VISUAL FETCH ================== #

def get_visual_clip(keyword, filename, duration):
    headers = {"Authorization": PEXELS_KEY}
    url = "https://api.pexels.com/videos/search"
    params = {
        "query": f"{keyword} horror cinematic dark portrait",
        "per_page": 3,
        "orientation": "portrait"
    }
    try:
        r = requests.get(url, headers=headers, params=params)
        data = r.json()
        if data.get("videos"):
            best = max(data["videos"], key=lambda x: x["width"] * x["height"])
            link = best["video_files"][0]["link"]
            with open(filename, "wb") as f:
                f.write(requests.get(link).content)

            clip = VideoFileClip(filename)
            if clip.duration < duration:
                loops = int(np.ceil(duration / clip.duration)) + 1
                clip = clip.loop(n=loops)
            clip = clip.subclip(0, duration)

            if clip.h < 1920: clip = clip.resize(height=1920)
            if clip.w < 1080: clip = clip.resize(width=1080)
            clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)
            return clip
    except:
        pass
    return ColorClip(size=(1080, 1920), color=(0, 0, 0), duration=duration)

# ================== MAIN PIPELINE ================== #

def main_pipeline():
    anti_ban_sleep()

    try:
        voice_engine = VoiceEngine()
    except Exception as e:
        print(f"Voice engine error: {e}")
        return None, None

    script = generate_viral_script()
    print(f"🎬 Title: {script['title']}")
    
    # Extract the AI's chosen voice model for the entire script
    target_model = script.get("recommended_voice_model", "Qwen-Standard")
    print(f"🤖 AI Selected Voice Profile: {target_model}")

    final_clips = []

    for i, line in enumerate(script["lines"]):
        try:
            # Pass text, requested model, and emotion
            wav_file = voice_engine.generate_acting_line(
                line["text"],
                i,
                requested_model=target_model,
                emotion=line.get("emotion", "neutral")
            )

            if not wav_file:
                continue

            audio_clip = AudioFileClip(wav_file)
            audio_clip = add_sfx(audio_clip, line["text"])

            video_file = f"temp_vid_{i}.mp4"
            clip = get_visual_clip(line["visual_keyword"], video_file, audio_clip.duration)

            clip = clip.fx(colorx, 0.75).set_audio(audio_clip)

            if i > 0:
                clip = clip.set_start(final_clips[-1].end - 0.5).crossfadein(0.5)
            else:
                clip = clip.fadein(0.5)
            
            clip = clip.fadeout(0.2)
            final_clips.append(clip)

        except Exception as e:
            print(f"Clip error: {e}")

    if not final_clips:
        print("❌ No clips generated.")
        return None, None

    print("✂️ Rendering Final Video with Transitions...")
    final_video = CompositeVideoClip(final_clips)

    # --- ADD BACKGROUND MUSIC ---
    print("🎵 Adding Background Music...")
    music_files = glob.glob("music/track*.mp3")
    
    if music_files:
        chosen_track = random.choice(music_files)
        print(f"Selected BG Music: {chosen_track}")
        try:
            bg_music = AudioFileClip(chosen_track).volumex(0.12)
            bg_music = audio_loop(bg_music, duration=final_video.duration)
            final_audio = CompositeAudioClip([final_video.audio, bg_music])
            final_video = final_video.set_audio(final_audio)
        except Exception as e:
            print(f"⚠️ Failed to apply BG music: {e}")

    output_file = "final_video.mp4"
    final_video.write_videofile(
        output_file,
        codec="libx264",
        audio_codec="aac",
        fps=24,
        preset="fast"
    )
    return output_file, script

# ================== YOUTUBE UPLOAD ================== #

def upload_to_youtube(file_path, metadata):
    if not file_path:
        return
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
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                }
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        ).execute()
        print("✅ Upload Successful")
    except Exception as e:
        print(f"❌ Upload failed: {e}")

# ================== ENTRY ================== #

if __name__ == "__main__":
    video_path, metadata = main_pipeline()
    if video_path and metadata:
        upload_to_youtube(video_path, metadata)
