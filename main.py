"""
COLD CASE ARCHIVE — Automated Documentary Pipeline v3.0
========================================================
Upgrades vs v2:
  1.  AI-First Evidence Engine    — Bypasses random Google Image garbage.
  2.  Asset Type Routing          — LLM strictly categorizes shots as "ai", "archive", or "stock".
  3.  Evidence Board Matting      — Adds hyper-realistic pinned-photo shadows to generated images.
  4.  Strict Archive Banning      — Prevents pulling clip-art, random athletes, or modern UI.
"""

import os, random, time, json, glob, math, base64, urllib.parse, re
import xml.etree.ElementTree as ET

import numpy as np
import cv2
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFilter
import PIL.ImageFont

from transformers import pipeline as hf_pipeline
from google import genai
from google.genai import types
from moviepy.editor import (
    ImageClip, VideoClip, VideoFileClip, ColorClip, TextClip,
    AudioFileClip, CompositeVideoClip, CompositeAudioClip,
    concatenate_videoclips, concatenate_audioclips
)
from moviepy.video.fx.all import colorx, fadein, fadeout, loop
from moviepy.audio.fx.all import audio_loop
from faster_whisper import WhisperModel
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import requests

from neural_voice import VoiceEngine, VOICE_MAP
import meta_upload

# ─────────────────────────────────────────────────────────
#  FIX: Pillow >= 10 removed ANTIALIAS
# ─────────────────────────────────────────────────────────
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# ═══════════════════════════════════════════════════════════
#  ENVIRONMENT CREDENTIALS
# ═══════════════════════════════════════════════════════════
GEMINI_KEY        = os.environ.get("GEMINI_API_KEY")
OPENROUTER_KEY    = os.environ.get("OPENROUTER_API_KEY")
YOUTUBE_TOKEN_VAL = os.environ.get("YOUTUBE_TOKEN_JSON")
CF_ACCOUNT_ID     = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN      = os.environ.get("CLOUDFLARE_API_TOKEN")
PEXELS_KEY        = os.environ.get("PEXELS_API_KEY")
PIXABAY_KEY       = os.environ.get("PIXABAY_API_KEY")
SEARCH_API_KEY    = os.environ.get("SEARCH_API_KEY")
GOOGLE_CSE_ID     = os.environ.get("GOOGLE_CSE_ID")

# ═══════════════════════════════════════════════════════════
#  GLOBAL CONFIG
# ═══════════════════════════════════════════════════════════
CHANNEL_HANDLE      = "@TheGlitchArchive"
TOPICS_FILE         = "topics.txt"
VIDEO_WIDTH         = 720
VIDEO_HEIGHT        = 1280
IMAGE_TRANSITION_T  = 3.0        # seconds per image slot
CROSSFADE_DUR       = 0.4        # seconds for cross-dissolve overlap

# ─────────────────────────────────────────────────────────
#  ERA-MATCHED VISUAL TEXTURES
#  Every FLUX.1 ai_prompt gets this appended automatically
# ─────────────────────────────────────────────────────────
ERA_STYLES = {
    "1900s-1930s": (
        "aged sepia photograph, silver gelatin print, heavy grain, deep scratches, "
        "torn edges, water staining, faded tones, yellowed borders"
    ),
    "1940s-1960s": (
        "aged black and white photograph, high contrast, film grain, light bleed on edges, "
        "vignette, non-uniform emulsion, yellowed borders"
    ),
    "1970s-1980s": (
        "Kodachrome film photograph, slightly oversaturated, light leak on left edge, "
        "dust on lens, slight motion blur, faded retro colors"
    ),
    "1990s-2000s": (
        "early digital camera photo, JPEG compression artifacts, overexposed highlights, "
        "slightly desaturated, grainy low-light, colour noise"
    ),
    "modern": (
        "CCTV footage aesthetic, barrel distortion, timestamp overlay blurred out, "
        "greenish tint, horizontal noise lines, security camera vignette"
    ),
    "unknown": (
        "aged archival photograph, faded colors, film grain, documentary style, "
        "muted tones, slight overexposure"
    ),
}

# ─────────────────────────────────────────────────────────
#  CINEMATIC STINGERS
#  Keyword → SFX file in the /sfx/ directory
# ─────────────────────────────────────────────────────────
SFX_KEYWORD_MAP = {
    "knock":   "knock.mp3",
    "bang":    "knock.mp3",
    "scream":  "scream.mp3",
    "yell":    "scream.mp3",
    "step":    "footsteps.mp3",
    "run":     "footsteps.mp3",
    "static":  "static.mp3",
    "glitch":  "static.mp3",
    "breath":  "whisper.mp3",
    "whisper": "whisper.mp3",
    "thud":    "thud.mp3",
}

STINGER_MAP = {
    "impossible":      "deep_impact.mp3",
    "vanished":        "reverb_hit.mp3",
    "never found":     "low_drone_sting.mp3",
    "found dead":      "low_drone_sting.mp3",
    "no explanation":  "deep_impact.mp3",
    "police":          "radio_static_burst.mp3",
    "body was":        "low_drone_sting.mp3",
    "blood":           "reverb_hit.mp3",
    "disappeared":     "reverb_hit.mp3",
    "without a trace": "deep_impact.mp3",
}

# ─────────────────────────────────────────────────────────
#  VARIABLE VIDEO LENGTHS
# ─────────────────────────────────────────────────────────
VIDEO_FORMATS = [
    {"label": "short",  "max_lines": 8,  "description": "Quick Hit  (~45 s)"},
    {"label": "medium", "max_lines": 12, "description": "Standard   (~65 s)"},
    {"label": "deep",   "max_lines": 16, "description": "Deep Dive  (~85 s)"},
]


# ═══════════════════════════════════════════════════════════
#  ANTI-BAN & MEMORY
# ═══════════════════════════════════════════════════════════
def anti_ban_sleep():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        secs = random.randint(300, 600)
        print(f"🕵️  Anti-Ban Sleep: {secs // 60} min {secs % 60} s")
        time.sleep(secs)


def get_past_topics() -> str:
    if not os.path.exists(TOPICS_FILE):
        return ""
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    return "\n".join(lines[-100:])


