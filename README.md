# 🦴 Auto Shorts Generator

Fully automated YouTube Shorts pipeline — trending topic discovery, Groq AI scripts, edge-tts voiceover, cinematic video assembly, auto-upload.

## Niches
| Mode | Description | Footage folder |
|------|-------------|----------------|
| `skeleton` | Shocking human body / anatomy facts | `skeleton/` |
| `challenge` | 30-day / list format viral Shorts | `gameplay/` |
| `trending` | Groq-scripted trending topic Shorts | Pexels API |

## Quick Start
```bash
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
python app.py skeleton
```

## Environment Variables
```
GROQ_API_KEY=       # required
PEXELS_API_KEY=     # optional (for trending mode)
YOUTUBE_CHANNEL_ID= # optional (for auto-upload)
```

## Footage Setup
- **Skeleton niche:** Drop 5-10 skeleton/anatomy `.mp4` clips into `skeleton/`
- **Challenge/gameplay niche:** Drop Minecraft/Subway Surfers clips into `gameplay/`
- **No footage:** Gradient background auto-generates as fallback

## Fonts
Download **Anton-Regular.ttf** from [Google Fonts](https://fonts.google.com/specimen/Anton) (free) and place it at `assets/fonts/Anton-Regular.ttf` for the best visual quality.

## Project Structure
```
auto-shorts-generator/
├── app.py                  # CLI orchestrator + ShortsGenerator class
├── server.py               # Flask API (used by frontend)
├── video_engine.py         # Video rendering — captions, Ken Burns, hook frame
├── voice_engine.py         # edge-tts voiceover + word timestamps
├── trending_content.py     # Groq script generation (3 content types)
├── trend_engine.py         # Google Trends + Reddit topic discovery
├── youtube_shorts_uploader.py  # YouTube Data API upload
├── skeleton/               # Drop skeleton footage clips here
├── gameplay/               # Drop gameplay footage clips here
├── music/                  # Drop background music (.mp3) here
├── assets/fonts/           # Drop Anton-Regular.ttf here
└── frontend/               # React dashboard
```

## Run as API Server
```bash
python server.py
# POST /api/generate  { "content_type": "skeleton", "auto_upload": false }
# GET  /api/status/<job_id>
# GET  /api/download/<job_id>
```
