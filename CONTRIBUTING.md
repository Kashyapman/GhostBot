# Contributing to GhostBot 👻🤖

First off, thank you for considering contributing to GhostBot! 

GhostBot has evolved from a simple text-to-video script into a **State-of-the-Art (SOTA) Programmatic Documentary Engine**. Because we are pushing the limits of what a free GitHub Actions runner can do—running local computer vision models, 5-stage audio mastering, and 2.5D depth mapping—we need talented developers to help optimize, expand, and perfect the pipeline.

Whether you are a Prompt Engineer, a Computer Vision specialist, or a backend API wizard, there is a place for you here.

---

## 🎯 High-Priority Contribution Areas (What We Need Right Now)

We welcome all PRs, but we are actively looking for contributors to tackle these specific technical challenges:

### 1. Advanced 2.5D Parallax & Vision Engineering
Currently, our `Depth-Anything-V2-Small-hf` implementation maps depth and shifts pixels left or right (X-axis).
* **The Goal:** We want complex camera movements. Can you write an OpenCV distortion map that handles Z-axis (push-in/pull-out) or organic handheld camera shake? 
* **Optimization:** If you can make the `cv2.remap` function run faster or use less RAM on the Ubuntu runner, we want your code.

### 2. Audio-Reactive Physics
Right now, the background music and cinematic stingers (thuds, static) just play over the video.
* **The Goal:** We want the video to *react* to the audio. Using `librosa` or `pydub` amplitude data, can you write a MoviePy `make_frame` function that causes the video to physically shake, glitch, or flash white exactly when a loud sound effect plays?

### 3. Expanded Contextual Matting (Pillow)
Our current diegetic framing wraps images in Polaroids, CRT scanlines, or cinematic shadows.
* **The Goal:** We need more programmatic Pillow templates. Can you write functions that wrap the FLUX.1 images in:
  * A "Top Secret" classified manila folder?
  * Microfilm viewer UI?
  * Burnt or torn newspaper clippings?

### 4. Kinetic Subtitle Animation
Our Netflix-style Karaoke subtitles successfully highlight the active word using Pillow strokes. 
* **The Goal:** We want motion. Can you modify `make_karaoke_frame` so the active word slightly scales up (pops) or bounces when it is spoken?

### 5. The Holy Grail: TikTok & X (Twitter) API Distribution
GhostBot currently successfully navigates YouTube and Meta (Facebook/Instagram).
* **The Goal:** We need robust Python modules to handle automated uploading to TikTok and X. TikTok's API is notoriously difficult for automated bots—if you have a working, stable workaround or official API implementation, this is a massive priority.

---

## 🛠️ How to Contribute (Dev Setup)

GhostBot relies on heavy system-level audio and image processors. Please ensure your local environment is configured correctly before testing.

### 1. Fork & Clone
Fork the repository to your own GitHub account, then clone it locally:
```bash
git clone [https://github.com/YOUR-USERNAME/GhostBot.git](https://github.com/YOUR-USERNAME/GhostBot.git)
cd GhostBot
```

### 2. Install System Dependencies
GhostBot requires native decoders for `moviepy`, `pydub`, and `Pillow`.
* **Ubuntu/Debian:** `sudo apt-get install ffmpeg libsndfile1 sox imagemagick ghostscript libwebp-dev libjpeg-dev`
* **MacOS (Homebrew):** `brew install ffmpeg sox imagemagick ghostscript`
* **Windows:** You will need to install [FFmpeg](https://ffmpeg.org/download.html) and [ImageMagick](https://imagemagick.org/script/download.php) and add them to your PATH.

### 3. Set Up Your Python Environment
Create a virtual environment and install the Python libraries:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

### 4. Create a Branch
Always create a new branch for your feature or bug fix:
```bash
git checkout -b feature/parallax-z-axis
```

### 5. Test Your Code
Because GhostBot runs in an automated CI/CD environment (GitHub Actions), ensure your code does not require a GUI, does not pop up windows, and manages memory efficiently. 
* *Pro Tip:* Run `main.py` locally and verify the final `final_video.mp4` renders successfully before opening a PR.

### 6. Submit a Pull Request
* Push your branch to your fork.
* Open a Pull Request against the `main` branch of this repository.
* **CRITICAL:** If you changed the visual pipeline (`main.py` image generation, matting, or parallax), **you must attach a short video or screenshot** of the new output in your PR description so we can see your work in action!

---

## 🐛 Found a Bug or Have a Big Idea?
If you find a bug (like a Meta API token issue or a MoviePy rendering crash) or have a massive idea for a new feature but don't have the time to code it yourself, please open an Issue! Go to the "Issues" tab, click "New Issue," and provide your system logs.

Happy coding, and welcome to the GhostBot team!
