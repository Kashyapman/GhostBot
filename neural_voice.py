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
        print("🎚️ Initializing Bark AI (Emotional Engine)...")
        # Force CPU for GitHub Actions (Prevents CUDA errors)
        self.device = "cpu" 
        self.sample_rate = 24000
        self.model, self.processor = self._setup_bark()

    def _setup_bark(self):
        """Loads the Bark Small model (CPU safe)."""
        print("   -> Loading Transformer Weights (This may take 2-3 mins)...")
        
        # We use 'suno/bark-small' to fit within GitHub Actions 7GB RAM limit
        processor = AutoProcessor.from_pretrained("suno/bark-small")
        model = BarkModel.from_pretrained("suno/bark-small").to(self.device)
        
        # Removed enable_cpu_offload() to prevent 'accelerate' crash on CPU runners
        return model, processor

    def _get_voice_preset(self, role):
        """Maps roles to specific Bark Speaker IDs."""
        if role == "narrator":
            return "v2/en_speaker_6" # Deep, reliable male
        elif role == "victim":
            return "v2/en_speaker_9" # Higher pitched, anxious female
        elif role == "demon":
            return "v2/en_speaker_6" 
        return "v2/en_speaker_6"

    def _preprocess_text(self, text, role):
        """Injects Bark-specific tokens for emotion."""
        text = text.replace("...", " ... ") # Ensure pauses are distinct
        
        if role == "victim":
            # Add breathing/fear markers if not present
            if "[gasps]" not in text and random.random() < 0.5:
                text = f"[gasps] {text}"
            if "!" in text:
                text = text.replace("!", "! [gasps] ")
                
        elif role == "narrator":
            # Slower pacing markers
            text = f"... {text} ..."
            
        return text

    def generate_acting_line(self, text, index, role="narrator"):
        """Generates audio with specific emotional direction."""
        filename = f"temp_voice_{index}.wav"
        
        # 1. Prepare Text & Voice
        processed_text = self._preprocess_text(text, role)
        voice_preset = self._get_voice_preset(role)
        
        print(f"   🎙️ Bark Generating: '{processed_text}' ({role})...")
        
        try:
            # 2. Tokenize
            inputs = self.processor(
                text=[processed_text],
                return_tensors="pt",
                voice_preset=voice_preset
            ).to(self.device)

            # 3. Generate (FIXED PARAMETERS)
            # We explicitly set max_new_tokens to 256 to override the conflicting default.
            # do_sample=True ensures we use the temperatures provided.
            audio_array = self.model.generate(
                **inputs,
                coarse_temperature=0.6,
                fine_temperature=0.7,
                max_new_tokens=256,  # Allows enough length for audio
                do_sample=True,      # Explicitly enable sampling
                pad_token_id=self.processor.tokenizer.pad_token_id # Safety for warning suppression
            )
            
            audio_array = audio_array.cpu().numpy().squeeze()
            
            # 4. Save Raw
            temp_raw = "temp_raw.wav"
            sf.write(temp_raw, audio_array, self.sample_rate)
            
            # 5. Post-Processing & Mastering
            sound = AudioSegment.from_file(temp_raw)
            
            # DEMON FX: Pitch Shift Down
            if role == "demon":
                new_sample_rate = int(sound.frame_rate * 0.8) # Slow down/Deepen
                sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
                sound = sound.set_frame_rate(24000)

            # MASTERING (Warmth & loudness)
            sound = sound.low_pass_filter(3500) # Remove digital hiss
            sound = compress_dynamic_range(sound, threshold=-20.0, ratio=4.0)
            sound = normalize(sound, headroom=1.0)
            
            sound.export(filename, format="wav")
            
            # Cleanup
            if os.path.exists(temp_raw): os.remove(temp_raw)
            return filename
            
        except Exception as e:
            print(f"   ⚠️ Bark Generation Failed: {e}")
            return None
