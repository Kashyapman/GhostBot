import os
import wave
import time
from google import genai
from google.genai import types
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing Gemini Master-Director Engine...")
        
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
            
        self.client = genai.Client(api_key=self.api_key)

    def _podcast_mastering(self, sound):
        """Applies true crime EQ. Pacing is controlled strictly by SSML."""
        sound = sound.low_pass_filter(8000) 
        sound = compress_dynamic_range(sound, threshold=-15.0, ratio=5.0, attack=5.0, release=50.0)
        sound = normalize(sound, headroom=0.1)
        
        # Add a 300ms cinematic pause buffer so the scenes don't rush into each other
        silence = AudioSegment.silent(duration=300)
        sound = sound + silence
        
        return sound

    def generate_acting_line(self, acting_text, clean_text, style_instruction, index, voice_name="Charon"):
        filename = f"temp_voice_{index}.wav"
        print(f"🎙️ Gemini Rendering [{voice_name}] | Style: {style_instruction}")

        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            )
        )

        # STRICT PROMPT: Forces Gemini to obey the SSML tags instead of speaking them
        prompt = f"""You are an elite, award-winning voice actor narrating a gritty True Crime documentary. 
YOUR VOCAL STYLE/EMOTION FOR THIS LINE: "{style_instruction}"

CRITICAL ACTING DIRECTION: 
The script below uses SSML tags (like <break>, <emphasis>, <prosody>). 
DO NOT speak the tags out loud. Instead, you MUST execute them perfectly as stage directions:
- When you see <break time="Xs"/>, pause in complete silence for that exact duration.
- When you see <emphasis level="strong">, hit that word hard with intense emotion.
- When you see <prosody rate="slow" pitch="low">, slow down and drop your pitch to build suspense.

Bring this terrifying script to life:

{acting_text}"""

        models_to_try = ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro"]

        for model_name in models_to_try:
            for attempt in range(3):
                try:
                    response = self.client.models.generate_content(
                        model=model_name, contents=prompt, config=config
                    )

                    audio_bytes = None
                    if response.candidates and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if part.inline_data:
                                audio_bytes = part.inline_data.data
                                break

                    if not audio_bytes: continue 

                    temp_raw = f"temp_raw_{index}.wav"
                    with wave.open(temp_raw, "wb") as wf:
                        wf.setnchannels(1) 
                        wf.setsampwidth(2) 
                        wf.setframerate(24000) 
                        wf.writeframes(audio_bytes)

                    sound = AudioSegment.from_file(temp_raw)
                    sound = self._podcast_mastering(sound)
                    sound.export(filename, format="wav")
                    
                    if os.path.exists(temp_raw): 
                        os.remove(temp_raw)

                    return filename

                except Exception as e:
                    if "429" in str(e) or "503" in str(e): 
                        time.sleep(35 + (attempt * 10))
                    else: 
                        break 
        return None
