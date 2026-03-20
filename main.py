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
from faster_whisper import WhisperModel

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from neural_voice import VoiceEngine

import meta_upload  

# ================== CONFIG ================== #

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY") 
PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
YOUTUBE_TOKEN_VAL = os.environ.get("YOUTUBE_TOKEN_JSON")
CHANNEL_HANDLE = "@TheGlitchArchive" 
TOPICS_FILE = "topics.txt"

if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

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

# ================== MEMORY SYSTEM ================== #

def get_past_topics():
    if not os.path.exists(TOPICS_FILE):
        return ""
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = f.read().splitlines()
    # Keep the last 100 cases to ensure a massive buffer against repetition
    return "\n".join(topics[-100:])

def save_new_topic(case_name):
    try:
        with open(TOPICS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{case_name}\n")
        print(f"💾 Saved '{case_name}' to memory bank.")
    except Exception as e:
        print(f"⚠️ Failed to save topic: {e}")

# ================== SCRIPT & SEO GENERATION ================== #

def generate_viral_script():
    print("🧠 Generating Master-Directed Script & SEO Metadata...")

    client = genai.Client(api_key=GEMINI_KEY)
    models_to_try = ["models/gemini-2.5-pro", "models/gemini-2.5-flash"]
    
    content_pool = [
        "Bizarre Unsolved Disappearances",
        "Impossible Heists and Robberies",
        "People Who Faked Their Own Deaths",
        "Crimes Solved Decades Later",
        "Real-life Glitches in the Matrix",
        "Creepy Mandela Effects",
        "Unexplained Time Slips",
        "Bizarre and Impossible Coincidences",
        "Bizarre Historical Artifacts That Shouldn't Exist",
        "Lost Civilizations and Vanished Towns",
        "Creepy Unsolved Mysteries from the 1800s",
        "Unexplained Deep Sea Anomalies and Sounds",
        "Ghost Ships Found Completely Abandoned",
        "Creepy Hijacked TV and Radio Broadcasts",
        "Mysterious Number Stations from the Cold War",
        "Unsolved Internet Rabbit Holes"
    ]
    
    niche = random.choice(content_pool)
    print(f"🎲 Selected Category for Today: {niche}")
    
    past_topics = get_past_topics()
    avoid_instruction = f"CRITICAL: Do NOT write about these specific historical cases, we have already covered them:\n{past_topics}\n" if past_topics else "No past topics yet."

    prompt = f"""
You are an elite viral YouTube Shorts writer, an Award-Winning Voice Director, AND a Master YouTube SEO Expert.
Your channel is called "The Glitch Archive" focusing on dark, eerie, and baffling stories.

TODAY'S TOPIC CATEGORY: {niche}

Your task is to write a highly engaging, high-retention short-form script about a highly specific, obscure case or event that fits this category. 
Do not invent a fake story; use a real, documented case, historical event, or widely reported anomaly, but focus on the most baffling aspects.

{avoid_instruction}

STRICT STORYTELLING & VIRAL RULES:
1. THE HOOK (0-3s): First line MUST drop a massive, shocking fact immediately. No background info.
2. OPEN LOOPS: Ask a compelling question early on, but delay the answer until the very end to force watch-time.
3. THE LOOP: The script MUST end abruptly on a cliffhanger that grammatically flows perfectly back into the first line of the video.
4. SSML MICRO-DIRECTION: Engineer the `acting_text` using strict SSML tags.
   - Use <prosody rate="slow" pitch="-2st" volume="soft"> for creepy lines.
   - Use <prosody rate="fast" pitch="+1st" volume="loud"> for urgent panics.
   - Use <break time="800ms"/> for dramatic pauses.
5. CASTING: Choose ONE specific voice model: "Charon" (gritty male), "Fenrir" (intense male), "Aoede" (haunting female), or "Kore" (unsettling female).
6. VISUAL KEYWORDS: Invent highly specific visual keywords for EVERY line to ensure high-quality B-roll fetching.
7. YOUTUBE SEO (ENGAGEMENT DRIVER):
   - title: Under 50 chars, Curiosity Gap, ends with #shorts #mystery.
   - case_name: Provide the actual historical name of the event/case to log it.
   - description: 3 lines of high-volume SEO keywords.
   - pinned_comment: Write a provocative, engaging question related to the case that the channel owner will pin to drive massive comments.
   - tags: Exactly 15 highly searched tags (mix of broad and long-tail).

Return ONLY valid JSON in this format:
{{
  "title": "They found WHAT in the walls? #shorts #mystery",
  "case_name": "The Discovery of the Somerton Man",
  "description": "Unsolved mysteries, scary stories, true crime documentary, bizarre historical events...",
  "pinned_comment": "If you found that note in your pocket, what would be your first move? Let me know 👇",
  "tags": ["mystery", "shorts", "unsolved", "scary", "glitch", "creepy"],
  "recommended_voice_model": "Charon",
  "lines": [
    {{
      "style_instruction": "Hushed, terrified whisper as if telling a dangerous secret.",
      "acting_text": "<prosody volume='soft' rate='slow'>He walked into the room...</prosody> <break time='1s'/> <emphasis level='strong'>and vanished.</emphasis>",
      "clean_text": "He walked into the room and vanished.",
      "visual_keyword": "muddy footprints on carpet"
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
            response = client.models.generate_content(model=model, contents=prompt, config=config)
            if response.text:
                data = json.loads(response.text)
                if "lines" in data and len(data["lines"]) > 0:
                    print(f"✅ Script & SEO generated with {model}")
                    return data
        except Exception as e:
            print(f"❌ Model error ({model}): {e}")
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print("⏳ Quota hit during script generation. Sleeping 5s before fallback...")
                time.sleep(5)
            continue

    if OPENROUTER_KEY:
        print("🔄 Gemini exhausted/failed. Falling back to OpenRouter (Llama 3.3 70B)...")
        try:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "messages": [{"role": "user", "content": prompt}]
            }
            
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            
            if r.status_code == 200:
                response_content = r.json()['choices'][0]['message']['content']
                cleaned_content = response_content.replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned_content)
                
                if "lines" in data and len(data["lines"]) > 0:
                    print("✅ Script & SEO generated with OpenRouter Fallback")
                    return data
            else:
                print(f"❌ OpenRouter request failed: {r.text}")
        except Exception as e:
            print(f"❌ OpenRouter Fallback error: {e}")

    return None

def generate_meta_caption(metadata):
    print("🤖 Generating optimized Meta caption...")
    client = genai.Client(api_key=GEMINI_KEY)
    
    prompt = f"""
    Write a highly engaging, suspenseful caption for a Facebook Reel and Instagram Reel about this mystery video:
    Video Title: {metadata['title']}
    Video Description: {metadata['description']}

    RULES:
    - The tone should be captivating and mysterious.
    - Include a call to action asking viewers to comment their thoughts.
    - Include 5-7 highly relevant, trending hashtags (e.g. #Mystery #Unsolved #Glitch).
    - Do not use any quotation marks around the final output.
    - Keep it under 150 words.
    """
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        print("✅ Meta Caption generated successfully with Gemini!")
        return response.text.strip()
    except Exception as e:
        print(f"❌ Gemini API Error for caption: {e}")
        
        if OPENROUTER_KEY:
            print("🔄 Falling back to OpenRouter for caption generation...")
            try:
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "meta-llama/llama-3.3-70b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}]
                }
                r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                if r.status_code == 200:
                    caption = r.json()['choices'][0]['message']['content'].strip()
                    caption = caption.strip('"') 
                    print("✅ Meta Caption generated successfully with OpenRouter!")
                    return caption
            except Exception as or_e:
                print(f"❌ OpenRouter API Error for caption: {or_e}")

        return f"{metadata['title']}\n\nWhat do you think happened? Let us know below! 👇\n\n#Mystery #Shorts #Unsolved #Creepy"

# ================== SFX ================== #

def add_sfx(audio_clip, text):
    text_lower = text.lower()
    for k, v in SFX_MAP.items():
        if k in text_lower:
            path = os.path.join("sfx", v)
            if os.path.exists(path):
                try:
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
        "query": f"{keyword} cinematic dark", 
        "per_page": 15, 
        "page": random.randint(1, 4), 
        "orientation": "portrait"
    }
    
    try:
        r = requests.get(url, headers=headers, params=params)
        data = r.json()
        
        if data.get("videos"):
            chosen_video = random.choice(data["videos"])
            best_file = max(chosen_video["video_files"], key=lambda x: x["width"] * x["height"])
            link = best_file["link"]
            
            with open(filename, "wb") as f:
                f.write(requests.get(link).content)

            clip = VideoFileClip(filename)
            # CRITICAL FIX: Strip Pexels raw audio to prevent bleed-through over TTS
            clip = clip.without_audio()
            
            if clip.duration < duration:
                loops = int(np.ceil(duration / clip.duration)) + 1
                clip = clip.loop(n=loops)
            clip = clip.subclip(0, duration)

            if clip.h < 1920: clip = clip.resize(height=1920)
            if clip.w < 1080: clip = clip.resize(width=1080)
            clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)
            return clip
    except Exception as e:
        pass
        
    return ColorClip(size=(1080, 1920), color=(15, 15, 15), duration=duration)

# ================== SUBTITLES ================== #

def add_dynamic_subtitles(video_clip, audio_path):
    print("📝 Transcribing audio for word-level subtitles...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, word_timestamps=True)

    subtitle_clips = []
    
    for segment in segments:
        for word in segment.words:
            clean_word = word.word.strip().upper()
            if not clean_word:
                continue

            try:
                txt_clip = TextClip(
                    clean_word,
                    fontsize=90,
                    color='yellow',
                    stroke_color='black',
                    stroke_width=3,
                    font='Impact',
                    method='caption',
                    size=(video_clip.w * 0.9, None)
                ).set_start(word.start).set_end(word.end).set_position(('center', video_clip.h * 0.70)) # Adjusted to UI Safe Zone
                
                subtitle_clips.append(txt_clip)
            except Exception as e:
                pass

    print(f"✅ Generated {len(subtitle_clips)} word captions!")
    return CompositeVideoClip([video_clip] + subtitle_clips)

# ================== MAIN PIPELINE ================== #

def main_pipeline():
    anti_ban_sleep()

    try:
        voice_engine = VoiceEngine()
    except Exception as e:
        print(f"Voice engine error: {e}")
        return None, None

    script = generate_viral_script()
    if not script:
        return None, None
        
    print(f"🎬 Title: {script['title']}")
    print(f"📁 Case Logged: {script.get('case_name', 'Unknown Case')}")
    print(f"🏷️ Tags: {', '.join(script['tags'][:5])}...")
    
    target_voice = script.get("recommended_voice_model", "Charon")
    print(f"🎙️ AI Casted Narrator: {target_voice}")
    
    final_clips = []

    for i, line in enumerate(script["lines"]):
        try:
            acting_input = line.get("acting_text", line.get("text"))
            style_instruction = line.get("style_instruction", "Serious and highly suspenseful.")
            clean_text = line.get("clean_text", line.get("text", ""))

            wav_file = voice_engine.generate_acting_line(
                acting_text=acting_input, 
                style_instruction=style_instruction,
                index=i, 
                voice_name=target_voice
            )

            if not wav_file:
                continue

            audio_clip = AudioFileClip(wav_file)
            audio_clip = add_sfx(audio_clip, clean_text)

            video_file = f"temp_vid_{i}.mp4"
            clip = get_visual_clip(line["visual_keyword"], video_file, audio_clip.duration)

            clip = clip.fx(colorx, 0.85).set_audio(audio_clip)

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

    print("✂️ Rendering Final Video with Transitions & Branding...")
    final_video = CompositeVideoClip(final_clips)

    temp_voice_track = "temp_master_voice.wav"
    final_video.audio.write_audiofile(temp_voice_track, fps=24000, logger=None)
    final_video = add_dynamic_subtitles(final_video, temp_voice_track)
    if os.path.exists(temp_voice_track):
        os.remove(temp_voice_track)

    try:
        # Puts watermark slightly lower to avoid overlapping with top-screen interactions
        watermark = TextClip(
            CHANNEL_HANDLE, 
            fontsize=40, 
            color='white', 
            font='Impact', 
            stroke_color='black', 
            stroke_width=2
        ).set_opacity(0.4).set_position(('center', 200)).set_duration(final_video.duration)
        final_video = CompositeVideoClip([final_video, watermark])
    except Exception as e:
        print(f"⚠️ Could not add watermark: {e}")

    print("🎵 Adding Background Music...")
    music_files = glob.glob("music/track*.mp3")
    
    if music_files:
        chosen_track = random.choice(music_files)
        try:
            bg_music = AudioFileClip(chosen_track).volumex(0.08)
            bg_music = audio_loop(bg_music, duration=final_video.duration)
            final_audio = CompositeAudioClip([final_video.audio, bg_music])
            final_video = final_video.set_audio(final_audio)
        except Exception as e:
            pass

    output_file = "final_video.mp4"
    final_video.write_videofile(
        output_file,
        codec="libx264",
        audio_codec="aac",
        fps=30,
        preset="fast",
        threads=4 
    )
    return output_file, script

# ================== YOUTUBE UPLOAD ================== #

def upload_to_youtube(file_path, metadata):
    if not file_path:
        return False
    print("🚀 Uploading to YouTube...")
    try:
        creds = Credentials.from_authorized_user_info(json.loads(YOUTUBE_TOKEN_VAL))
        youtube = build("youtube", "v3", credentials=creds)
        
        # Combine base description with the auto-generated pinned comment hook
        full_description = f"{metadata['description']}\n\n{metadata.get('pinned_comment', '')}"

        youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": metadata["title"],
                    "description": full_description,
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
        print("✅ YouTube Upload Successful")
        
        # NOTE: Automatically pinning comments via API requires advanced scopes and multi-step requests.
        # Placing the "comment hook" inside the description achieves a similar viewer-prompting effect.
        
        return True
    except Exception as e:
        print(f"❌ YouTube Upload failed: {e}")
        return False

# ================== CLEANUP ================== #

def cleanup_files(final_video):
    print("🧹 Starting cleanup phase...")
    try:
        if final_video and os.path.exists(final_video):
            os.remove(final_video)
            print(f"Deleted {final_video}")

        for f in glob.glob("temp_vid_*.mp4"):
            os.remove(f)
            
        for f in glob.glob("temp_*.wav"):
            os.remove(f)
            
        print("✅ Cleanup complete!")
    except Exception as e:
        print(f"⚠️ Error during cleanup: {e}")

# ================== ENTRY ================== #

if __name__ == "__main__":
    video_path, metadata = main_pipeline()
    
    if video_path and metadata:
        upload_success = upload_to_youtube(video_path, metadata)
        
        if upload_success:
            # Safely get the case_name, fallback to title if the AI formats weirdly
            case_to_save = metadata.get('case_name', metadata['title'])
            save_new_topic(case_to_save)
            
            meta_caption = generate_meta_caption(metadata)
            meta_upload.upload_to_facebook(video_path, meta_caption)
            
            temp_public_url = meta_upload.get_temp_public_url(video_path)
            if temp_public_url:
                meta_upload.upload_to_instagram(temp_public_url, meta_caption)
            else:
                print("⏭️ Skipping Instagram due to temporary host failure.")
        
        cleanup_files(video_path)
        
    print("🎉 Daily GhostBot execution finished!")