def save_new_topic(case_name: str):
    try:
        with open(TOPICS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{case_name}\n")
        print(f"💾 Saved '{case_name}' to memory bank.")
    except Exception as e:
        print(f"⚠️  Could not save topic: {e}")


# ═══════════════════════════════════════════════════════════
#  GLOBAL SOTA INTELLIGENCE — self-selecting best free model
# ═══════════════════════════════════════════════════════════

CHANNEL_MEMORY_FILE = "channel_memory.json"

def _clean_text_snippet(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())

def _score_title_candidate(title: str, case_name: str = "") -> int:
    """
    Scores a title for curiosity, brevity, and spoiler avoidance.
    """
    t = _clean_text_snippet(title)
    tl = t.lower()
    score = 0

    if not t:
        return -999

    # Length sweet spot for Shorts
    if 28 <= len(t) <= 44:
        score += 6
    elif len(t) <= 50:
        score += 3
    else:
        score -= 3

    # Curiosity-gap language
    curiosity_terms = [
        "what", "why", "how", "didn't exist", "vanished", "missing",
        "found", "unanswered", "unknown", "no name", "no identity",
        "disappeared", "untold", "the man", "the woman"
    ]
    if any(term in tl for term in curiosity_terms):
        score += 4

    # Spoiler penalty
    spoiler_terms = [
        "explained", "answered", "solved", "mystery explained", "case file",
        "full story", "timeline", "inside", "complete"
    ]
    if any(term in tl for term in spoiler_terms):
        score -= 5

    # Avoid directly repeating the case name
    if case_name and case_name.lower() in tl:
        score -= 4

    # Strong first token / clean punctuation
    if not any(ch in t for ch in [":", "-", "|"]):
        score += 1

    # Slight reward for being specific but not too obvious
    if any(term in tl for term in ["man", "woman", "boy", "girl", "file", "body", "note"]):
        score += 1

    return score


def _pick_best_title(candidates: list[str], case_name: str = "") -> str:
    clean = []
    for cand in candidates:
        c = _clean_text_snippet(cand).strip('"').strip("'")
        if c and c not in clean:
            clean.append(c)

    if not clean:
        return "They found WHAT?"

    return max(clean, key=lambda t: _score_title_candidate(t, case_name))


def build_retention_profile(script_data: dict, case_name: str = "") -> dict:
    """
    Annotates the script with beat-level intent without changing the core story.
    """
    lines = script_data.get("lines", []) if isinstance(script_data, dict) else []
    n = len(lines)
    if n == 0:
        return {"beats": [], "case_name": case_name or script_data.get("case_name", "") if isinstance(script_data, dict) else ""}

    if n == 1:
        beats = ["hook"]
    elif n == 2:
        beats = ["hook", "loop"]
    elif n == 3:
        beats = ["hook", "contradiction", "loop"]
    elif n <= 5:
        beats = ["hook"] + ["escalation"] * max(0, n - 2) + ["loop"]
    else:
        beats = []
        mid_start = max(2, n - 4)
        for i in range(n):
            if i == 0:
                beats.append("hook")
            elif i in (1, 2, 3):
                beats.append("escalation")
            elif i in (mid_start, mid_start + 1):
                beats.append("contradiction")
            elif i == n - 1:
                beats.append("loop")
            else:
                beats.append("escalation")

    speaker_fallback = []
    if n == 1:
        speaker_fallback = ["narrator"]
    elif n == 2:
        speaker_fallback = ["narrator", "witness"]
    else:
        speaker_fallback = []
        for i in range(n):
            if i == 0 or i == n - 1:
                speaker_fallback.append("narrator")
            elif i in (max(1, n // 2 - 1), max(2, n // 2)):
                speaker_fallback.append("document")
            elif i in (max(1, n // 2),):
                speaker_fallback.append("witness")
            else:
                speaker_fallback.append("narrator")

    style_defaults = {
        "hook": "Hushed, immediate, impossible.",
        "escalation": "Tight, escalating, factual.",
        "contradiction": "Cold, documentary, evidentiary.",
        "loop": "Quiet, unresolved, haunting.",
    }

    for i, line in enumerate(lines):
        if not isinstance(line, dict):
            continue

        clean = _clean_text_snippet(line.get("clean_text", ""))
        acting = _clean_text_snippet(line.get("acting_text", clean))
        style = _clean_text_snippet(line.get("style_instruction", ""))

        line["clean_text"] = clean
        line["acting_text"] = acting
        line["style_instruction"] = style or style_defaults.get(beats[i], "Measured, authoritative.")

        speaker = _clean_text_snippet(line.get("speaker", "")).lower()
        if speaker not in {"narrator", "witness", "document", "reporter"}:
            line["speaker"] = speaker_fallback[i]

        line["beat"] = beats[i]

    script_data["lines"] = lines
    script_data["retention_profile"] = {
        "case_name": case_name or script_data.get("case_name", ""),
        "beat_count": n,
        "hook": "line_1_immediate_interrupt",
        "middle": "contradiction_to_witness_evidence",
        "end": "loop_back_to_opening_question",
    }

    if case_name and not script_data.get("case_name"):
        script_data["case_name"] = case_name

    return script_data


def load_channel_memory() -> list[dict]:
    if not os.path.exists(CHANNEL_MEMORY_FILE):
        return []
    try:
        with open(CHANNEL_MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def record_run_memory(entry: dict) -> None:
    try:
        memory = load_channel_memory()
        memory.append(entry)
        memory = memory[-200:]
        with open(CHANNEL_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
        print("💾 Saved run memory.")
    except Exception as e:
        print(f"⚠️  Could not save run memory: {e}")


def get_top_free_openrouter_models(limit: int = 3) -> list[str]:
    print("🔍 Scouting OpenRouter for top SOTA free models...")
    defaults = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-235b-a22b:free",
        "mistralai/mistral-large:free",
    ]
    REWARD = {
        "meta-llama/llama-3.3-70b-instruct:free": 99,
        "qwen/qwen3-235b-a22b:free":               98,
        "mistralai/mistral-large:free":             97,
        "deepseek/deepseek-r1:free":                95,
        "nvidia/nemotron-4-super:free":             94,
        "google/gemma-3-27b-it:free":               90,
    }
    if not OPENROUTER_KEY:
        return defaults
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        if r.status_code != 200:
            return defaults
        all_models = r.json().get("data", [])
        free_ids = [
            m["id"] for m in all_models
            if (m.get("pricing", {}).get("prompt") == "0"
                and m.get("pricing", {}).get("completion") == "0")
            or ":free" in m["id"]
        ]
        if not free_ids:
            return defaults

        def score(mid):
            ml = mid.lower()
            for k, v in REWARD.items():
                if k in ml:
                    return v
            s = 50
            if "instruct" in ml: s += 20
            if "llama-3"  in ml: s += 15
            if "qwen"     in ml: s += 15
            if "mistral"  in ml: s += 10
            return s

        best = sorted(free_ids, key=score, reverse=True)[:limit]
        print(f"🌟 SOTA Cascade: {best}")
        return best
    except Exception:
        return defaults


def ask_llm(system_instruction: str, prompt: str, sota_models: list[str]) -> str:
    """Tries OpenRouter SOTA cascade then Gemini Flash as final fallback."""
    full_prompt = prompt + "\n\nCRITICAL: Return ONLY the exact requested content. No preamble, no markdown."

    if OPENROUTER_KEY:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        }
        for model in sota_models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user",   "content": full_prompt},
                ],
            }
            try:
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers, json=payload, timeout=45
                )
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                time.sleep(4)
            except Exception:
                time.sleep(4)

    # Gemini Flash fallback
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        cfg = types.GenerateContentConfig(
            system_instruction=system_instruction, temperature=0.7
        )
        rsp = client.models.generate_content(
            model="models/gemini-2.5-flash", contents=full_prompt, config=cfg
        )
        return rsp.text.strip()
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════
#  LIVE RESEARCH ENGINE
# ═══════════════════════════════════════════════════════════
def scrape_wikipedia(case_name: str) -> str:
    """Fetches the full Wikipedia article plain-text extract for a case."""
    print(f"📚 Wikipedia → {case_name}")
    ua = {"User-Agent": "GlitchArchiveBot/2.0 (educational documentary)"}
    try:
        # Step 1: Search
        sr = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "format": "json",
                    "list": "search", "srsearch": case_name, "srlimit": 1},
            headers=ua, timeout=10
        )
        results = sr.json().get("query", {}).get("search", [])
        if not results:
            return ""
        title = results[0]["title"]

        # Step 2: Full extract
        er = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "format": "json", "prop": "extracts",
                    "titles": title, "exintro": False, "explaintext": True,
                    "exsectionformat": "plain"},
            headers=ua, timeout=15
        )
        pages = er.json().get("query", {}).get("pages", {})
        for _, page in pages.items():
            extract = page.get("extract", "")
            return extract[:4000]          # enough for strong research, not token-greedy
    except Exception as e:
        print(f"⚠️  Wikipedia failed: {e}")
    return ""


def scrape_google_news_rss(case_name: str) -> str:
    """Fetches recent headlines via Google News RSS — no API key needed."""
    print(f"📰 Google News RSS → {case_name}")
    try:
        q   = urllib.parse.quote(case_name)
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        r   = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root  = ET.fromstring(r.content)
        items = root.findall(".//item")[:6]
        lines = []
        for item in items:
            t = item.find("title")
            d = item.find("description")
            if t is not None and t.text:
                lines.append(t.text)
            if d is not None and d.text:
                clean = (d.text
                         .replace("<b>", "").replace("</b>", "")
                         .replace("&nbsp;", " ").replace("&amp;", "&"))
                lines.append(clean[:220])
        return "\n".join(lines[:10])
    except Exception as e:
        print(f"⚠️  Google News RSS failed: {e}")
    return ""


def detect_era(text: str) -> str:
    """Extracts the decade of a case from any text block."""
    import re
    years = re.findall(r"\b(1[89]\d{2}|20[012]\d)\b", text)
    if not years:
        return "unknown"
    earliest = min(int(y) for y in years)
    if   earliest < 1935: return "1900s-1930s"
    elif earliest < 1965: return "1940s-1960s"
    elif earliest < 1990: return "1970s-1980s"
    elif earliest < 2010: return "1990s-2000s"
    else:                 return "modern"


