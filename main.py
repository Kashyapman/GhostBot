def generate_viral_script():
    print("🧠 Generating HIGH RETENTION Script...")

    client = genai.Client(api_key=GEMINI_KEY)

    models_to_try = [
        "models/gemini-1.5-flash-latest",
        "models/gemini-1.5-pro-latest"
    ]

    niche = random.choice([
        "The Mirror That Blinked",
        "The Thing Under The Bed",
        "The Fake Human Next Door",
        "Unknown Caller at 3AM"
    ])

    prompt = f"""
You are a viral YouTube Shorts horror expert.

Topic: {niche}

Rules:
- First line MUST interrupt scrolling.
- Very short sentences.
- Escalate tension.
- End unresolved.
- 6-9 lines.
- Psychological horror only.

Return VALID JSON ONLY.
"""

    config = types.GenerateContentConfig(
        temperature=1.1,
        top_p=0.95,
        response_mime_type="application/json"
    )

    for model in models_to_try:
        try:
            print(f"Trying {model}")
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )

            if response.text:
                return json.loads(response.text)

        except Exception as e:
            print(f"Model error: {e}")
            continue

    print("⚠️ AI failed — using fallback")

    return {
        "title": "Don't Look Behind You #shorts",
        "description": "Something is standing there.",
        "tags": ["horror", "shorts"],
        "lines": [
            {"role": "narrator", "text": "Stop scrolling. Now.", "visual_keyword": "dark hallway portrait"},
            {"role": "victim", "text": "[gasps] I heard that.", "visual_keyword": "scared face closeup"},
            {"role": "demon", "text": "You shouldn't have looked.", "visual_keyword": "shadow figure portrait"}
        ]
    }
