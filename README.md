# 🦴 Auto Shorts Generator

Fully automated YouTube Shorts pipeline — trending topic discovery, Groq AI scripts, edge-tts voiceover, cinematic video assembly, auto-upload.

## Modes
| Command | Mode | Background |
|---------|------|------------|
| `python app.py skeleton` | Anatomy facts | `skeleton/` folder |
| `python app.py trending` | Trending topics | Pexels API |
| `python app.py challenge` | 30-day list format | `gameplay/` folder |
| `python app.py cinematic skeleton` | AI scenes + Ken Burns | Pollinations AI |
| `python app.py cinematic skeletor` | Skeletor progression | Pollinations AI |
| `python app.py cinematic socrates` | Socrates funny situations | Pollinations AI |
| `python app.py cinematic chad` | Chad transformation | Pollinations AI |

## Quick Start
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in GROQ_API_KEY at minimum
python app.py skeleton
```

## Environment Variables
```
GROQ_API_KEY=        # required for all modes
PEXELS_API_KEY=      # optional, only for 'trending' mode
YOUTUBE_CHANNEL_ID=  # optional, only for auto-upload
```

## Footage Setup (optional — improves quality)
- `skeleton/` — drop anatomy/skeleton `.mp4` clips here
- `gameplay/` — drop Minecraft/Subway Surfers clips here
- `music/`    — drop background music `.mp3` files here
- `assets/fonts/Anton-Regular.ttf` — download free from [Google Fonts](https://fonts.google.com/specimen/Anton)

## How Cinematic Mode Works
1. Groq generates a scene-by-scene visual description from the script
2. Pollinations AI (free, no API key) generates one image per scene
3. Ken Burns zoom animates each image into a clip
4. Clips are concatenated as the video background
5. Voice + word-highlight captions + music assembled on top

**Upgrade path:** Replace Pollinations + Ken Burns with Kling AI API (~$10/mo)
for real cinematic motion when you're ready to scale.

## Project Structure
```
auto-shorts-generator/
├── app.py                   # CLI + ShortsGenerator class
├── server.py                # Flask API
├── video_engine.py          # Rendering: captions, Ken Burns, hook frame
├── voice_engine.py          # edge-tts voiceover + word timestamps
├── character_engine.py      # Pollinations images + Ken Burns animation
├── trending_content.py      # Groq scripts (3 content types)
├── trend_engine.py          # Google Trends + Reddit topic discovery
├── youtube_shorts_uploader.py
├── skeleton/                # Drop skeleton footage here
├── gameplay/                # Drop gameplay footage here
├── scenes/                  # Auto-generated scene images + clips
├── music/                   # Background music
└── assets/fonts/            # Anton-Regular.ttf
```