def propose_case_and_research(
    niche: str,
    past_topics: str,
    sota_models: list[str]
) -> tuple[str, str, str]:
    """
    1. Asks an LLM to propose one specific, obscure, real case.
    2. Scrapes Wikipedia + Google News for that case.
    3. Returns (case_name, research_brief, era).
    """
    print(f"🔬 Phase 0 Research Engine → niche: '{niche}'")

    avoid = (f"CRITICAL — Do NOT suggest any case from this list:\n{past_topics}\n"
             if past_topics else "")

    proposal = ask_llm(
        "You are a veteran true crime research specialist.",
        f"""Suggest ONE highly specific, obscure, and 100% real historical case in the category: "{niche}".
{avoid}
Requirements:
- Must be a real, documented event with a verifiable Wikipedia article
- Must be genuinely unusual, eerie, or deeply puzzling
- Reply with ONLY the exact case name (e.g. "The Tamam Shud Case")""",
        sota_models
    ).strip().strip('"').strip("'")

    if not proposal or len(proposal) > 90:
        proposal = f"obscure unsolved {niche} case"
    print(f"🕵️  Selected Case: {proposal}")

    wiki_text = scrape_wikipedia(proposal)
    news_text = scrape_google_news_rss(proposal)
    era       = detect_era(wiki_text + " " + news_text)

    brief = f"CASE NAME: {proposal}\n\n"
    if wiki_text:
        brief += f"=== WIKIPEDIA RESEARCH ===\n{wiki_text}\n\n"
    if news_text:
        brief += f"=== RECENT NEWS & RE-EXAMINATIONS ===\n{news_text}\n\n"
    if not wiki_text and not news_text:
        brief += "(No external source found — write from best available knowledge)\n"

    print(f"📅 Detected Era: {era}")
    return proposal, brief, era


# ═══════════════════════════════════════════════════════════
#  THE WRITER
#  Research-grounded · Channel persona · Multi-draft · Dual voice
# ═══════════════════════════════════════════════════════════

def generate_viral_script(sota_models: list[str]) -> dict | None:
    print("🧠 Phase 1 Writer: Research → Draft → Refine...")

    content_pool = [
        "Bizarre Unsolved Disappearances",
        "Impossible Heists and Robberies",
        "People Who Faked Their Own Deaths",
        "Real-life Glitches in the Matrix",
        "Bizarre Historical Artifacts That Shouldn't Exist",
        "Creepy Hijacked TV and Radio Broadcasts",
        "Unsolved Coded Messages That Baffled Intelligence Agencies",
        "People Who Appeared From Nowhere With No Identity",
        "Government Cover-Ups That Were Later Confirmed",
        "Serial Cases That Stopped Overnight With No Explanation",
    ]
    niche = random.choice(content_pool)
    past_topics = get_past_topics()

    case_name, research_brief, era = propose_case_and_research(
        niche, past_topics, sota_models
    )

    template = """{
  "case_name": "The Tamam Shud Case",
  "era": "1940s-1960s",
  "recommended_voice_model": "Charon",
  "lines": [
    {
      "speaker": "narrator",
      "style_instruction": "Hushed whisper, building dread.",
      "acting_text": "He was found on the beach. <break time='1.2s'/> No wallet. No name. <emphasis level='strong'>No identity.</emphasis>",
      "clean_text": "He was found on the beach. No wallet. No name. No identity."
    },
    {
      "speaker": "document",
      "style_instruction": "Cold, flat, official — reading from a coroner report.",
      "acting_text": "<prosody rate='slow' pitch='-10%'>Cause of death: unknown. Identity: unknown. Purpose: unknown.</prosody>",
      "clean_text": "Cause of death: unknown. Identity: unknown. Purpose: unknown."
    },
    {
      "speaker": "witness",
      "style_instruction": "Quietly stunned, personal — quoting a detective who worked the case.",
      "acting_text": "The detective told me, <break time='0.6s'/> <emphasis level='strong'>'In thirty years, I never saw anything like it.'</emphasis>",
      "clean_text": "The detective told me, in thirty years, I never saw anything like it."
    }
  ]
}"""

    stage1_prompt = f"""
You are the writer for "COLD CASE ARCHIVE" — a YouTube Shorts channel run by a former homicide detective turned investigative journalist.
Your voice is world-weary, precise, and quietly furious.
You do not sensationalize. You state facts and let the horror speak for itself.
You expose what investigators got WRONG and what witness accounts directly contradicted official reports.

CASE NAME TO CENTER: {case_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESEARCH BRIEF — THIS IS YOUR ONLY SOURCE:
{research_brief}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BANNED CASES (do NOT write about these):
{past_topics if past_topics else "(none yet)"}

━━━━ PSYCHOLOGICAL PACING RULES ━━━━
LINE 1  — PATTERN INTERRUPT: Open with the single most impossible confirmed fact. Add the human cost or consequence if it sharpens the hook. No intro.
LINES 2–5 — ESCALATION: Short, punchy, increasingly specific. Every line must add new information.
LINES 6–8 — THE CONTRADICTION (MANDATORY): State what official records said. Immediately follow with what witnesses or physical evidence actually showed. This is why it was never solved.
LINES 9–10 — THE IMPOSSIBLE DETAIL: The fact that defied forensic logic, physics, or all expert explanation.
FINAL LINE — PERFECT LOOP: Circle back to the first word, image, or emotional wound from Line 1.

━━━━ MULTI-VOICE DIRECTION ━━━━
Use "speaker" field to assign each line one of these voices:
  "narrator"  — main storytelling (world-weary detective voice, most lines)
  "document"  — reading official police, coroner, or government reports (cold, bureaucratic)
  "witness"   — quoting what investigators, witnesses, or experts actually said (personal, stunned)
Use each voice at least once. Never use "document" twice in a row.

━━━━ SSML ACTING TAGS ━━━━ (inside acting_text only — never in clean_text)
  <break time="1s"/>                       pause before a reveal
  <emphasis level="strong">WORD</emphasis> hit the word hard without shouting
  <prosody rate="slow" pitch="-15%">       maximum dread, slower delivery
  <prosody rate="fast">                    rapid factual escalation
Use micro-pauses before contradiction lines and on the final reveal.

━━━━ BANNED CLICHÉS ━━━━
"Dive into" / "chilling reminder" / "Some say" / "Will we ever know?" / "Buckle up" / "In the annals of history"

━━━━ TECHNICAL RULES ━━━━
- combined clean_text word count: 130–160 words
- 8 to 12 total line objects
- era field must be: "{era}"
- First line must feel immediate and specific, never generic.
- Prefer concrete nouns, dates, locations, evidence, and witness language.
- Keep the final line haunting and circular, not explanatory.

Return ONLY valid JSON exactly matching this format:
{template}
"""

    client = genai.Client(api_key=GEMINI_KEY)
    json_config = types.GenerateContentConfig(
        temperature=0.92, top_p=0.95, response_mime_type="application/json"
    )

    script_data = None

    try:
        rsp = client.models.generate_content(
            model="models/gemini-2.5-pro", contents=stage1_prompt, config=json_config
        )
        script_data = json.loads(rsp.text)
        print("✅ Stage 1: Gemini 2.5 Pro")
    except Exception as e:
        print(f"⚠️  Gemini Pro failed: {e}")

    if not script_data and OPENROUTER_KEY:
        headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
        for model in sota_models:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": stage1_prompt}],
                "response_format": {"type": "json_object"},
            }
            try:
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers, json=payload, timeout=70
                )
                if r.status_code == 200:
                    raw = (r.json()["choices"][0]["message"]["content"]
                           .replace("```json", "").replace("```", "").strip())
                    script_data = json.loads(raw)
                    print(f"✅ Stage 1: {model}")
                    break
            except Exception:
                time.sleep(5)

    if not script_data:
        try:
            rsp = client.models.generate_content(
                model="models/gemini-2.5-flash", contents=stage1_prompt, config=json_config
            )
            script_data = json.loads(rsp.text)
            print("✅ Stage 1: Gemini 2.5 Flash (fallback)")
        except Exception as e:
            print(f"❌ All writers failed: {e}")
            return None

    if script_data and script_data.get("lines"):
        print("✏️  Stage 2: Refinement Pass...")
        raw_lines = "\n".join(
            f"[{l.get('speaker', 'narrator')}]: {l.get('clean_text', '')}"
            for l in script_data["lines"]
        )
        refine_prompt = f"""You are a veteran documentary script editor.
Below is a first draft of a true crime script. Make it 30% more cinematic WITHOUT adding new facts.

FIRST DRAFT:
{raw_lines}

EDITING RULES:
1. Rewrite the weakest or most generic sentence to be more visceral and specific.
2. Keep the opening immediate; if the first line feels abstract, compress it.
3. Preserve speaker assignments and the contradiction structure.
4. Ensure the final line loops back to the first word or concept of the opening line.
5. Keep total word count within ±12 words of the original draft.

Return ONLY a numbered list of revised clean_text lines:
1. [revised line]
2. [revised line]
...
"""
        revised = ask_llm("You are an elite documentary script editor.", refine_prompt, sota_models)
        if revised:
            revised_lines = [
                ln.strip() for ln in revised.split("\n")
                if ln.strip() and ln.strip()[0].isdigit()
            ]
            for i, ln in enumerate(revised_lines):
                if i < len(script_data["lines"]):
                    clean = ln.split(".", 1)[-1].strip().lstrip("0123456789. ")
                    if clean and len(clean) > 10:
                        script_data["lines"][i]["clean_text"] = clean
        print("✅ Stage 2 complete")

    if "era" not in script_data:
        script_data["era"] = era
    if "case_name" not in script_data:
        script_data["case_name"] = case_name

    script_data = build_retention_profile(script_data, case_name=case_name)
    return script_data


