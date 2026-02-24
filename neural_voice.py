import os
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel #
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing Qwen3-TTS (Autobot)...")
        self.device = "cpu"
        
        # Using the 0.6B model for fast, reliable CPU inference
        self.model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", 
            device_map=self.device,
            dtype=torch.float32,
            attn_implementation="sdpa" #
        )

    def _get_voice_profile(self, role):
        # Qwen3-TTS supports explicit emotional instructions
        profiles = {
            "narrator": ("Ryan", "Speak in a creepy, suspenseful, and low-pitched storytelling voice."),
            "victim": ("Vivian", "Speak with extreme fear, panic, and a trembling voice."),
            "demon": ("Aiden", "Speak in a terrifying, deep, distorted, and slow demonic voice.")
        }
        return profiles.get(role, ("Ryan", "Speak in a suspenseful tone."))

    def generate_acting_line(self, text, index, role="narrator"):
        filename = f"temp_voice_{index}.wav"
        speaker, instruct = self._get_voice_profile(role)

        print(f"🎙️ Generating: '{text}' (Voice: {speaker} | Emotion: {instruct})")

        try:
            # Generate audio using instructions and text
            wavs, sr = self.model.generate_custom_voice(
                language="English",
                speaker=speaker,
                instruct=instruct,
                text=text
            )

            temp_raw = "temp_raw.wav"
            sf.write(temp_raw, wavs[0], sr) #

            sound = AudioSegment.from_file(temp_raw)
            
            # Post-processing for extra demonic distortion
            if role == "demon":
                new_rate = int(sound.frame_rate * 0.85)
                sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_rate})
                sound = sound.set_frame_rate(24000)

            # Clean up and compress for loud YouTube Shorts audio
            sound = sound.low_pass_filter(5000)
            sound = compress_dynamic_range(sound, threshold=-20.0, ratio=4.0)
            sound = normalize(sound, headroom=0.5)

            sound.export(filename, format="wav")

            if os.path.exists(temp_raw):
                os.remove(temp_raw)

            return filename

        except Exception as e:
            print(f"⚠️ Voice Generation Failed: {e}")
            return None
