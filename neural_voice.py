import os
import time
import wave
import requests
from google import genai
from google.genai import types
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

# ============================================================
# SILENCE MAP — Trailing silence duration per emotional style
# ============================================================
SILENCE_MAP = {
    "whisper":        900,
    "hushed":         850,
    "terrified":      700,
    "haunting":       1100,
    "chilling":       1000,
    "shocked":        550,
    "dramatic":       650,
    "cold":           200,
    "official":       160,
    "flat":           150,
    "document":       180,
    "fast":           100,
    "rapid":          80,
    "matter-of-fact": 150,
    "default":        300,
}

# ============================================================
# VOICE MAPS (Dual Engine Support)
# ============================================================
ELEVENLABS_VOICES = {
    "narrator": "VJwFZoxTZo5aI0IowiXA",  # David - Deep, Warm, and Steady
    "witness":  "iVwieylcLv7bwfinSNdw",  # Louise - Clear, calm, thoughtful
    "document": "ddiq1IkwhtAlQgobNKtj",  # John - Flat, Even and Consistent
    "reporter": "H538pP1BbhodCGiYVMKD",  # Harry - Articulate British Storyteller
}

GEMINI_VOICES = {
    "narrator": "Charon",    
    "witness":  "Kore",      
    "document": "Fenrir",    
    "reporter": "Puck",      
}

VOICE_MAP = GEMINI_VOICES

# Ensures LLM character choices map cleanly to our role system
LEGACY_VOICE_MAP = {
    "Charon": "narrator",
    "Kore":   "witness",
    "Fenrir": "document",
    "Puck":   "reporter"
}

def get_style_silence(style_instruction: str) -> int:
    style_lower = style_instruction.lower()
    for key, duration in SILENCE_MAP.items():
        if key in style_lower:
            return duration
    return SILENCE_MAP["default"]