# ═══════════════════════════════════════════════════════════
#  AI-FIRST CINEMATOGRAPHER & ASSET ROUTING
# ═══════════════════════════════════════════════════════════

def generate_cinematographer_prompts(
    script_text: str,
    required_images: int,
    sota_models: list[str],
    era: str = "unknown"
) -> list[dict]:
    era_texture = ERA_STYLES.get(era, ERA_STYLES["unknown"])

    template = """{
  "visuals": [
    {
      "asset_type": "ai",
      "search_query": "Somerton beach 1948",
      "hero_object": "worn leather wallet",
      "shot_type": "Extreme Close-Up",
      "camera_motion": "slow push-in",
      "motion_cue": "static tension",
      "ai_prompt": "Extreme close-up worn leather wallet on detective desk, harsh desk lamp, aged 35mm film, film halation, dust on lens, yellowed, non-uniform grain, cinematic, vertical, 1940s-1960s film texture"
    }
  ]
}"""

    prompt = f"""You are an elite Documentary Cinematographer and Archival Researcher.
Map {required_images} visually varied, perfectly paced shots to the voiceover script below.

SCRIPT:
"{script_text}"

ERA OF THIS CASE: {era}
MANDATORY TEXTURE FOR EVERY AI PROMPT — append this to every ai_prompt:
"{era_texture}"

SHOT DESIGN RULES:
1. asset_type MUST be "ai" for 95% of shots. AI recreations (e.g., "macro shot of a rusted key", "top-down view of redacted police files") look 100x better than random archive searches.
2. asset_type CAN be "archive" ONLY for highly specific, globally known historical figures or locations (e.g., "Alcatraz"). BANNED: Do not use "archive" for generic nouns like "analyst", "blueprint", "gears".
3. asset_type CAN be "stock" for abstract mood elements (e.g. "dark rainy window").
4. Every visual must carry one clear hero object.
5. Rotate shot types naturally: Extreme Close-Up, Wide Establishing, Over-the-Shoulder, Dutch Angle.
6. BANNED: legible text, signs, numbers, captions, or interface overlays.

Return ONLY valid JSON with EXACTLY {required_images} items:
{template}
"""

    def _normalize_visual(item: dict, idx: int) -> dict:
        if not isinstance(item, dict):
            item = {}
            
        asset_type = item.get("asset_type", "ai").lower()
        if asset_type not in ["ai", "archive", "stock"]:
            asset_type = "ai"
            
        item["asset_type"] = asset_type
        item.setdefault("search_query", "historical crime evidence")
        item.setdefault("hero_object", "redacted document")
        item.setdefault("shot_type", ["Extreme Close-Up", "Wide Establishing", "Over-the-Shoulder", "Dutch Angle"][idx % 4])
        item.setdefault("camera_motion", "slow push-in")
        item.setdefault("motion_cue", "subtle human movement")
        item.setdefault(
            "ai_prompt",
            f"Dark cinematic mystery scene, documentary style, volumetric lighting, vertical composition, "
            f"{item.get('hero_object', 'redacted document')}, {era_texture}"
        )
        return item

    if OPENROUTER_KEY:
        headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
        for model in sota_models:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
            try:
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers, json=payload, timeout=60
                )
                if r.status_code == 200:
                    raw = (r.json()["choices"][0]["message"]["content"]
                           .replace("```json", "").replace("```", "").strip())
                    visuals = json.loads(raw).get("visuals", [])
                    visuals = [_normalize_visual(v, i) for i, v in enumerate(visuals)]
                    while len(visuals) < required_images:
                        visuals.append(_normalize_visual({}, len(visuals)))
                    return visuals[:required_images]
            except Exception:
                time.sleep(4)

    try:
        client = genai.Client(api_key=GEMINI_KEY)
        cfg = types.GenerateContentConfig(
            temperature=0.7, response_mime_type="application/json"
        )
        rsp = client.models.generate_content(
            model="models/gemini-2.5-flash", contents=prompt, config=cfg
        )
        visuals = (json.loads(rsp.text.replace("```json", "").replace("```", "").strip())
                   .get("visuals", []))
        visuals = [_normalize_visual(v, i) for i, v in enumerate(visuals)]
        while len(visuals) < required_images:
            visuals.append(_normalize_visual({}, len(visuals)))
        return visuals[:required_images]
    except Exception as e:
        print(f"❌ Visual prompt generation failed: {e}")

    return [_normalize_visual({}, i) for i in range(required_images)]


# ═══════════════════════════════════════════════════════════
#  4-LAYER TITANIUM PIPELINE
# ═══════════════════════════════════════════════════════════
def fetch_archive_image(query: str, filename: str) -> bool:
    print(f"🏛️  [1/4] Archives: {query[:45]}...")
    clean = " ".join(query.split()[:4])
    ua    = {"User-Agent": "GhostBot/2.0 (Educational Documentary)"}

    # Wikipedia pageimages
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "format": "json", "prop": "pageimages",
                    "generator": "search", "gsrsearch": clean,
                    "gsrlimit": 3, "pithumbsize": 1000},
            headers=ua, timeout=10
        )
        pages = r.json().get("query", {}).get("pages", {})
        for _, page in pages.items():
            if "thumbnail" in page:
                data = requests.get(page["thumbnail"]["source"], headers=ua, timeout=15).content
                with open(filename, "wb") as f: f.write(data)
                if os.path.getsize(filename) > 1000: return True
    except Exception: pass

    # Google CSE
    if SEARCH_API_KEY and GOOGLE_CSE_ID:
        try:
            params = {"q": f"{clean} evidence photo", "cx": GOOGLE_CSE_ID,
                      "key": SEARCH_API_KEY, "searchType": "image",
                      "num": 1, "safe": "active"}
            items = requests.get(
                "https://www.googleapis.com/customsearch/v1", params=params
            ).json().get("items", [])
            if items:
                data = requests.get(items[0]["link"], headers=ua, timeout=15).content
                with open(filename, "wb") as f: f.write(data)
                if os.path.getsize(filename) > 1000: return True
        except Exception: pass

    # Internet Archive
    try:
        docs = requests.get(
            "https://archive.org/advancedsearch.php",
            params={"q": f'"{clean}" AND mediatype:image',
                    "fl": "identifier", "rows": 3, "output": "json"},
            headers=ua, timeout=10
        ).json().get("response", {}).get("docs", [])
        for doc in docs:
            iid = doc.get("identifier")
            if iid:
                data = requests.get(
                    f"https://archive.org/download/{iid}/{iid}.jpg",
                    headers=ua, timeout=15
                ).content
                if len(data) > 1000:
                    with open(filename, "wb") as f: f.write(data)
                    return True
    except Exception: pass
    return False


