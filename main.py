import os
import random
import time
import json
import requests
import numpy as np
import PIL.Image
from datetime import datetime

from google import genai
from google.genai import types

from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from neural_voice import VoiceEngine

# ---------------- CONFIG ---------------- #

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]

if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# ------------- SFX MAP ------------------ #

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

# ----------- ANTI BAN ------------------- #

def anti_ban_sleep():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        sleep_seconds = random.randint(300, 900)
        print(f"🕵️ Sleeping {sleep_seconds//60} minutes (anti-spam)")
        time.sleep(sleep_seconds)

# ----------- MODEL DISCOVERY ------------ #

def get_available_models(client):
    valid_models = []
    try:
        for m in client.models.list():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
    except:
        return ["models/gemini-1.5-flash"]

    valid_models.sort(key=lambda x: 0 if 'flash' in x.lower() else 1)
    return valid_models

# ----------- SCRIPT GENERATION ---------- #

def generate_viral_script():
    print("🧠 Generating HIGH RETENTION Script...")

    client = genai.Client(api_key=GEMINI_KEY)
    models = get_available_models(client)

    niches = [
        "The Fake Human Next Door",
        "The Mirror That Blinked",
        "The 3AM Rule You Broke",
        "The Thing Under The Bed",
        "The Figure Behind You",
        "Unknown Caller at 3AM",
        "The Door That Wasn't There Yesterday"
    ]

    niche = random.choice(niches)

    prompt = f"""
You are an elite viral YouTube Shorts horror writer.

TOPIC: {niche}

STRICT RULES:
- First line MUST stop scrolling.
- Max 8 words per sentence.
- Escalate tension every 2 lines.
- Add micro cliffhangers.
- End unresolved.
- Psychological horror only.
- 6–9 lines total.
- 35–50 seconds length pacing.

Use audio tags naturally:
[gasps]
[laughs]
[sighs]
...

Return VALID JSON ONLY in this structure:

{{
  "title": "High curiosity viral title #shorts",
  "description": "Curiosity driven description.",
  "tags": ["horror", "shorts", "viral", "scary"],
  "lines": [
    {{
      "role": "narrator",
      "text": "Hook line",
      "visual_keyword": "cinematic horror portrait"
    }}
  ]
}}
"""

    config = types.GenerateContentConfig(
        temperature=1.15,
        top_p=0.95,
        top_k=40,
        response_mime_type="application/json"
    )

    for model in models:
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

            # Validate minimum structure
            if "lines" in data and len(data["lines"]) >= 3:
                return data

        except Exception as e:
            print(f"Model error: {e}")
            continue

    print("⚠️ AI failed — using fallback")

    return {
        "title": "Don't Look Behind You #shorts",
        "description": "Something is standing there.",
        "tags": ["horror", "shorts"],
        "lines": [
            {"role": "narrator", "text": "Stop scrolling. Now.", "visual_keyword": "dark hallway portrait"},
            {"role": "victim", "text": "[gasps] I heard that.", "visual_keyword": "scared face closeup"},
            {"role": "demon", "text": "You shouldn't have looked.", "visual_keyword": "shadow figure portrait"}
        ]
    }

# ----------- SFX ------------------------ #

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

# ----------- VISUALS -------------------- #

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

            if clip.h < 1920:
                clip = clip.resize(height=1920)
            if clip.w < 1080:
                clip = clip.resize(width=1080)

            clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)

            return clip

    except:
        pass

    return ColorClip(size=(1080, 1920), color=(0, 0, 0), duration=duration)

# ----------- MAIN PIPELINE -------------- #

def main_pipeline():
    anti_ban_sleep()

    try:
        voice_engine = VoiceEngine()
    except Exception as e:
        print(f"Voice engine error: {e}")
        return None, None

    script = generate_viral_script()

    print(f"🎬 Title: {script['title']}")

    final_clips = []

    for i, line in enumerate(script["lines"]):
        try:
            wav = voice_engine.generate_acting_line(
                line["text"],
                i,
                line.get("role", "narrator")
            )

            if not wav:
                continue

            audio_clip = AudioFileClip(wav)
            audio_clip = add_sfx(audio_clip, line["text"])

            video_file = f"temp_vid_{i}.mp4"
            clip = get_visual_clip(line["visual_keyword"], video_file, audio_clip.duration)

            clip = clip.set_audio(audio_clip).fadein(0.2).fadeout(0.2)
            final_clips.append(clip)

        except Exception as e:
            print(f"Clip error: {e}")

    if not final_clips:
        print("No clips generated.")
        return None, None

    print("Rendering final video...")
    final = concatenate_videoclips(final_clips, method="compose")

    out_file = "final_video.mp4"

    final.write_videofile(
        out_file,
        codec="libx264",
        audio_codec="aac",
        fps=24,
        preset="fast"
    )

    return out_file, script

# ----------- YOUTUBE UPLOAD ------------- #

def upload_to_youtube(file_path, metadata):
    if not file_path:
        return

    print("Uploading to YouTube...")

    try:
        creds = Credentials.from_authorized_user_info(json.loads(YOUTUBE_TOKEN_VAL))
        youtube = build('youtube', 'v3', credentials=creds)

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

        print("Upload successful.")

    except Exception as e:
        print(f"Upload failed: {e}")

# ----------- ENTRY POINT ---------------- #

if __name__ == "__main__":
    video, meta = main_pipeline()
    if video and meta:
        upload_to_youtube(video, meta)
