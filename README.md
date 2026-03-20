# GhostBot 👻🤖

GhostBot is a fully automated, end-to-end video generation and multi-platform publishing pipeline engineered specifically for high-retention True Crime content. Designed to run completely hands-off via GitHub Actions, the bot handles everything from script generation and dynamic voiceovers to final asset rendering and uploading across multiple social networks.

## 🌟 Key Features

* **Automated Content Pipeline:** Fully autonomous video generation flow requiring zero manual intervention.
* **Intelligent Scripting:** Utilizes a Gemini/OpenRouter fallback system to generate compelling, high-retention scripts.
* **Dynamic Voice Casting:** Leverages advanced Text-To-Speech with SSML pacing for realistic, dramatic, and engaging narration.
* **Multi-Platform Publishing:** Seamlessly uploads finished content to YouTube, Facebook, and Instagram simultaneously.
* **Automated Memory System:** Prevents duplicate content by logging processed `case_name`s to a text file and automatically committing the updates back to the repository.
* **CI/CD Orchestration:** Runs entirely in the cloud using GitHub Actions with automatic environment cleanup and state management.

## 📂 Repository Structure

* `.github/workflows/` - Contains the YAML configuration for the automated GitHub Actions pipeline.
* `music/` - Directory for background music tracks to enhance video atmosphere.
* `sfx/` - Directory for sound effects to add emphasis and pacing to the narration.
* `main.py` - The core execution script that orchestrates the entire video generation and publishing process.
* `meta_upload.py` - Dedicated module for handling Facebook and Instagram Graph API uploads.
* `neural_voice.py` - Manages the text-to-speech engine, dynamic voice casting, and SSML generation.
* `long_form_queue.txt` - Queue management file for scheduling and tracking long-form content generation.
* `topics.txt` - The bot's memory bank; tracks previously covered cases and topics to avoid repetition.
* `requirements.txt` - Python dependencies required to run the pipeline.

## 🚀 Setup & Installation

### Prerequisites
To run GhostBot locally or configure it on a new repository, you will need several API keys to handle generation, media sourcing, and uploading.

1.  Clone the repository:
    ```bash
    git clone [https://github.com/Kashyapman/GhostBot.git](https://github.com/Kashyapman/GhostBot.git)
    cd GhostBot
    ```

2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Environment Variables & Secrets
For GitHub Actions to run the pipeline successfully, ensure the following Repository Secrets are configured in your repository settings:

* `GEMINI_API_KEY` / `OPENROUTER_API_KEY` - For AI script generation.
* `PEXELS_API_KEY` - For fetching relevant B-roll footage and images.
* `YOUTUBE_API_KEY` / `CLIENT_SECRETS` - For YouTube OAuth and automated uploading.
* `META_API_KEY` / `ACCESS_TOKEN` - For Facebook and Instagram API access.
* **GitHub Token:** Ensure the default `GITHUB_TOKEN` under your Action settings has **Read & Write** permissions so the bot can commit memory updates to `topics.txt`.

## ⚙️ How It Works

1.  **Trigger:** The GitHub Action is triggered (either on a cron schedule or via manual dispatch).
2.  **Topic Selection:** `main.py` cross-references `long_form_queue.txt` and `topics.txt` to select a new, unrepeated case.
3.  **Generation:** The AI models generate the script, while `neural_voice.py` crafts the audio with specific SSML pacing for dramatic effect.
4.  **Assembly:** Visuals are pulled and combined with the `music` and `sfx` assets to render the final video.
5.  **Distribution:** The final video is pushed to YouTube via the core pipeline and to Meta platforms via `meta_upload.py`.
6.  **Memory Update:** The new topic is written to `topics.txt`, and the changes are committed back to the repository to prevent future duplicates.

## 📝 License
This project is private and maintained for automated channel management.