def fetch_cloudflare_image(prompt: str, filename: str) -> bool:
    print(f"☁️  [2/4] FLUX.1: {prompt[:45]}...")
    if not CF_ACCOUNT_ID or not CF_API_TOKEN: return False
    url = (f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}"
           f"/ai/run/@cf/black-forest-labs/flux-1-schnell")
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json={"prompt": prompt}, timeout=50)
        if r.status_code == 200:
            ct = r.headers.get("Content-Type", "")
            if "application/json" in ct:
                b64 = r.json().get("result", {}).get("image")
                if b64:
                    with open(filename, "wb") as f: f.write(base64.b64decode(b64))
                    return True
            else:
                with open(filename, "wb") as f: f.write(r.content)
                if os.path.getsize(filename) > 1000: return True
    except Exception: pass
    return False


def fetch_pexels_image(prompt: str, filename: str) -> bool:
    print(f"📷 [3/4] Pexels: {prompt[:45]}...")
    if not PEXELS_KEY: return False
    query = " ".join(prompt.split()[:5])
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_KEY},
            params={"query": query, "per_page": 1, "orientation": "portrait"},
            timeout=30
        )
        if r.status_code == 200:
            photos = r.json().get("photos", [])
            if photos:
                data = requests.get(photos[0]["src"]["large2x"], timeout=20).content
                with open(filename, "wb") as f: f.write(data)
                if os.path.getsize(filename) > 1000: return True
    except Exception: pass
    return False


def fetch_placeholder_image(filename: str) -> bool:
    try:
        PIL.Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (20, 20, 30)).save(filename, "JPEG")
        return True
    except Exception: return False


def verify_and_convert_image(filename: str) -> bool:
    try:
        with PIL.Image.open(filename) as img:
            img.load()
            if img.mode not in ("RGB",):
                img = img.convert("RGB")
            img.save(filename, format="JPEG", quality=95)
        return True
    except Exception: return False


# ═══════════════════════════════════════════════════════════
#  CONTEXTUAL MATTING 
# ═══════════════════════════════════════════════════════════
def apply_diegetic_matting(filename: str) -> bool:
    try:
        with PIL.Image.open(filename) as img:
            img  = img.convert("RGBA")
            tw, th = VIDEO_WIDTH, VIDEO_HEIGHT
            bg   = PIL.Image.new("RGBA", (tw, th), (12, 12, 15, 255))
            style = random.choice(["polaroid", "cinematic_shadow", "crt_monitor", "evidence_board"])

            if style == "polaroid":
                img.thumbnail((450, 450), PIL.Image.Resampling.LANCZOS)
                fw, fh = img.width + 40, img.height + 120
                frame  = PIL.Image.new("RGBA", (fw, fh), (245, 245, 240, 255))
                frame.paste(img, (20, 20))
                frame = frame.rotate(random.uniform(-5, 5), expand=True, fillcolor=(0,0,0,0))
                ox = (tw - frame.width)  // 2
                oy = (th - frame.height) // 2
                bg.paste(frame, (ox, oy), frame)

            elif style == "cinematic_shadow":
                img.thumbnail((600, 800), PIL.Image.Resampling.LANCZOS)
                shadow = PIL.Image.new("RGBA", img.size, (0, 0, 0, 220))
                shadow = shadow.filter(PIL.ImageFilter.GaussianBlur(15))
                ox = (tw - img.width)  // 2
                oy = (th - img.height) // 2
                bg.paste(shadow, (ox + 15, oy + 15), shadow)
                bg.paste(img,    (ox, oy),            img)

            elif style == "evidence_board":
                img.thumbnail((540, 720), PIL.Image.Resampling.LANCZOS)
                border = 12
                fw, fh = img.width + border*2, img.height + border*2
                frame  = PIL.Image.new("RGBA", (fw, fh), (245, 245, 240, 255))
                frame.paste(img, (border, border))
                frame = frame.rotate(random.uniform(-3, 3), expand=True, fillcolor=(0,0,0,0))
                
                shadow = PIL.Image.new("RGBA", frame.size, (0, 0, 0, 180))
                shadow = shadow.filter(PIL.ImageFilter.GaussianBlur(12))
                
                ox = (tw - frame.width)  // 2
                oy = (th - frame.height) // 2
                bg.paste(shadow, (ox + 12, oy + 12), shadow)
                bg.paste(frame, (ox, oy), frame)

            elif style == "crt_monitor":
                img.thumbnail((680, 1000), PIL.Image.Resampling.LANCZOS)
                d = PIL.ImageDraw.Draw(img)
                for y in range(0, img.height, 4):
                    d.line([(0, y), (img.width, y)], fill=(0, 0, 0, 70), width=1)
                ox = (tw - img.width)  // 2
                oy = (th - img.height) // 2
                bg.paste(img, (ox, oy), img)

            bg.convert("RGB").save(filename, format="JPEG", quality=95)
            return True
    except Exception as e:
        print(f"⚠️  Matting error: {e}")
        return False


# ═══════════════════════════════════════════════════════════
#  EASED PARALLAX ENGINE
# ═══════════════════════════════════════════════════════════
def generate_depth_map(image_path: str) -> str | None:
    print(f"🧠 Depth Map → {os.path.basename(image_path)}")
    try:
        estimator  = hf_pipeline(
            task="depth-estimation",
            model="depth-anything/Depth-Anything-V2-Small-hf",
            device="cpu"
        )
        img        = PIL.Image.open(image_path).convert("RGB")
        depth_path = image_path.replace(".jpg", "_depth.jpg")
        estimator(img)["depth"].save(depth_path)
        return depth_path
    except Exception as e:
        print(f"⚠️  Depth map failed: {e}")
        return None


def _ease_in_out(progress: float) -> float:
    """Cosine S-curve — makes camera feel operated by a human, not a script."""
    return (1 - math.cos(progress * math.pi)) / 2


def apply_parallax_effect(
    t: float,
    duration: float,
    img_array: np.ndarray,
    depth_array: np.ndarray,
    direction: str = "left"
) -> np.ndarray:
    max_shift   = 28.0
    progress    = t / duration
    eased       = _ease_in_out(progress)

    if direction == "left":
        shift = max_shift * (1.0 - eased)
    else:
        shift = max_shift * eased

    normalized  = depth_array / 255.0
    shift_map   = (normalized * shift).astype(np.float32)

    h, w        = img_array.shape[:2]
    map_x       = np.zeros((h, w), np.float32)
    map_y       = np.zeros((h, w), np.float32)
    for y in range(h):
        map_y[y, :] = y
        map_x[y, :] = np.arange(w) + shift_map[y, :]

    return cv2.remap(
        img_array, map_x, map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )


def get_image_clip(asset_type: str, search_query: str, ai_prompt: str, duration: float, index: int):
    """Full Titanium Pipeline + eased parallax + cross-dissolve."""
    fname = f"temp_img_{index}.jpg"
    ok = False
    
    print(f"🎬 [Shot {index}] Type: {asset_type} | Target: {search_query[:30] if asset_type != 'ai' else ai_prompt[:30]}")

    if asset_type == "archive":
        ok = fetch_archive_image(search_query, fname)
        if not ok: ok = fetch_cloudflare_image(ai_prompt, fname)
    elif asset_type == "stock":
        ok = fetch_pexels_image(search_query, fname)
        if not ok: ok = fetch_cloudflare_image(ai_prompt, fname)
    else: # "ai"
        ok = fetch_cloudflare_image(ai_prompt, fname)
        if not ok: ok = fetch_pexels_image(search_query, fname)
        if not ok: ok = fetch_archive_image(search_query, fname)

    if not ok: ok = fetch_placeholder_image(fname)

    if not verify_and_convert_image(fname):
        fetch_placeholder_image(fname)
    apply_diegetic_matting(fname)

    try:
        base = (ImageClip(fname)
                .resize(height=VIDEO_HEIGHT))
        if base.w < VIDEO_WIDTH:
            base = base.resize(width=VIDEO_WIDTH)
        base = base.crop(
            x_center=base.w / 2, y_center=base.h / 2,
            width=VIDEO_WIDTH, height=VIDEO_HEIGHT
        )

        cropped_path = f"temp_cropped_{index}.jpg"
        base.save_frame(cropped_path, t=0)
        depth_path = generate_depth_map(cropped_path)

        if depth_path and os.path.exists(depth_path):
            img_arr   = cv2.cvtColor(cv2.imread(cropped_path), cv2.COLOR_BGR2RGB)
            depth_arr = cv2.imread(depth_path, cv2.IMREAD_GRAYSCALE)
            cam_dir   = "left" if index % 2 == 0 else "right"

            clip = VideoClip(
                make_frame=lambda t: apply_parallax_effect(
                    t, duration, img_arr, depth_arr, cam_dir
                ),
                duration=duration
            )
        else:
            # Ken Burns with eased zoom
            def zoom_func(t):
                p     = t / duration
                eased = _ease_in_out(p)
                return (1 + 0.06 * eased) if index % 2 == 0 else (1.06 - 0.06 * eased)

            clip = base.resize(zoom_func).crop(
                x_center=VIDEO_WIDTH / 2, y_center=VIDEO_HEIGHT / 2,
                width=VIDEO_WIDTH, height=VIDEO_HEIGHT
            )

        clip = clip.fx(fadein, CROSSFADE_DUR).fx(fadeout, CROSSFADE_DUR)
        return clip

    except Exception as e:
        print(f"⚠️  Clip {index} failed: {e}")
        return ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 35), duration=duration)


