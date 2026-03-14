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
        """Applies true crime pitch-shifting, EQ, and heavy compression."""
        
        # 1. Pitch Drop & Pacing: Slow the audio down by 8%. 
        # This makes the voice sound deeper, older, and more deliberate/suspenseful.
        new_rate = int(sound.frame_rate * 0.92)
        sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_rate})
        sound = sound.set_frame_rate(self.sample_rate)

        # 2. Dark EQ: Cut off high frequencies to remove "digital hiss" and keep it bass-heavy
        sound = sound.low_pass_filter(6000) 
        
        # 3. Aggressive Compression: Simulates the narrator being right up against the microphone
        sound = compress_dynamic_range(sound, threshold=-16.0, ratio=6.0, attack=2.0, release=100.0)
        
        # 4. Maximize Volume
        sound = normalize(sound, headroom=0.1)
        
        # 5. Snappy pacing: Trim dead air faster so the cuts feel more urgent
        sound = sound.strip_silence(silence_len=100, silence_thresh=-45, padding=40)

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
