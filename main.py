from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

# ... (Keep your imports)

def master_audio(file_path):
    print("🎚️ Mastering Audio (Bass Boost + Compression)...")
    sound = AudioSegment.from_file(file_path)
    
    # 1. Pitch Shift Down (Manual "Dark" Vibe) - Optional
    # sound = sound._spawn(sound.raw_data, overrides={'frame_rate': int(sound.frame_rate * 0.95)})
    
    # 2. Add Bass (Low Shelf Filter approximation)
    # Pydub doesn't have a direct EQ, so we overlay a low-pass filter version
    bass = sound.low_pass_filter(150)
    sound = sound.overlay(bass.apply_gain(-2)) # Blend it back in
    
    # 3. Compression (Make it punchy)
    sound = compress_dynamic_range(sound, threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
    
    # 4. Normalize (Max Volume)
    sound = normalize(sound)
    
    sound.export(file_path, format="mp3")

async def generate_dynamic_voice(script_data, filename="voice.mp3"):
    print(f"🎙️ Generating Voice with Edge-TTS...")
    clips = []
    
    for i, line in enumerate(script_data.get("lines", [])):
        text = line["text"]
        role = line.get("role", "narrator")
        
        # Christopher is the best base. We use him for everything but change settings.
        voice_id = "en-US-ChristopherNeural"
        
        if role == "victim":
            # Fast and slightly higher
            rate = "+25%" 
            pitch = "+2Hz"
        elif role == "demon":
            # The "Demon" voice needs to be SLOW to sound scary
            rate = "-20%"   
            pitch = "-15Hz" 
        else: # Narrator
            # Default Documentary Style
            rate = "-5%"
            pitch = "-2Hz"
            
        temp_file = f"temp_voice_{i}.mp3"
        communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
        await communicate.save(temp_file)
        
        if os.path.exists(temp_file):
            clip = AudioFileClip(temp_file)
            clips.append(clip)
            # Tighter pause (0.1s instead of 0.2s) for better flow
            clips.append(AudioClip(lambda t: 0, duration=0.1))

    if clips:
        final_audio = concatenate_audioclips(clips)
        final_audio.write_audiofile("raw_voice.mp3")
        
        # --- APPLY MASTERING ---
        master_audio("raw_voice.mp3")
        # -----------------------
        
        final_audio_mastered = AudioFileClip("raw_voice.mp3")
        final_audio_mastered.write_audiofile(filename)
        
        # Cleanup
        for i in range(len(script_data["lines"])):
            try: os.remove(f"temp_voice_{i}.mp3")
            except: pass
        if os.path.exists("raw_voice.mp3"): os.remove("raw_voice.mp3")
    else:
        print("❌ Audio Generation Failed")