# ═══════════════════════════════════════════════════════════
#  ATMOSPHERICS & MUSIC 
# ═══════════════════════════════════════════════════════════
def fetch_atmospheric_b_roll(duration: float, filename: str = "temp_atmosphere.mp4") -> bool:
    print("🌫️  Fetching Atmospheric B-Roll (Pexels Video)...")
    if not PEXELS_KEY: return False
    queries = ["dust particles black background", "film grain overlay dark",
               "rain drops dark glass", "smoke dark background", "fog night dark"]
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_KEY},
            params={"query": random.choice(queries), "per_page": 3, "orientation": "portrait"},
            timeout=30
        )
        if r.status_code == 200:
            videos = r.json().get("videos", [])
            if videos:
                video  = random.choice(videos)
                files  = [f for f in video.get("video_files", []) if f.get("quality") == "hd"] \
                         or video.get("video_files", [])
                if files:
                    with open(filename, "wb") as f:
                        f.write(requests.get(files[0]["link"], timeout=45).content)
                    return True
    except Exception: pass
    return False


def fetch_pixabay_audio(
    script_text: str,
    sota_models: list[str],
    filename: str = "temp_bg_music.mp3"
) -> bool:
    print("🎵 AI Music Supervisor scoring the scene...")
    if not PIXABAY_KEY: return False
    vibe = ask_llm(
        "You are a cinematic Music Supervisor. Output ONLY data.",
        f"""Read this true crime script. Output EXACTLY 2–3 instrumental keywords 
for a stock music search. BANNED: murder, ghost, detective, blood, death, victim.
GOOD examples: 'dark ambient drone', 'tension strings', 'low horror synth'.
SCRIPT: {script_text}""",
        sota_models
    ).replace('"', '').replace("'", "").strip()

    if not vibe or len(vibe) > 50:
        vibe = "dark suspense ambient"
    try:
        r = requests.get(
            "https://pixabay.com/api/audio/",
            params={"key": PIXABAY_KEY, "q": vibe, "per_page": 3},
            timeout=15
        )
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits and hits[0].get("audio"):
                with open(filename, "wb") as f:
                    f.write(requests.get(hits[0]["audio"], timeout=30).content)
                return True
    except Exception: pass
    return False


# ═══════════════════════════════════════════════════════════
#  SFX + CINEMATIC STINGERS
# ═══════════════════════════════════════════════════════════
def add_sfx(audio_clip, text: str):
    text_l = text.lower()
    for kw, sfx_file in SFX_KEYWORD_MAP.items():
        if kw in text_l:
            path = os.path.join("sfx", sfx_file)
            if os.path.exists(path):
                try:
                    sfx = AudioFileClip(path).volumex(0.60)
                    return CompositeAudioClip(
                        [audio_clip, sfx.subclip(0, min(sfx.duration, audio_clip.duration))]
                    )
                except Exception: pass
    return audio_clip


def add_stinger_sfx(audio_clip, text: str):
    """Adds a cinematic impact stinger 0.3s into the clip on key narrative beats."""
    text_l = text.lower()
    for kw, sfx_file in STINGER_MAP.items():
        if kw in text_l:
            path = os.path.join("sfx", sfx_file)
            if os.path.exists(path):
                print(f"🔊 SUCCESS: Applied SFX -> {path}")
                try:
                    stinger = (AudioFileClip(path)
                               .volumex(0.85)
                               .set_start(min(0.3, max(0.0, audio_clip.duration - 0.6))))
                    return CompositeAudioClip([audio_clip, stinger])
                except Exception: pass
    return audio_clip


# ═══════════════════════════════════════════════════════════
#  NETFLIX KARAOKE SUBTITLE SYSTEM
# ═══════════════════════════════════════════════════════════
def get_subtitle_font(size: int = 60):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return PIL.ImageFont.truetype(path, size)
            except Exception:
                continue
    return PIL.ImageFont.load_default()

def make_karaoke_frame(
    words: list[dict],
    active_idx: int,
    video_width: int
) -> PIL.Image.Image:
    """
    Renders a transparent (RGBA) PIL frame.
    FIXED: Dynamically shrinks font size to prevent overlapping, 
    and uses native stroke for crisp, readable text.
    """
    frame_h = 160
    img = PIL.Image.new("RGBA", (video_width, frame_h), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(img)

    # Base font sizes
    norm_size = 54
    act_size = 68

    fn_normal = get_subtitle_font(norm_size)
    fn_active = get_subtitle_font(act_size)

    def get_widths(f_norm, f_act):
        w_list = []
        for i, w in enumerate(words):
            fn = f_act if i == active_idx else f_norm
            bbox = draw.textbbox((0, 0), w["word"] + " ", font=fn)
            w_list.append(bbox[2] - bbox[0])
        return w_list

    widths = get_widths(fn_normal, fn_active)
    total_w = sum(widths)

    max_w = video_width - 40
    while total_w > max_w and norm_size > 24:
        norm_size -= 2
        act_size -= 2
        fn_normal = get_subtitle_font(norm_size)
        fn_active = get_subtitle_font(act_size)
        widths = get_widths(fn_normal, fn_active)
        total_w = sum(widths)

    x = (video_width - total_w) // 2

    for i, w in enumerate(words):
        is_active = (i == active_idx)
        fn = fn_active if is_active else fn_normal
        
        fill = (255, 230, 0, 255) if is_active else (255, 255, 255, 210)
        
        bbox = draw.textbbox((0, 0), w["word"], font=fn)
        text_h = bbox[3] - bbox[1]
        
        y = (frame_h - text_h) // 2 + (6 if not is_active else 0) 

        draw.text(
            (x, y), 
            w["word"], 
            font=fn, 
            fill=fill, 
            stroke_width=5 if is_active else 3, 
            stroke_fill=(0, 0, 0, 255)
        )
        
        x += widths[i]

    return img

def _pil_rgba_to_moviepy(pil_image: PIL.Image.Image, duration: float):
    """Converts a PIL RGBA image to a MoviePy clip with alpha mask."""
    rgb_arr   = np.array(pil_image.convert("RGB"))
    alpha_arr = np.array(pil_image.split()[3]).astype(float) / 255.0
    clip      = ImageClip(rgb_arr, duration=duration)
    mask      = ImageClip(alpha_arr, ismask=True, duration=duration)
    return clip.set_mask(mask)


def add_dynamic_subtitles(video_clip, audio_path: str):
    """
    Netflix-style karaoke subtitles with natural phrase breaks.
    """
    print("📝 Generating karaoke subtitles...")

    try:
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio_path, word_timestamps=True)

        all_words = []
        for seg in segments:
            if seg.words:
                for word in seg.words:
                    clean = word.word.strip().upper()
                    if clean:
                        all_words.append({
                            "word": clean,
                            "start": word.start,
                            "end": word.end,
                        })

        if not all_words:
            return video_clip

        duration = max(float(getattr(video_clip, "duration", 0.0) or 0.0), all_words[-1]["end"])
        words_per_second = len(all_words) / max(duration, 1.0)
        phrase_cap = 2 if words_per_second > 2.8 or duration < 60 else 3

        phrases = []
        current = []
        for word in all_words:
            if current:
                gap = word["start"] - current[-1]["end"]
                if gap > 0.42 or len(current) >= phrase_cap:
                    phrases.append(current)
                    current = []
            current.append(word)
        if current:
            phrases.append(current)

        sub_clips = []
        sub_y = int(video_clip.h * 0.67)

        for phrase_words in phrases:
            for active_idx, word_info in enumerate(phrase_words):
                dur = max(word_info["end"] - word_info["start"], 0.05)
                pil_frame = make_karaoke_frame(phrase_words, active_idx, VIDEO_WIDTH)
                word_clip = (
                    _pil_rgba_to_moviepy(pil_frame, dur)
                    .set_start(word_info["start"])
                    .set_position(("center", sub_y))
                )
                sub_clips.append(word_clip)

        if sub_clips:
            return CompositeVideoClip([video_clip] + sub_clips)
        return video_clip

    except Exception as e:
        print(f"⚠️  Karaoke subtitles failed ({e}) — using basic fallback...")
        try:
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(audio_path, word_timestamps=True)
            sub_clips = []
            for seg in segments:
                if seg.words:
                    for word in seg.words:
                        clean = word.word.strip().upper()
                        if not clean:
                            continue
                        try:
                            tc = (
                                TextClip(
                                    clean,
                                    fontsize=70,
                                    color="yellow",
                                    stroke_color="black",
                                    stroke_width=4,
                                    font="Impact",
                                    method="caption",
                                    size=(video_clip.w * 0.9, None),
                                )
                                .set_start(word.start)
                                .set_end(word.end)
                                .set_position(("center", video_clip.h * 0.70))
                            )
                            sub_clips.append(tc)
                        except Exception:
                            pass
            return CompositeVideoClip([video_clip] + sub_clips) if sub_clips else video_clip
        except Exception:
            return video_clip


