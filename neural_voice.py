import os
import random
import torch
import soundfile as sf
import numpy as np
from transformers import AutoProcessor, BarkModel
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing Bark AI (Cinematic Emotional Engine)...")
        self.device = "cpu"
        self.sample_rate = 24000
        self.model, self.processor = self._setup_bark()

    def _setup_bark(self):
        print("   -> Loading Bark Small (Optimized for CPU Stability)...")
        processor = AutoProcessor.from_pretrained("suno/bark-small")
        model = BarkModel.from_pretrained("suno/bark-small").to(self.device)
        return model, processor

    def _get_voice_preset(self, role):
        presets = {
            "narrator": "v2/en_speaker_6",
            "victim": "v2/en_speaker_9",
            "demon": "v2/en_speaker_2"
        }
        return presets.get(role, "v2/en_speaker_6")

    def _inject_emotion(self, text, role):
        text = text.replace("...", " ... ")

        # Hook amplification
        if random.random() < 0.3:
            text = f"... {text}"

        if role == "victim":
            if "[gasps]" not in text and random.random() < 0.6:
                text = f"[gasps] {text}"
            text = text.replace("!", "! [gasps] ")

        elif role == "demon":
            text = f"... {text} ..."

        return text

    def generate_acting_line(self, text, index, role="narrator"):
        filename = f"temp_voice_{index}.wav"

        processed_text = self._inject_emotion(text, role)
        voice_preset = self._get_voice_preset(role)

        print(f"🎙️ Generating: '{processed_text}' ({role})")

        try:
            inputs = self.processor(
                text=[processed_text],
                return_tensors="pt",
                voice_preset=voice_preset
            ).to(self.device)

            audio_array = self.model.generate(
                **inputs,
                coarse_temperature=0.7,
                fine_temperature=0.8,
                max_new_tokens=300,
                do_sample=True,
                pad_token_id=self.processor.tokenizer.pad_token_id
            )

            audio_array = audio_array.cpu().numpy().squeeze()

            temp_raw = "temp_raw.wav"
            sf.write(temp_raw, audio_array, self.sample_rate)

            sound = AudioSegment.from_file(temp_raw)

            if role == "demon":
                new_sample_rate = int(sound.frame_rate * 0.75)
                sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
                sound = sound.set_frame_rate(24000)

            sound = sound.low_pass_filter(4000)
            sound = compress_dynamic_range(sound, threshold=-22.0, ratio=4.5)
            sound = normalize(sound, headroom=0.8)

            sound.export(filename, format="wav")

            if os.path.exists(temp_raw):
                os.remove(temp_raw)

            return filename

        except Exception as e:
            print(f"⚠️ Voice Generation Failed: {e}")
            return None
