import os
import random
import time
import json
import glob
import requests
import urllib.parse
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
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")
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
    print("🧠 Generating Master-Directed Dual Script (Audio + Visuals)...")

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
You are an elite viral YouTube Shorts writer, an Award-Winning Voice Director, AND a Master Visual Editor.
Your channel is "The Glitch Archive" focusing on dark, eerie, and baffling historical true crime/mysteries.

TODAY'S TOPIC CATEGORY: {niche}

Your task is to write a highly engaging, high-retention short-form script about a highly specific, obscure case or event that fits this category. 
Do not invent a fake story; use a real, documented case, historical event, or widely reported anomaly.

{avoid_instruction}

STRICT STORYTELLING & VIRAL RULES:
1. THE HOOK (0-3s): First line MUST drop a bizarre paradox, an impossible fact, or a terrifying anomaly immediately.
2. NATURAL PACING: Do not restrict yourself to a specific word count. Write an immersive story. Focus on building suspense.
3. OPEN LOOPS: Ask a compelling question early on, but delay the answer until the very end.
4. THE PERFECT LOOP: End abruptly on a cliffhanger that grammatically flows perfectly back into the first line.

VOICE ACTING & EXPRESSION DIRECTION (CRITICAL FOR REALISM):
- recommended_voice_model: Choose ONE specific voice model: "Charon" (gritty male), "Fenrir" (intense male), "Aoede" (haunting female), or "Kore" (unsettling female).
- style_instruction: A short note on the vibe (e.g., "Hushed, terrified whisper.")
- EXPRESSION TAGS (SSML): You MUST use highly detailed SSML tags inside `acting_text`.
  - <break time="0.5s"/> to <break time="2.0s"/> for suspenseful pauses.
  - <emphasis level="strong"> for shocking words.
  - <prosody rate="slow" pitch="low"> for dark, creeping explanations.
- Keep the `clean_text` completely free of XML tags.

VISUAL DIRECTOR INSTRUCTIONS (CRITICAL FOR RETENTION):
Shorts require a visual change every 2.5 to 4 seconds. For EVERY line of dialogue, you MUST provide an array of 2 to 3 `visuals`. 
You must choose between REAL EVIDENCE or AI GENERATION for each visual:
- RULE A (REAL EVIDENCE): If referencing a real artifact, person, or document, write a highly specific Google Image query. (e.g., "Somerton Man 1948 unedited crime scene photo" or "Nampa Image doll 1889 close up").
- RULE B (AI GENERATION): If the scene was never photographed or impossible to find, you MUST start the keyword with "AI_GEN: " followed by a descriptive prompt. (e.g., "AI_GEN: A dark, muddy tunnel deep underground with a cracked stone figure").

YOUTUBE SEO:
- title: Write a highly engaging title. End with #shorts #mystery.
- case_name: Provide the actual historical name of the event/case to log it.
- description: 3 lines of high-volume SEO keywords.
- pinned_comment: Write a provocative, engaging question related to the case.
- tags: Exactly 15 highly searched tags.

