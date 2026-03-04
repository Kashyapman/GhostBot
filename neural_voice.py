import os
import torch
import soundfile as sf
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize
from qwen_tts import Qwen3TTSModel

class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing True Crime Voice Engine...")
        self.device = "cpu"
        self.sample_rate = 24000
        
        self.model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            device_map=self.device,
            dtype=torch.float32
        )

    def _podcast_mastering(self, sound):
        """Applies professional EQ and compression to sound like a high-end podcast."""
        # 1. Very slight bass boost for that "movie trailer" authoritative depth
        sound = sound.low_pass_filter(8000) 
        
        # 2. Aggressive dynamic range compression (keeps quiet whispers and loud moments at same volume)
        sound = compress_dynamic_range(sound, threshold=-18.0, ratio=5.0, attack=5.0, release=50.0)
        
        # 3. Normalize right to the ceiling so it punches through phone speakers
        sound = normalize(sound, headroom=0.2)
        
        # 4. Strip out trailing silences at the end so the YouTube loop is instantaneous
        sound = sound.strip_silence(silence_len=150, silence_thresh=-40, padding=50)

        return sound

    def generate_acting_line(self, text, index, emotion="serious"):
        filename = f"temp_voice_{index}.wav"
        print(f"🎙️ Generating: '{text}' | Emotion: {emotion}")

        try:
            # We removed the crazy pitch shifts and rely entirely on Qwen's instruction engine
            wavs, sr = self.model.generate_custom_voice(
                text=text,
                language="English",
                speaker="Ryan", 
                instruct=f"You are a professional true crime documentary narrator. Speak in a {emotion}, investigative, and intense tone."
            )

            temp_raw = "temp_raw.wav"
            sf.write(temp_raw, wavs[0], sr)

            sound = AudioSegment.from_file(temp_raw)

            # Master the audio
            sound = self._podcast_mastering(sound)
            sound.export(filename, format="wav")

            if os.path.exists(temp_raw):
                os.remove(temp_raw)

            return filename

        except Exception as e:
            print(f"⚠️ Voice Generation Failed: {e}")
            return None
