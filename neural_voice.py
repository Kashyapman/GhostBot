import os
import wave
import time
from google import genai
from google.genai import types
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing Gemini TTS Voice Engine...")
        
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
            
        self.client = genai.Client(api_key=self.api_key)

    def _podcast_mastering(self, sound):
        """Applies true crime EQ and cinematic pacing to the Gemini audio."""
        sound = sound.low_pass_filter(8000) 
        sound = compress_dynamic_range(sound, threshold=-15.0, ratio=5.0, attack=5.0, release=50.0)
        sound = normalize(sound, headroom=0.1)
        
        # Add a 300ms cinematic pause buffer so the scenes don't rush into each other
        silence = AudioSegment.silent(duration=300)
        sound = sound + silence
        
        return sound

    def generate_acting_line(self, acting_text, index, voice_name="Charon"):
        filename = f"temp_voice_{index}.wav"
        print(f"🎙️ Gemini Casting '{voice_name}': '{acting_text}'")

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

        prompt = f"Read the following line verbatim. Apply the emotions and stage directions indicated in brackets. Use the ellipses for dramatic pauses. Do not add any conversational filler. Just perform the line:\n\n{acting_text}"

        # Automatic Rate Limit Shield: Will retry up to 3 times if Quota is exhausted
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash-preview-tts", # Correct audio endpoint
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
                    print(f"⚠️ No audio data returned for line {index}")
                    return None

                temp_raw = f"temp_raw_{index}.wav"
                
                # Gemini returns RAW PCM data. We must construct the WAV headers manually.
                with wave.open(temp_raw, "wb") as wf:
                    wf.setnchannels(1) # Mono
                    wf.setsampwidth(2) # 16-bit
                    wf.setframerate(24000) # 24kHz
                    wf.writeframes(audio_bytes)

                sound = AudioSegment.from_file(temp_raw)
                sound = self._podcast_mastering(sound)
                sound.export(filename, format="wav")

                if os.path.exists(temp_raw):
                    os.remove(temp_raw)

                return filename

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    print(f"⏳ Rate limit hit (429). Sleeping 35 seconds to reset quota... (Attempt {attempt+1}/3)")
                    time.sleep(35)
                else:
                    print(f"⚠️ Gemini Audio Generation Failed: {e}")
                    return None
                    
        print(f"❌ Failed to generate audio for line {index} after 3 attempts.")
        return None