Return ONLY valid JSON in this format:
{{
  "title": "They found WHAT in the walls? #shorts #mystery",
  "case_name": "The Discovery of the Somerton Man",
  "description": "Unsolved mysteries, scary stories, true crime documentary...",
  "pinned_comment": "If you found that note in your pocket, what would be your first move? Let me know 👇",
  "tags": ["mystery", "shorts", "unsolved", "scary", "glitch", "creepy"],
  "recommended_voice_model": "Charon",
  "lines": [
    {{
      "style_instruction": "Hushed, terrified whisper as if telling a dangerous secret.",
      "acting_text": "<prosody rate='slow' pitch='low'>He walked into the room...</prosody> <break time='1.5s'/> and <emphasis level='strong'>vanished</emphasis>.",
      "clean_text": "He walked into the room and vanished.",
      "visuals": [
        "AI_GEN: Shadowy silhouette of a man walking into a pitch black 1950s hotel room",
        "Somerton Man hotel room 1948 crime scene photo",
        "AI_GEN: Dusty footprints disappearing into thin air on a worn carpet"
      ]
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

# ================== DYNAMIC VISUAL FETCH ================== #

def fetch_ai_image(prompt, filename):
    """Generates an image using SOTA FLUX.1 via Pollinations.ai"""
    full_prompt = f"{prompt}, highly detailed, photorealistic, dark cinematic lighting, eerie true crime documentary style, 8k resolution"
    encoded_prompt = urllib.parse.quote(full_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true"
    r = requests.get(url)
    if r.status_code == 200:
        with open(filename, "wb") as f:
            f.write(r.content)
        return True
    return False

def get_image_clip(keyword, duration, index):
    """Fetches real historical images or SOTA AI images and applies Alternating Ken Burns."""
    img_filename = f"temp_img_{index}.jpg"
    success = False
    
    # PATH A: SOTA AI Image Generation
    if keyword.startswith("AI_GEN:"):
        clean_prompt = keyword.replace("AI_GEN:", "").strip()
        print(f"🪄 Generating SOTA AI Image: {clean_prompt[:40]}...")
        success = fetch_ai_image(clean_prompt, img_filename)
        
    # PATH B: Real Evidence (Google Image Search)
    else:
        print(f"🔍 Searching Google for Evidence: {keyword}")
        if GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "q": f"{keyword} real historical photo evidence", 
                "cx": GOOGLE_CSE_ID, "key": GOOGLE_SEARCH_API_KEY,
                "searchType": "image", "num": 1, "safe": "active"
            }
            try:
                r = requests.get(url, params=params).json()
                if "items" in r:
                    img_url = r["items"][0]["link"]
                    with open(img_filename, "wb") as f:
                        f.write(requests.get(img_url).content)
                    success = True
                else:
                    print("⚠️ No Google results found. Falling back to AI Image...")
            except Exception as e:
                print(f"⚠️ Google API error: {e}")
        
        # SOTA Fallback if Google fails to find the historical photo
        if not success:
            success = fetch_ai_image(keyword, img_filename)

    # Absolute fallback (Black screen) if both APIs completely fail
    if not success or not os.path.exists(img_filename):
        return ColorClip(size=(1080, 1920), color=(15, 15, 15), duration=duration)

    # APPLY ALTERNATING KEN BURNS EFFECT
    try:
        clip = ImageClip(img_filename).set_duration(duration)
        
        # Ensure image completely fills the 9:16 vertical frame
        clip = clip.resize(height=1920)
        if clip.w < 1080: clip = clip.resize(width=1080)
        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=1080, height=1920)
        
        # Alternating Zoom: Evens zoom IN, Odds zoom OUT to prevent visual fatigue
        if index % 2 == 0:
            zoom_func = lambda t: 1 + 0.05 * (t / duration)
        else:
            zoom_func = lambda t: 1.05 - 0.05 * (t / duration)
            
        clip = clip.resize(zoom_func)
        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=1080, height=1920)
        return clip
    except Exception as e:
        print(f"⚠️ MoviePy Clip Generation Error: {e}")
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
                ).set_start(word.start).set_end(word.end).set_position(('center', video_clip.h * 0.70))
                
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
    global_img_index = 0 # Keeps track for the alternating Ken Burns effect

    for i, line in enumerate(script["lines"]):
        try:
            acting_input = line.get("acting_text", line.get("text"))
            style_instruction = line.get("style_instruction", "Serious and highly suspenseful.")
            clean_text = line.get("clean_text", line.get("text", ""))
            
            # Extract the array of visuals generated by the AI Director
            visuals_list = line.get("visuals", ["AI_GEN: dark cinematic eerie background"])

            wav_file = voice_engine.generate_acting_line(
                acting_text=acting_input, 
                clean_text=clean_text, 
                style_instruction=style_instruction,
                index=i, 
                voice_name=target_voice
            )

            if not wav_file:
                continue

            audio_clip = AudioFileClip(wav_file)
            audio_clip = add_sfx(audio_clip, clean_text)

            # --- THE DYNAMIC VISUAL SLICER ---
            line_visual_clips = []
            
            # Divide the duration of the audio clip by the number of generated visuals
            duration_per_image = audio_clip.duration / max(1, len(visuals_list))
            
            for vis_keyword in visuals_list:
                img_clip = get_image_clip(vis_keyword, duration_per_image, global_img_index)
                
                # Sequence the sub-clips within this single audio line
                if len(line_visual_clips) > 0:
                    img_clip = img_clip.set_start(line_visual_clips[-1].end)
                else:
                    img_clip = img_clip.set_start(0)
                    
                line_visual_clips.append(img_clip)
                global_img_index += 1

            # Combine all sliced visuals into one video clip that matches the exact length of the audio line
            line_video = CompositeVideoClip(line_visual_clips).set_duration(audio_clip.duration)
            
            # Apply your true crime color grading and attach the audio
            line_video = line_video.fx(colorx, 0.85).set_audio(audio_clip)

            # Sequence the master timeline
            if len(final_clips) > 0:
                line_video = line_video.set_start(final_clips[-1].end)
            
            final_clips.append(line_video)

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
            
        for f in glob.glob("temp_img_*.jpg"):
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