class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing Titanium Voice Engine (ElevenLabs Rotation + Gemini Failover) v5.0...")

        # 1. Load ElevenLabs API Keys for Rotation
        self.eleven_keys = []
        key1 = os.environ.get("ELEVEN_API_KEY_1")
        key2 = os.environ.get("ELEVEN_API_KEY_2")
        if key1: self.eleven_keys.append(key1)
        if key2: self.eleven_keys.append(key2)

        if not self.eleven_keys:
            print("⚠️ No ElevenLabs keys found in environment. Will default entirely to Gemini TTS.")

        # 2. Load Gemini API Key for Fallback
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing. Required for failover.")

        self.gemini_client = genai.Client(api_key=self.gemini_key)

    # ----------------------------------------------------------
    # PROFESSIONAL 5-STAGE MASTERING CHAIN
    # ----------------------------------------------------------
    def _podcast_mastering(self, sound: AudioSegment, style_instruction: str = "default", clean_text: str | None = None) -> AudioSegment:
        sound = sound.high_pass_filter(80)
        sound = sound.low_pass_filter(12000)
        sound = compress_dynamic_range(sound, threshold=-14.0, ratio=4.5, attack=4.0, release=40.0)
        sound = normalize(sound, headroom=0.2)

        silence_ms = get_style_silence(style_instruction)
        if clean_text:
            tail = clean_text.strip()
            if tail.endswith("..."): silence_ms += 160
            elif tail.endswith("?"): silence_ms += 110
            elif tail.endswith("!"): silence_ms += 70
            elif "—" in tail or "-" in tail: silence_ms += 40

            if len(tail.split()) <= 6:
                silence_ms = max(80, silence_ms - 40)

        return sound + AudioSegment.silent(duration=silence_ms)

    # ----------------------------------------------------------
    # PRIMARY ENGINE: ELEVENLABS NATIVE ROTATION
    # ----------------------------------------------------------
    def _generate_via_elevenlabs(self, clean_text: str, role: str, index: int) -> str | None:
        if not self.eleven_keys:
            return None

        eleven_id = ELEVENLABS_VOICES.get(role, ELEVENLABS_VOICES["narrator"])
        temp_raw = f"temp_raw_eleven_{index}.mp3"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_id}"

        payload = {
            "text": clean_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        # Iterate through available keys until one works
        for i, api_key in enumerate(self.eleven_keys):
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=30)

                if response.status_code == 200:
                    with open(temp_raw, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk: f.write(chunk)
                    print(f"   ↳ ✅ ElevenLabs Rendered (Used Key {i+1})")
                    return temp_raw
                else:
                    err_msg = response.text.lower()
                    # Catch quota limits or unauthorized keys and rotate to the next one
                    if "quota" in err_msg or "insufficient" in err_msg or response.status_code == 401:
                        print(f"   ↳ ⚠️ Key {i+1} exhausted or unauthorized. Rotating...")
                        continue
                    else:
                        print(f"   ↳ ⚠️ ElevenLabs API Error on Key {i+1}: {response.status_code} - {response.text}")
                        continue
            except Exception as e:
                print(f"   ↳ ⚠️ Connection Error on Key {i+1}: {e}")
                continue

        # If loop finishes without returning, all keys are dead
        return None

    # ----------------------------------------------------------
    # SECONDARY ENGINE: GEMINI FALLBACK
    # ----------------------------------------------------------
    def _generate_via_gemini(self, acting_text: str, clean_text: str, style_instruction: str, index: int, role: str) -> str | None:
        voice_name = GEMINI_VOICES.get(role, "Charon")
        temp_raw = f"temp_raw_gemini_{index}.wav"
        print(f"   ↳ 🔄 Failover to Gemini [{voice_name}]")

        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name))
            )
        )

        prompt = f'''You are a voice actor recording for a gritty True Crime documentary. 
YOUR VOCAL STYLE FOR THIS LINE: "{style_instruction}"
Execute SSML tags as stage directions. DO NOT speak the tags.
SCRIPT: {acting_text}'''

        for attempt in range(3):
            try:
                response = self.gemini_client.models.generate_content(
                    model="gemini-2.5-flash-preview-tts", contents=prompt, config=config
                )

                audio_bytes = None
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data:
                            audio_bytes = part.inline_data.data
                            break

                if audio_bytes:
                    with wave.open(temp_raw, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(audio_bytes)
                    return temp_raw
                    
            except Exception as e:
                if "429" in str(e) or "503" in str(e):
                    time.sleep(15 + (attempt * 10))
                else:
                    print(f"   ↳ ⚠️ Gemini TTS Error: {e}")
                    break
        return None

    # ----------------------------------------------------------
    # MASTER ROUTER
    # ----------------------------------------------------------
    def generate_acting_line(self, acting_text: str, clean_text: str, style_instruction: str, index: int, voice_name: str = "Charon") -> str | None:
        role = LEGACY_VOICE_MAP.get(voice_name, "narrator")
        text_payload = clean_text.strip()
        
        if not text_payload:
            return None

        final_filename = f"temp_voice_{index}.wav"
        print(f"🎙️ Line {index} | Style: {style_instruction[:40]}...")

        # Step 1: Try Native ElevenLabs API with Key Rotation
        temp_raw = self._generate_via_elevenlabs(text_payload, role, index)

        # Step 2: Seamless Failover to Gemini TTS if ElevenLabs fails/exhausts
        if not temp_raw or not os.path.exists(temp_raw):
            temp_raw = self._generate_via_gemini(acting_text, clean_text, style_instruction, index, role)

        # Step 3: Master the resulting audio
        if temp_raw and os.path.exists(temp_raw):
            try:
                # Pydub automatically detects if the source is mp3 (ElevenLabs) or wav (Gemini)
                sound = AudioSegment.from_file(temp_raw)
                sound = self._podcast_mastering(sound, style_instruction, clean_text=text_payload)
                sound.export(final_filename, format="wav")
                os.remove(temp_raw)
                return final_filename
            except Exception as e:
                print(f"⚠️ Audio mastering failed on line {index}: {e}")
                
        return None
