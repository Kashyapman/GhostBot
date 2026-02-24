import os
import torch
import soundfile as sf
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize
from qwen_tts import Qwen3TTSModel

class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing Qwen3-TTS CustomVoice Engine...")
        self.device = "cpu"
        self.sample_rate = 24000
        
        # Load the CustomVoice variant to enable the .generate_custom_voice() method
        self.model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            device_map=self.device,
            dtype=torch.float32
        )

    def _apply_model_morphing(self, sound, requested_model):
        """Morphs the base voice to match the AI's requested model style"""
        requested_model = requested_model.lower()
        
        if "female" in requested_model or "high" in requested_model:
            new_rate = int(sound.frame_rate * 1.2)
            sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_rate})
            
        elif "deep" in requested_model or "cinematic" in requested_model:
            new_rate = int(sound.frame_rate * 0.85)
            sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_rate})
            
        elif "distorted" in requested_model or "monster" in requested_model or "entity" in requested_model:
            new_rate = int(sound.frame_rate * 0.70)
            sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_rate})

        return sound.set_frame_rate(self.sample_rate)

    def generate_acting_line(self, text, index, requested_model="Qwen-Standard", emotion="neutral"):
        filename = f"temp_voice_{index}.wav"
        
        print(f"🎙️ Generating: '{text}' | Emotion: {emotion} | Profile: {requested_model}")

        try:
            # Use the correct API method and pass the AI's emotion into the 'instruct' parameter
            wavs, sr = self.model.generate_custom_voice(
                text=text,
                language="English",
                speaker="Ryan", # Default built-in dynamic English male speaker
                instruct=f"Speak in a {emotion} tone. Style: {requested_model}"
            )

            temp_raw = "temp_raw.wav"
            sf.write(temp_raw, wavs[0], sr)

            sound = AudioSegment.from_file(temp_raw)

            # Apply additional programmatic voice morphing (Pitch shifting)
            sound = self._apply_model_morphing(sound, requested_model)

            # Post-Production Audio Mastering
            sound = sound.low_pass_filter(6000)
            sound = compress_dynamic_range(sound, threshold=-22.0, ratio=4.5)
            sound = normalize(sound, headroom=0.8)

            sound.export(filename, format="wav")

            if os.path.exists(temp_raw):
                os.remove(temp_raw)

            return filename

        except Exception as e:
            print(f"⚠️ Voice Generation Failed: {e}")
            return None