# ═══════════════════════════════════════════════════════════
#  THUMBNAIL GENERATOR
# ═══════════════════════════════════════════════════════════
def generate_thumbnail(
    case_name: str,
    source_image_path: str,
    output_path: str = "thumbnail.jpg"
) -> str | None:
    print("🖼️  Generating YouTube Thumbnail...")
    try:
        with PIL.Image.open(source_image_path) as img:
            img       = img.convert("RGB").resize((1280, 720), PIL.Image.Resampling.LANCZOS)
            arr       = np.array(img, dtype=np.float32)
            arr       = np.clip(arr * 0.55 + 10, 0, 255).astype(np.uint8)
            arr[:,:,0] = np.clip(arr[:,:,0].astype(int) + 28, 0, 255)
            base      = PIL.Image.fromarray(arr)

        draw   = PIL.ImageDraw.Draw(base)
        title  = case_name.upper()
        if len(title) > 26:
            title = title[:26] + "…"

        fn_title  = get_subtitle_font(88)
        fn_badge  = get_subtitle_font(42)
        fn_handle = get_subtitle_font(38)

        draw.rectangle([(0, 570), (1280, 720)], fill=(170, 0, 0))
        draw.text((44, 594), CHANNEL_HANDLE, font=fn_handle, fill=(255, 255, 255))

        for dx, dy in [(-3,3),(3,3),(-3,-3),(3,-3),(0,4),(0,-4),(4,0),(-4,0)]:
            draw.text((40 + dx, 28 + dy), title, font=fn_title, fill=(0, 0, 0))
        draw.text((40, 28), title, font=fn_title, fill=(255, 230, 0))

        draw.rectangle([(40, 148), (272, 200)], fill=(170, 0, 0))
        draw.text((56, 153), "UNSOLVED", font=fn_badge, fill=(255, 255, 255))
        draw.text((40, 220), "TRUE STORY", font=get_subtitle_font(34), fill=(230, 230, 230))

        base.save(output_path, "JPEG", quality=95)
        print(f"✅ Thumbnail → {output_path}")
        return output_path
    except Exception as e:
        print(f"⚠️  Thumbnail failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════
#  END SCREEN 
# ═══════════════════════════════════════════════════════════
def add_end_screen(video_clip, question: str = "What really happened?"):
    print("🎬 Adding End Screen...")
    END_DUR = 2.5
    try:
        card = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0), duration=END_DUR)

        q_clip = (TextClip(question, fontsize=52, color="white", font="Impact",
                           stroke_color="#CC0000", stroke_width=2,
                           method="caption", size=(int(VIDEO_WIDTH * 0.85), None))
                  .set_position("center").set_duration(END_DUR).fx(fadein, 0.7))

        h_clip = (TextClip(CHANNEL_HANDLE, fontsize=30, color="#888888", font="Impact")
                  .set_position(("center", int(VIDEO_HEIGHT * 0.75)))
                  .set_duration(END_DUR).fx(fadein, 1.2))

        end = CompositeVideoClip([card, q_clip, h_clip])
        return concatenate_videoclips([video_clip, end], method="compose")
    except Exception as e:
        print(f"⚠️  End screen failed: {e}")
        return video_clip


# ═══════════════════════════════════════════════════════════
#  YOUTUBE UPLOAD
# ═══════════════════════════════════════════════════════════
def upload_to_youtube(
    file_path: str,
    yt_metadata: dict,
    thumbnail_path: str | None = None
) -> tuple[bool, str | None]:
    if not file_path:
        return False, None
    print("🚀 Uploading to YouTube...")
    try:
        creds   = Credentials.from_authorized_user_info(json.loads(YOUTUBE_TOKEN_VAL))
        youtube = build("youtube", "v3", credentials=creds)

        insert_rsp = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title":       yt_metadata["title"],
                    "description": yt_metadata["description"] + "\n\nWhat would be your first move? 👇",
                    "tags":        yt_metadata["tags"],
                    "categoryId":  "24",
                },
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
            },
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True),
        ).execute()

        video_id = insert_rsp.get("id")
        print(f"✅ YouTube upload success! ID: {video_id}")

        if thumbnail_path and video_id and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path)
                ).execute()
                print("✅ Custom thumbnail uploaded!")
            except Exception as e:
                print(f"⚠️  Thumbnail upload failed: {e}")

        return True, video_id
    except Exception as e:
        print(f"❌ YouTube upload failed: {e}")
        return False, None


# ═══════════════════════════════════════════════════════════
#  THE MARKETER
# ═══════════════════════════════════════════════════════════

def generate_youtube_metadata(
    script_text: str,
    sota_models: list[str],
    case_name: str = ""
) -> dict:
    sys = "You are an elite YouTube Shorts SEO Strategist. Output ONLY the exact data requested."

    title_pack = ask_llm(
        sys,
        f"""Write EXACTLY 3 different YouTube Shorts title candidates.
Rules:
- Each title must be under 50 characters.
- Each title must create a curiosity gap.
- Do NOT reveal the twist, ending, or full case name.
- Candidate 1 should be safest.
- Candidate 2 should be the sharpest curiosity hook.
- Candidate 3 should be the most emotionally charged.
- Separate the 3 titles with || only.
Script: {script_text}""",
        sota_models,
    )

    candidates = [t.strip().strip('"').strip("'") for t in title_pack.split("||")] if title_pack else []
    title = _pick_best_title(candidates, case_name=case_name) or "They found WHAT?"

    description = ask_llm(
        sys,
        f"""Write a 3-sentence YouTube Shorts description for title: '{title}'.
Requirements:
1. First sentence should deepen intrigue without giving away the answer.
2. Second sentence should reinforce the investigative / documentary tone.
3. Final sentence MUST be a provocative question.
No hashtags.""",
        sota_models,
    ) or "An unsolved mystery that will leave you speechless."

    tags_raw = ask_llm(
        sys,
        f"Title: '{title}'. Give exactly 10 highly-searched SEO tags, comma-separated. No hashtags.",
        sota_models,
    )
    tags = (
        [t.strip().replace("#", "") for t in tags_raw.split(",") if t.strip()]
        if tags_raw
        else [
            "mystery", "shorts", "creepy", "unsolved", "truecrime",
            "coldcase", "horror", "scary", "paranormal", "history"
        ]
    )

    return {
        "title": f"{title} #shorts #mystery",
        "description": description,
        "tags": tags,
    }


