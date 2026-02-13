import os
import random
import time
import json
import requests
import re
import numpy as np
import PIL.Image
import soundfile as sf
from datetime import datetime

# --- OFFICIAL GOOGLE AI SDK ---
import google.generativeai as genai
# ------------------------------

# --- AUDIO & VIDEO LIBRARIES ---
from moviepy.editor import *
from moviepy.video.fx.all import resize, crop
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from kokoro_onnx import Kokoro
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

# --- CONFIGURATION ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN_VAL = os.environ["YOUTUBE_TOKEN_JSON"]

# --- CRITICAL: BYPASS NUMPY SECURITY FOR KOKORO ---
_old_np_load = np.load
def _new_np_load(*args, **kwargs):
    kwargs['allow_pickle'] = True
    return _old_np_load(*args, **kwargs)
np.load = _new_np_load

# --- FIX FOR PILLOW ERROR ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

SFX_MAP = {
    "knock": "knock.mp3", "bang": "knock.mp3",
    "scream": "scream.mp3", "yell": "scream.mp3",
    "step": "footsteps.mp3", "run": "footsteps.mp3",
    "static": "static.mp3", "glitch": "static.mp3",
    "breath": "whisper.mp3", "whisper": "whisper.mp3"
}

# ==========================================
# 🧠 PART 1: THE NEURAL VOICE ENGINE
# ==========================================
class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing Neural Voice Engine...")
        self.kokoro = self._setup_kokoro()

    def _setup_kokoro(self):
        model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
        voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin"
        model_filename = "kokoro-v0_19.onnx"
        voices_filename = "voices.bin"

        if os.path.exists(model_filename) and os.path.getsize(model_filename) < 50*1024*1024:
            os.remove(model_filename)
            
        if not os.path.exists(model_filename):
            print("   -> Downloading Neural Weights...")
            r = requests.get(model_url, stream=True)
            with open(model_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

        if not os.path.exists(voices_filename):
            print("   -> Downloading Voice Vectors...")
            r = requests.get(voices_url, stream=True)
            with open(voices_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

        return Kokoro(model_filename, voices_filename)

    def _get_chimera_voice(self):
        try:
            voices = self.kokoro.get_voices()
            v1 = voices["bm_lewis"]
            v2 = voices["af_bella"]
            return (v1 * 0.70) + (v2 * 0.30)
        except: return "bm_lewis"

    def generate_acting_line(self, text, index, mood="neutral"):
        filename = f"temp_voice_{index}.wav"
        chimera_voice = self._get_chimera_voice()
        
        raw_chunks = re.split(r'([!?.,])', text)
        chunks = []
        curr = ""
        for p in raw_chunks:
            curr += p
            if p in "!?,.":
                chunks.append(curr.strip())
                curr = ""
        if curr: chunks.append(curr.strip())

        audio_segments = []
        for chunk in chunks:
            if not chunk: continue
            speed = 0.95
            if "!" in chunk: speed = 1.15
            elif "..." in chunk: speed = 0.8
            elif "?" in chunk: speed = 1.05
            
            if mood == "panic": speed *= 1.1
            if mood == "dread": speed *= 0.85

            temp_file = f"temp_chunk_{random.randint(0,99999)}.wav"
            audio, sr = self.kokoro.create(chunk, voice=chimera_voice, speed=speed, lang="en-gb")
            sf.write(temp_file, audio, sr)
            
            seg = AudioSegment.from_file(temp_file)
            audio_segments.append(seg)
            
            pause_ms = 150
            if "..." in chunk: pause_ms = 450
            elif "." in chunk: pause_ms = 300
            elif "!" in chunk: pause_ms = 100
            audio_segments.append(AudioSegment.silent(duration=pause_ms))
            try: os.remove(temp_file)
            except: pass

        if not audio_segments: return None
        final_audio = sum(audio_segments)
        final_audio = final_audio.high_pass_filter(80)
        final_audio = compress_dynamic_range(final_audio, threshold=-20.0, ratio=4.0)
        final_audio = normalize(final_audio, headroom=1.0)
        final_audio.export(filename, format="wav")
        return filename

# ==========================================
# 🎨 PART 2: THE VISUAL ENGINE
# ==========================================

def zoom_in_effect(clip, zoom_ratio=0.04):
    def effect(get_frame, t):
        img = PIL.Image.fromarray(get_frame(t))
        base_size = img.size
        new_size = [
            int(base_size[0] * (1 + (zoom_ratio * t))),
            int(base_size[1] * (1 + (zoom_ratio * t)))
        ]
        img = img.resize(new_size, PIL.Image.LANCZOS)
        x = (new_size[0] - base_size[0]) // 2
        y = (new_size[1] - base_size[1]) // 2
        img = img.crop([x, y, x + base_size[0], y + base_size[1]])
        return np.array(img)
    return clip.fl(effect)

def generate_ai_image(prompt, filename):
    print(f"🎨 Generating AI Image for: '{prompt}'...")
    try:
        model = genai.ImageGenerationModel("imagen-3.0-generate-001")
        result = model.generate_images(
            prompt=f"Cinematic horror photography, hyper-realistic, 8k, dark atmosphere: {prompt}",
            number_of_images=1,
        )
        result[0].save(filename)
        return True
    except Exception as e:
        print(f"   ⚠️ AI Image Gen Failed: {e}")
        return False

def get_visual_clip(keyword, filename, duration):
    clean_keyword = " ".join(keyword.split()[:4])
    print(f"🎥 Finding Visual: '{clean_keyword}'")
    
    headers = {"Authorization": PEXELS_KEY}
    url = "https://api.pexels.com/videos/search"
    params = {"query": f"{clean_keyword} horror cinematic", "per_page": 3, "orientation": "portrait"}
    
    video_found = False
    try:
        r = requests.get(url, headers=headers, params=params)
        data = r.json()
        if data.get('videos'):
            best = data['videos'][0]
            for v in data['videos']:
                if v['width'] * v['height'] > best['width'] * best['height']: best = v
            
            link = best['video_files'][0]['link']
            with open(filename, "wb") as f:
                f.write(requests.get(link).content)
            video_found = True
    except: pass
    
    if video_found:
        clip = VideoFileClip(filename)
        if clip.duration < duration:
            clip = clip.loop(duration=duration)
        return clip.subclip(0, duration)

    print("   ⚠️ No Pexels video found. Engaging AI Generator...")
    img_filename = filename.replace(".mp4", ".png")
    
    if generate_ai_image(keyword, img_filename):
        clip = ImageClip(img_filename).set_duration(duration)
        clip = zoom_in_effect(clip, zoom_ratio=0.04)
        return clip
    
    print("   ❌ AI Generation Failed. Using Black Screen.")
    return ColorClip(size=(1080, 1920), color=(0,0,0), duration=duration)

# ==========================================
# 🎬 PART 3: THE PATIENT DIRECTOR
# ==========================================

def anti_ban_sleep():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        sleep_sec = random.randint(30, 90)
        print(f"🕵️ Anti-Ban: Napping for {sleep_sec}s...")
        time.sleep(sleep_sec)

def get_real_models():
    """Asks Google for the ACTUAL list of models available to you."""
    genai.configure(api_key=GEMINI_KEY)
    valid = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid.append(m.name)
    except: return []
    # Sort: Flash -> Pro -> others
    valid.sort(key=lambda x: 'flash' not in x)
    return valid

def generate_viral_script():
    print("🧠 Director: Writing Script (Patient Mode)...")
    
    # 1. Get Real Models
    models_to_try = get_real_models()
    if not models_to_try:
        # Fallback if list fails
        models_to_try = ["models/gemini-2.0-flash", "models/gemini-1.5-flash"]
    
    print(f"   -> Available Models: {models_to_try}")

    niches = [
        "The 'Fake' Human (Uncanny Valley)", "Deep Sea Thalassophobia", 
        "The Backrooms Level 0", "Rules for Night Shift Security", 
        "Glitch in the Matrix", "The Hum (Sound)"
    ]
    niche = random.choice(niches)

    prompt = f"""
    Write a cinematic, TERRIFYING YouTube Short story about: {niche}.
    ### RULES:
    1. NO LISTS. Write a continuous 3-sentence story.
    2. VISUAL KEYWORDS: Short (2-4 words).
    
    ### JSON FORMAT:
    {{
        "title": "SCARY CLICKBAIT TITLE #shorts",
        "description": "Viral description.",
        "tags": ["horror", "shorts"],
        "lines": [
            {{ "text": "Sentence 1.", "visual_keyword": "dark hallway", "mood": "dread" }},
            {{ "text": "Sentence 2.", "visual_keyword": "shadow monster", "mood": "panic" }}
        ]
    }}
    """
    
    safety = [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
    
    # 2. Try Models with PATIENCE
    for model_name in models_to_try:
        retries = 3
        while retries > 0:
            try:
                print(f"   Attempting generation with {model_name}...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, safety_settings=safety)
                
                clean_text = response.text.strip().replace("```json", "").replace("```", "")
                return json.loads(clean_text)
                
            except Exception as e:
                err_str = str(e)
                if "429" in err_str:
                    # EXTRACT WAIT TIME or Default to 40s
                    print(f"   ⚠️ Quota exceeded (429).")
                    print("   ⏳ Waiting 40 seconds to cool down...")
                    time.sleep(40) 
                    retries -= 1
                elif "404" in err_str:
                    print(f"   ⚠️ Model {model_name} not found. Skipping.")
                    break # Don't retry a 404
                else:
                    print(f"   ⚠️ Error: {e}")
                    break
                
    print("❌ All models exhausted. Script generation failed.")
    return None

def add_sfx(audio_clip, text):
    text_lower = text.lower()
    sfx_path = None
    for k, v in SFX_MAP.items():
        if k in text_lower:
            path = os.path.join("sfx", v)
            if os.path.exists(path): sfx_path = path; break
    
    if not sfx_path and random.random() < 0.25:
        path = os.path.join("sfx", "static.mp3")
        if os.path.exists(path): sfx_path = path
            
    if sfx_path:
        try:
            sfx = AudioFileClip(sfx_path).volumex(0.35)
            if sfx.duration > audio_clip.duration:
                sfx = sfx.subclip(0, audio_clip.duration)
            return CompositeAudioClip([audio_clip, sfx])
        except: pass
    return audio_clip

def main_pipeline():
    anti_ban_sleep()
    
    try: voice_engine = VoiceEngine()
    except Exception as e: 
        print(f"❌ Engine Start Error: {e}"); return None, None
    
    script = generate_viral_script()
    if not script: return None, None
    
    print(f"🎬 Title: {script['title']}")
    final_clips = []
    
    for i, line in enumerate(script["lines"]):
        try:
            wav_file = voice_engine.generate_acting_line(line["text"], i, line.get("mood", "neutral"))
            if not wav_file: continue
            
            audio_clip = AudioFileClip(wav_file)
            audio_clip = add_sfx(audio_clip, line["text"])
            
            video_file = f"temp_vid_{i}.mp4"
            
            clip = get_visual_clip(line["visual_keyword"], video_file, audio_clip.duration)
            
            if clip.w > 1080:
                clip = clip.crop(x1=clip.w/2 - 540, width=1080, height=1920)
            elif clip.h < 1920:
                clip = clip.resize(height=1920)
                
            clip = clip.set_audio(audio_clip).fadein(0.2).fadeout(0.2)
            final_clips.append(clip)
        except Exception as e: print(f"⚠️ Clip Error: {e}")
        
    if not final_clips: 
        print("❌ No final clips assembled."); return None, None

    print("✂️ Rendering Final Master...")
    final = concatenate_videoclips(final_clips, method="compose")
    out_file = "final_video.mp4"
    final.write_videofile(out_file, codec="libx264", audio_codec="aac", fps=24, preset="fast")
    return out_file, script

def upload_to_youtube(file_path, metadata):
    if not file_path: return
    print("🚀 Uploading...")
    try:
        creds = Credentials.from_authorized_user_info(json.loads(YOUTUBE_TOKEN_VAL))
        youtube = build('youtube', 'v3', credentials=creds)
        youtube.videos().insert(
            part="snippet,status",
            body={ 
                "snippet": { "title": metadata['title'], "description": metadata['description'], "tags": metadata['tags'], "categoryId": "24" },
                "status": { "privacyStatus": "public", "selfDeclaredMadeForKids": False }
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        ).execute()
        print("✅ Success!")
    except Exception as e: print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    v, m = main_pipeline()
    if v and m: upload_to_youtube(v, m)
