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

from moviepy.editor import *
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
# Kept intact, but for True Crime, consider changing files to things like "camera_click.mp3", "police_siren.mp3", or "tape_recorder.mp3" later.
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
    print("🧠 Generating High Retention True Crime Script...")

    client = genai.Client(api_key=GEMINI_KEY)
    models_to_try = ["models/gemini-2.5-pro", "models/gemini-2.5-flash"]

    niche = random.choice([
        "Unsolved Disappearances",
        "Bizarre Heists",
        "People Who Faked Their Own Deaths",
        "The Most Elaborate Scams",
        "Crimes Solved Decades Later"
    ])

    prompt = f"""
You are an elite viral YouTube Shorts True Crime writer.

TOPIC: {niche}

STRICT RULES:
1. THE HOOK: The first line MUST be under 3 seconds and drop a massive, shocking fact immediately. (e.g. "He lived in her walls for six months before she noticed.")
2. THE LOOP: The script MUST end unresolved in a way that grammatically flows perfectly back into the first line. (e.g., Last line: "And the most terrifying part of it all is..." -> First line: "He lived in her walls...")
3. PACING: Break the script into short, punchy, fast-paced lines. Keep tension high.
4. TONE: Serious, investigative, grim, and highly suspenseful. No fictional horror, keep it grounded in gritty reality.
5. EMOTIONS: Assign realistic narrator emotions per line (e.g., "urgent", "grim", "disbelief", "whisper", "authoritative").

Return ONLY valid JSON in this format:
{{
  "title": "High curiosity viral title #shorts #truecrime",
  "description": "Curiosity driven description.",
  "tags": ["truecrime", "mystery", "shorts", "unsolved"],
  "recommended_voice_model": "Qwen-Standard-Storyteller",
  "lines": [
    {{
      "emotion": "urgent",
      "text": "Hook line goes here.",
      "visual_keyword": "police tape night"
    }}
  ]
}}
"""

    config = types.GenerateContentConfig(
        temperature=0.9,
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
        "title": "The Man Who Didn't Exist #shorts #truecrime",
        "description": "How did he vanish completely?",
        "tags": ["truecrime", "shorts", "mystery"],
        "recommended_voice_model": "Qwen-Standard-Storyteller",
        "lines": [
            {"emotion": "urgent", "text": "He walked into a room with no exits and was never seen again.", "visual_keyword": "dark empty room"},
            {"emotion": "grim", "text": "Police searched for months.", "visual_keyword": "police searching"},
            {"emotion": "whisper", "text": "But what they found...", "visual_keyword": "evidence folder"},
            {"emotion": "urgent", "text": "proves that", "visual_keyword": "shadowy figure"}
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
                    # Lowered SFX volume slightly for True Crime so it doesn't distract from the narration
                    sfx = AudioFileClip(path).volumex(0.20) 
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
        "query": f"{keyword} true crime detective evidence mystery dark",
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
    return ColorClip(size=(1080, 1920), color=(15, 15, 15), duration=duration)

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
    
    final_clips = []

    for i, line in enumerate(script["lines"]):
        try:
            wav_file = voice_engine.generate_acting_line(
                line["text"],
                i,
                emotion=line.get("emotion", "serious")
            )

            if not wav_file:
                continue

            audio_clip = AudioFileClip(wav_file)
            audio_clip = add_sfx(audio_clip, line["text"])

            video_file = f"temp_vid_{i}.mp4"
            clip = get_visual_clip(line["visual_keyword"], video_file, audio_clip.duration)

            clip = clip.fx(colorx, 0.85).set_audio(audio_clip)

            # High Retention Post-Processing: Hard cuts and fast flashes
            if i > 0:
                if random.random() < 0.2:
                    clip = clip.fadein(0.1, color=[255,255,255]) 
                else:
                    clip = clip.set_start(final_clips[-1].end)
            
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
            bg_music = AudioFileClip(chosen_track).volumex(0.08)
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
    return output
