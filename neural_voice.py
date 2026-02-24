import os
import torch
import soundfile as sf
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

class VoiceEngine:
    def __init__(self):
        print("🎙 Initializing Qwen Emotional TTS...")
        self.device = "cpu"
        self.sample_rate = 24000
        self.model_id = "Qwen/Qwen2.5-TTS"
        self.processor = AutoProcessor.from_pretrained(self.model_id)
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_id,
            torch_dtype=torch.float32
        ).to(self.device)

    def generate_line(self, text, emotion, index):
        filename = f"temp_voice_{index}.wav"

        styled = f"<emotion:{emotion}> {text}"

        inputs = self.processor(
            text=styled,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            speech = self.model.generate(
                **inputs,
                do_sample=True,
                temperature=0.95,
                top_p=0.9
            )

        audio = speech.cpu().numpy().squeeze()
        sf.write(filename, audio, self.sample_rate)

        # Post mastering
        sound = AudioSegment.from_file(filename)
        sound = compress_dynamic_range(sound, threshold=-18.0, ratio=3.5)
        sound = normalize(sound, headroom=0.5)
        sound.export(filename, format="wav")

        return filename
