import os
import wave
import time
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Please set your GEMINI_API_KEY environment variable.")

client = genai.Client(api_key=API_KEY)

os.makedirs("voices", exist_ok=True)

# A serious, grounded reference text helps the cloning model capture a gritty, documentary-style timbre
REFERENCE_TEXT = "The evidence was scattered across the room. We documented every anomaly, but nothing could explain what happened next. The sequence of events remains completely undocumented."

# The GhostBot Roster
VOICES_TO_GENERATE = {
    "Charon": "Charon", # Gritty Male
    "Fenrir": "Fenrir", # Intense Male
    "Aoede": "Aoede",   # Haunting Female
    "Kore": "Kore"      # Unsettling Female
}

def generate_reference_audio(archetype_name, gemini_voice_name):
    print(f"🎙️ Generating GhostBot reference for: {archetype_name}...")
    
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=gemini_voice_name)
            )
        )
    )

    prompt = f"Read the following text clearly, seriously, and naturally:\n\n{REFERENCE_TEXT}"

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts", 
                contents=prompt, 
                config=config
            )

            audio_bytes = None
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        audio_bytes = part.inline_data.data
                        break

            if audio_bytes:
                filepath = f"voices/{archetype_name}.wav"
                with wave.open(filepath, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(audio_bytes)
                print(f"✅ Saved successfully to {filepath}\n")
                return 
            else:
                print(f"❌ Failed to extract audio bytes for {archetype_name}\n")
                break

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"⏳ Rate limit hit! Sleeping for 40 seconds before retrying...")
                time.sleep(40)
            else:
                print(f"❌ API Error for {archetype_name}: {e}\n")
                break

if __name__ == "__main__":
    print("🚀 Starting GhostBot Voice Cloning Generation...\n")
    for archetype, gemini_voice in VOICES_TO_GENERATE.items():
        generate_reference_audio(archetype, gemini_voice)
        time.sleep(5) 
        
    print("🎉 All base voices generated! Commit the 'voices' folder to your GhostBot repo.")
