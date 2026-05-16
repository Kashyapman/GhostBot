import os
import wave
import time
from google import genai
from google.genai import types
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

# ============================================================
# SILENCE MAP — Trailing silence duration per emotional style
# Controls pacing between lines far more precisely than a flat 300ms
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
# VOICE MAP — exported so main.py can import and use it
# Maps speaker role → Gemini TTS voice name
# ============================================================
VOICE_MAP = {
    "narrator": "Charon",    # Deep, world-weary, authoritative
    "witness":  "Kore",      # Female, personal, scared or stunned
    "document": "Fenrir",    # Flat, cold, bureaucratic (police/coroner reports)
    "reporter": "Puck",      # Neutral, journalistic
}


def get_style_silence(style_instruction: str) -> int:
    """Returns trailing silence (ms) matched to the emotional style of the line."""
    style_lower = style_instruction.lower()
    for key, duration in SILENCE_MAP.items():
        if key in style_lower:
            return duration
    return SILENCE_MAP["default"]


class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing Gemini Master-Director Engine v2.0...")

        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")

        self.client = genai.Client(api_key=self.api_key)

    # ----------------------------------------------------------
    # PROFESSIONAL 5-STAGE MASTERING CHAIN
    # Upgraded from flat low-pass + compression to full EQ → dynamics → normalize
    # ----------------------------------------------------------
    def _podcast_mastering(self, sound: AudioSegment, style_instruction: str = "default") -> AudioSegment:
        """
        Stage 1 — High-Pass Filter (80Hz):
            Removes low-frequency room rumble and mic handling noise.
            Critical for clean podcast/documentary audio.

        Stage 2 — Low-Pass Filter (12 000Hz):
            Removes harsh sibilance above 12kHz.
            Keeps the voice warm without sounding muffled.

        Stage 3 — Dynamic Compression (podcast-grade settings):
            threshold=-14dBFS  (tighter than before for more consistent level)
            ratio=4.5:1        (firm but not over-squashed)
            attack=4ms         (fast enough to catch transients)
            release=40ms       (snappy — lets the voice breathe)

        Stage 4 — Normalize to -0.2dBFS:
            Maximises loudness consistently across all lines.

        Stage 5 — Dynamic trailing silence:
            Duration is driven by SILENCE_MAP so dramatic whispers
            hang longer than rapid factual lines.
        """
        # Stage 1
        sound = sound.high_pass_filter(80)

        # Stage 2
        sound = sound.low_pass_filter(12000)

        # Stage 3
        sound = compress_dynamic_range(
            sound,
            threshold=-14.0,
            ratio=4.5,
            attack=4.0,
            release=40.0
        )

        # Stage 4
        sound = normalize(sound, headroom=0.2)

        # Stage 5 — style-aware silence
        silence_ms = get_style_silence(style_instruction)
        silence = AudioSegment.silent(duration=silence_ms)
        sound = sound + silence

        return sound

    # ----------------------------------------------------------
    # CORE GENERATION METHOD
    # ----------------------------------------------------------
    def generate_acting_line(
        self,
        acting_text: str,
        clean_text: str,
        style_instruction: str,
        index: int,
        voice_name: str = "Charon"
    ) -> str | None:
        """
        Renders one script line to a mastered .wav file.

        Parameters
        ----------
        acting_text       : SSML-tagged text the model should perform
        clean_text        : Plain text used for SFX matching (not sent to TTS)
        style_instruction : Emotional/vocal direction for this line
        index             : Position index — used for unique temp filenames
        voice_name        : Gemini prebuilt voice (from VOICE_MAP)

        Returns path to the mastered .wav, or None on total failure.
        """
        filename = f"temp_voice_{index}.wav"
        print(f"🎙️ Rendering [{voice_name}] | Style: {style_instruction[:55]}")

        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            )
        )

        # DIRECTOR PROMPT — instructs the model to execute SSML as stage directions
        prompt = f"""You are an elite, award-winning voice actor recording for "COLD CASE ARCHIVE" —
a gritty True Crime documentary channel. You are a world-weary former detective who narrates 
these cases with quiet precision and contained fury.

YOUR VOCAL STYLE / EMOTION FOR THIS LINE:
"{style_instruction}"

CRITICAL ACTING DIRECTION — READ BEFORE PERFORMING:
The script uses SSML tags as stage directions. DO NOT speak the tag text aloud. Execute them:
- <break time="Xs"/>              → pause in complete silence for that exact duration
- <emphasis level="strong">       → hit that word hard — intensity, weight, not volume
- <prosody rate="slow" pitch="-15%"> → slow down and lower your pitch — maximum dread
- <prosody rate="fast">           → rapid-fire delivery — facts escalating fast

RECORDING ENVIRONMENT:
You are in a quiet, slightly reverberant late-night radio studio.
Your voice has natural room presence. You are NOT in a dead anechoic booth.
Bring gravitas. Bring humanity. The listener must feel this is a real person 
who has spent years investigating this case.

SCRIPT LINE TO PERFORM:
{acting_text}"""

        models_to_try = ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro"]

        for model_name in models_to_try:
            for attempt in range(3):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )

                    audio_bytes = None
                    if response.candidates and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if part.inline_data:
                                audio_bytes = part.inline_data.data
                                break

                    if not audio_bytes:
                        print(f"⚠️ No audio bytes returned (model={model_name}, attempt={attempt + 1})")
                        continue

                    # Write raw PCM to a temp wav
                    temp_raw = f"temp_raw_{index}.wav"
                    with wave.open(temp_raw, "wb") as wf:
                        wf.setnchannels(1)    # Mono
                        wf.setsampwidth(2)    # 16-bit
                        wf.setframerate(24000) # 24kHz — Gemini TTS native rate
                        wf.writeframes(audio_bytes)

                    # Load → master → export
                    sound = AudioSegment.from_file(temp_raw)
                    sound = self._podcast_mastering(sound, style_instruction)
                    sound.export(filename, format="wav")

                    if os.path.exists(temp_raw):
                        os.remove(temp_raw)

                    print(f"✅ Line {index} rendered ({voice_name}) — {sound.duration_seconds:.1f}s")
                    return filename

                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "503" in err_str:
                        wait = 35 + (attempt * 12)
                        print(f"⏳ Rate limit hit — waiting {wait}s (attempt {attempt + 1}/3)...")
                        time.sleep(wait)
                    else:
                        print(f"⚠️ TTS error on line {index} (attempt {attempt + 1}): {e}")
                        break  # Non-retriable error — try next model

        print(f"❌ All TTS attempts exhausted for line {index}")
        return None
