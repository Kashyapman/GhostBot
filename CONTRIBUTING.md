# Contributing to GhostBot 👻🤖

First off, thank you for considering contributing to GhostBot! 

GhostBot has evolved from a simple text-to-video script into a **v4.0 State-of-the-Art (SOTA) Programmatic Documentary Engine**. Because we are pushing the limits of what a free GitHub Actions runner can do—running local 3D computer vision models, dual-pass optical glow subtitles, 5-stage audio mastering, and mathematical audio ducking—we need talented developers to help optimize, expand, and perfect the pipeline.

Whether you are an LLM Prompt Engineer, a Computer Vision specialist, or a backend API wizard, there is a place for you here.

---

## 🎯 High-Priority Contribution Areas (What We Need Right Now)

We recently deployed our Titanium Engine with 3D parallax, pause-bait micro-clues, and dynamic pacing. Now, we are actively looking for contributors to tackle these next-level technical challenges:

### 1. Robust AI Video Integration (Asynchronous Queues)
We currently rely on FLUX.1 for static images because video APIs (Kling, Luma, Runway) timeout on GitHub Actions.
* **The Goal:** Can you build a resilient, asynchronous polling system that queues AI video generation, sleeps, and retrieves the MP4s without burning through the runner's maximum timeout limits?

### 2. OpenCV OCR & Document Highlighting
Our current "pause-bait" features flash redacted AI documents on screen to induce re-watches.
* **The Goal:** We want to dynamically draw animated red circles or yellow highlighters over specific words on the generated AI documents. This requires robust Optical Character Recognition (OCR) that won't crash the pipeline if the AI image text is slightly garbled.

### 3. Advanced 3D Parallax (Z-Axis & Pitch/Yaw)
Currently, our `Depth-Anything-V2-Small-hf` implementation maps depth and shifts pixels on the X-axis with Cosine S-Curve easing.
* **The Goal:** We want complex 3D camera movements. Can you write an OpenCV distortion map that handles Z-axis (push-in/pull-out) or organic handheld camera shake using the depth maps?

### 4. Audio-Reactive Physics
We recently implemented mathematical audio ducking ("tape stops") and cut-triggered micro-foley.
* **The Goal:** We want the video to *react* visually to the audio. Using amplitude data, can you write a MoviePy `make_frame` function that causes the video to physically shake, glitch, or flash white exactly when a loud cinematic stinger plays?

### 5. The Holy Grail: TikTok & X (Twitter) API Distribution
GhostBot currently successfully navigates YouTube and Meta (Facebook/Instagram via a 3-tier failsafe).
* **The Goal:** We need robust Python modules to handle automated uploading to TikTok and X. TikTok's API is notoriously difficult for automated bots—if you have a working, stable workaround or official API implementation, this is a massive priority.

---

## 🛠️ How to Contribute (Dev Setup)

GhostBot relies on heavy system-level audio and image processors. Please ensure your local environment is configured correctly before testing.

### 1. Fork & Clone
Fork the repository to your own GitHub account, then clone it locally:

    git clone https://github.com/YOUR-USERNAME/GhostBot.git
    cd GhostBot

### 2. Install System Dependencies
GhostBot requires native decoders for `moviepy`, `pydub`, and `Pillow` (including text-rendering and WebP support).
* **Ubuntu/Debian:** `sudo apt-get install ffmpeg libsndfile1 sox imagemagick ghostscript libwebp-dev libjpeg-dev zlib1g-dev libfreetype6-dev`
* **MacOS (Homebrew):** `brew install ffmpeg sox imagemagick ghostscript`
* **Windows:** You will need to install FFmpeg and ImageMagick and add them to your PATH.

### 3. Set Up Your Python Environment
Create a virtual environment and install the Python libraries:

    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install -r requirements.txt

### 4. Create a Branch
Always create a new branch for your feature or bug fix:

    git checkout -b feature/parallax-z-axis

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
