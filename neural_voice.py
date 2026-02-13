import os
import random
import numpy as np
import soundfile as sf
import requests
import re
from kokoro_onnx import Kokoro
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

# --- CRITICAL: BYPASS NUMPY SECURITY FOR KOKORO ---
_old_np_load = np.load
def _new_np_load(*args, **kwargs):
    kwargs['allow_pickle'] = True
    return _old_np_load(*args, **kwargs)
np.load = _new_np_load
# --------------------------------------------------

class VoiceEngine:
    def __init__(self):
        print("🎚️ Initializing Neural Voice Engine...")
        self.kokoro = self._setup_kokoro()
        self.sample_rate = 24000 # Kokoro native rate

    def _setup_kokoro(self):
        # STABLE RELEASE LINKS
        model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
        voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin"
        
        model_filename = "kokoro-v0_19.onnx"
        voices_filename = "voices.bin"

        # Auto-Repair: Delete corrupt files
        if os.path.exists(model_filename) and os.path.getsize(model_filename) < 50*1024*1024:
            os.remove(model_filename)
            
        if not os.path.exists(model_filename):
            print("   -> Downloading Neural Weights...")
            r = requests.get(model_url, stream=True)
            with open(model_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

        if not os.path.exists(voices_filename):
            print("   -> Downloading Voice Vectors...")
            r = requests.get(voices_url, stream=True)
            with open(voices_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

        return Kokoro(model_filename, voices_filename)

    def _get_chimera_voice(self):
        """
        Mixes 'bm_lewis' (Deep Male) and 'af_bella' (Breath Female)
        to create a unique, eerie storytelling voice.
        """
        try:
            voices = self.kokoro.get_voices()
            v1 = voices["bm_lewis"]
            v2 = voices["af_bella"]
            # 70% Lewis / 30% Bella = Deep but airy
            return (v1 * 0.70) + (v2 * 0.30)
        except:
            return "bm_lewis" # Fallback

    def generate_acting_line(self, text, index, mood="neutral"):
        """
        Parses text for acting cues and generates varied audio segments.
        """
        filename = f"temp_voice_{index}.wav"
        chimera_voice = self._get_chimera_voice()
        
        # 1. Parse "Acting Chunks"
        # Split by punctuation to control speed per phrase
        raw_chunks = re.split(r'([!?.,])', text)
        chunks = []
        curr = ""
        for p in raw_chunks:
            curr += p
            if p in "!?,.":
                chunks.append(curr.strip())
                curr = ""
        if curr: chunks.append(curr.strip())

        # 2. Generate Audio Segments
        audio_segments = []
        
        for chunk in chunks:
            if not chunk: continue
            
            # ACTING LOGIC: Determine Speed
            speed = 0.95 # Default storytelling
            if "!" in chunk: speed = 1.15 # Panic
            elif "..." in chunk: speed = 0.8  # Suspense
            elif "?" in chunk: speed = 1.05 # Confusion
            elif "," in chunk: speed = 0.95 # Flow
            
            # Mood Overrides
            if mood == "panic": speed *= 1.1
            if mood == "dread": speed *= 0.85

            # Generate Raw Audio
            temp_file = f"temp_chunk_{random.randint(0,99999)}.wav"
            audio, sr = self.kokoro.create(chunk, voice=chimera_voice, speed=speed, lang="en-gb")
            sf.write(temp_file, audio, sr)
            
            # Convert to Pydub
            seg = AudioSegment.from_file(temp_file)
            audio_segments.append(seg)
            
            # 3. THE BREATH (Silence/Pause Logic)
            pause_ms = 150
            if "..." in chunk: pause_ms = 450
            elif "." in chunk: pause_ms = 300
            elif "!" in chunk: pause_ms = 100
            
            audio_segments.append(AudioSegment.silent(duration=pause_ms))
            
            try: os.remove(temp_file)
            except: pass

        # 4. Stitch
        final_audio = sum(audio_segments)
        
        # 5. MASTERING
        # High Pass (Clean Mud)
        final_audio = final_audio.high_pass_filter(80)
        # Compression (YouTuber Sound)
        final_audio = compress_dynamic_range(final_audio, threshold=-20.0, ratio=4.0)
        # Normalize
        final_audio = normalize(final_audio, headroom=1.0)
        
        final_audio.export(filename, format="wav")
        return filename