def generate_platform_captions(
    yt_metadata: dict,
    platform: str,
    sota_models: list[str]
) -> str:
    if platform == "Instagram":
        p = f"""Write a viral Instagram Reels caption.
Title: {yt_metadata['title']}
Description: {yt_metadata['description']}
REQUIREMENTS:
1. First line: aggressive scroll-stopping hook.
2. Tease the scariest detail — do NOT summarise.
3. End with a debate-driving Call-To-Action.
4. Exactly 6 trending true-crime/mystery hashtags."""
    else:
        p = f"""Write an engaging Facebook Reels caption.
Title: {yt_metadata['title']}
Description: {yt_metadata['description']}
REQUIREMENTS:
1. Conversational, slightly unnerving tone.
2. Open with a "What would you do if…" question.
3. Exactly 3 hashtags."""

    return (ask_llm(f"You are an elite {platform} Social Media Manager.", p, sota_models)
            or f"{yt_metadata['title']}\n\nWhat do you think happened? 👇\n\n#Mystery")


# ═══════════════════════════════════════════════════════════
#  MASTER ORCHESTRATION
# ═══════════════════════════════════════════════════════════
def main_pipeline() -> tuple:
    anti_ban_sleep()

    try:
        voice_engine = VoiceEngine()
    except Exception as e:
        print(f"❌ VoiceEngine init failed: {e}")
        return None, None, None, None, None

    sota_models = get_top_free_openrouter_models()

    fmt = random.choices(VIDEO_FORMATS, weights=[20, 60, 20], k=1)[0]
    print(f"📐 Format: {fmt['description']}")

    script = generate_viral_script(sota_models)
    if not script:
        return None, None, None, None, None

    if len(script.get("lines", [])) > fmt["max_lines"]:
        script["lines"] = script["lines"][:fmt["max_lines"]]

    script["format_label"] = fmt["label"]
    script["format_description"] = fmt["description"]
    script["retention_profile"] = script.get("retention_profile", {})

    era       = script.get("era", "unknown")
    case_name = script.get("case_name", "Unknown Case")
    base_voice = script.get("recommended_voice_model", "Charon")

    # ══ PHASE 2: MULTI-VOICE AUDIO ASSEMBLY ══
    audio_clips     = []
    stinger_clips   = []
    current_time    = 0.0
    full_script_txt = ""

    for i, line in enumerate(script["lines"]):
        clean_text  = line.get("clean_text",  "")
        acting_text = line.get("acting_text", clean_text)
        style       = line.get("style_instruction", "Measured, authoritative narrator")
        speaker     = line.get("speaker", "narrator")

        voice_name  = VOICE_MAP.get(speaker, base_voice)

        full_script_txt += clean_text + " "

        wav = voice_engine.generate_acting_line(acting_text, clean_text, style, i, voice_name)
        if wav:
            clip = AudioFileClip(wav)
            clip = add_sfx(clip, clean_text)
            
            # Map stingers to the absolute master timeline instead of the individual clip
            text_l = clean_text.lower()
            for kw, sfx_file in STINGER_MAP.items():
                if kw in text_l:
                    path = os.path.join("sfx", sfx_file)
                    if os.path.exists(path):
                        try:
                            # Start the stinger slightly before the end of the current clip
                            stinger_start = current_time + min(0.3, max(0.0, clip.duration - 0.6))
                            stinger = (AudioFileClip(path)
                                       .volumex(0.38)
                                       .set_start(stinger_start))
                            stinger_clips.append(stinger)
                        except Exception: pass
                    break # Only one stinger per line

            audio_clips.append(clip)
            current_time += clip.duration

    if not audio_clips:
        print("❌ No audio clips generated.")
        return None, None, None, None, None

    # 1. Concatenate the dialogue sequentially first without the 15-second reverb gaps
    master_voice = concatenate_audioclips(audio_clips)
    
    # 2. Composite the long reverb stingers OVER the master track so they bleed naturally underneath the next lines
    if stinger_clips:
        master_voice = CompositeAudioClip([master_voice] + stinger_clips)

    # ══ PHASE 3: VISUAL PIPELINE ══
    required_images  = max(1, int(master_voice.duration / IMAGE_TRANSITION_T))
    visual_dirs      = generate_cinematographer_prompts(
        full_script_txt, required_images, sota_models, era=era
    )
    dur_per_image    = master_voice.duration / len(visual_dirs)
    first_image_path = "temp_img_0.jpg"

    # CRITICAL FIX: Pass asset_type to ensure AI routing
    visual_clips = [
        get_image_clip(
            v.get("asset_type", "ai"),
            v.get("search_query", ""),
            v.get("ai_prompt", ""),
            dur_per_image, i
        )
        for i, v in enumerate(visual_dirs)
    ]

    try:
        final_video = (
            concatenate_videoclips(
                visual_clips, method="compose", padding=-CROSSFADE_DUR
            )
            .set_duration(master_voice.duration)
            .fx(colorx, 0.85)
        )

        if fetch_atmospheric_b_roll(master_voice.duration):
            try:
                atm = (VideoFileClip("temp_atmosphere.mp4").without_audio()
                       .fx(loop, duration=master_voice.duration)
                       .resize(height=VIDEO_HEIGHT))
                if atm.w < VIDEO_WIDTH:
                    atm = atm.resize(width=VIDEO_WIDTH)
                atm = (atm
                       .crop(x_center=atm.w/2, y_center=atm.h/2,
                             width=VIDEO_WIDTH, height=VIDEO_HEIGHT)
                       .set_opacity(0.22))
                final_video = CompositeVideoClip([final_video, atm])
            except Exception as e:
                print(f"⚠️  Atmospheric overlay: {e}")

        final_video = final_video.set_audio(master_voice)

    except Exception as e:
        print(f"❌ Video assembly failed: {e}")
        return None, None, None, None, None

    temp_voice_track = "temp_master_voice.wav"
    master_voice.write_audiofile(temp_voice_track, fps=24000, logger=None)
    final_video = add_dynamic_subtitles(final_video, temp_voice_track)

    try:
        wm = (TextClip(CHANNEL_HANDLE, fontsize=28, color="white",
                       font="Impact", stroke_color="black", stroke_width=1)
              .set_opacity(0.35)
              .set_position(("center", 140))
              .set_duration(final_video.duration))
        final_video = CompositeVideoClip([final_video, wm])
    except Exception: pass

    if fetch_pixabay_audio(full_script_txt, sota_models):
        try:
            bg = audio_loop(
                AudioFileClip("temp_bg_music.mp3").volumex(0.25),
                duration=final_video.duration
            )
            final_video = final_video.set_audio(
                CompositeAudioClip([final_video.audio, bg])
            )
        except Exception: pass

    last_line = (script["lines"][-1].get("clean_text", "")
                 if script["lines"] else "")
    end_q     = last_line if "?" in last_line else "What really happened?"
    final_video = add_end_screen(final_video, end_q)

    # ══ RENDER ══
    output_file = "final_video.mp4"
    try:
        final_video.write_videofile(
            output_file, codec="libx264", audio_codec="aac",
            fps=24, preset="fast", threads=2, logger=None
        )
    except Exception as e:
        print(f"❌ Render failed: {e}")
        return None, None, None, None, None

    thumbnail_path = None
    if os.path.exists(first_image_path):
        thumbnail_path = generate_thumbnail(case_name, first_image_path)

    try:
        for f in (glob.glob("temp_*.wav") + glob.glob("temp_*.jpg")
                  + glob.glob("temp_*.mp4") + glob.glob("temp_*.mp3")):
            if f != output_file:
                os.remove(f)
    except Exception: pass

    return output_file, script, full_script_txt, sota_models, thumbnail_path


# ═══════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    video_path, script_data, script_text, sota_models, thumbnail_path = main_pipeline()

    if video_path and script_data and sota_models:
        yt_metadata = generate_youtube_metadata(
            script_text, sota_models, case_name=script_data.get("case_name", "")
        )
        success, video_id = upload_to_youtube(video_path, yt_metadata, thumbnail_path)

        if success:
            record_run_memory({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "case_name": script_data.get("case_name", "Unknown Case"),
                "title": yt_metadata.get("title", ""),
                "format_label": script_data.get("format_label", ""),
                "era": script_data.get("era", ""),
                "video_id": video_id,
            })
            save_new_topic(script_data.get("case_name", "Unknown Case"))
            fb_caption = generate_platform_captions(yt_metadata, "Facebook",  sota_models)
            ig_caption = generate_platform_captions(yt_metadata, "Instagram", sota_models)
            meta_upload.upload_to_facebook(video_path, fb_caption)
            temp_url = meta_upload.get_temp_public_url(video_path)
            if temp_url:
                meta_upload.upload_to_instagram(temp_url, ig_caption)
    else:
        print("❌ Pipeline produced no output.")
