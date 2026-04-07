from dotenv import load_dotenv
load_dotenv()

import os
from trending_content import get_content
from voice_engine import generate_voice, words_to_caption_segments
from video_engine import assemble_video
from youtube_shorts_uploader import YouTubeShortsUploader


class ShortsGenerator:
    """
    Core video generator. Used by both CLI (app.py) and API (server.py).
    Supports three content types:
      - 'skeleton'  : anatomy facts, uses skeleton/ footage folder
      - 'trending'  : trending topics, uses Pexels
      - 'cinematic' : AI character scenes (Pollinations + Ken Burns)
    """

    def generate_video(self, content, output_path="short.mp4",
                       local_footage_folder=None):
        pexels_key = os.environ.get("PEXELS_API_KEY", "")
        content_type = content.get("content_type", "skeleton")
        bg_path = None

        # ── Cinematic mode: generate AI scene background ──────────────────────
        if content_type == "cinematic":
            character = content.get("character", "skeleton")
            print(f"\n[character] Generating cinematic scenes ({character})...")
            try:
                from character_engine import build_cinematic_background
                bg_path = build_cinematic_background(
                    script=content["script"],
                    character_key=character,
                    num_scenes=6,
                    clip_duration=4.0,
                    output_folder="scenes"
                )
            except Exception as e:
                print(f"Character engine error: {e} — falling back to skeleton folder")
                bg_path = None
            local_footage_folder = None  # bg_path takes over

        # ── Other modes: pick footage folder ─────────────────────────────────
        else:
            if local_footage_folder is None:
                if content_type == "skeleton" and os.path.exists("skeleton"):
                    clips = [f for f in os.listdir("skeleton") if f.endswith((".mp4",".mov"))]
                    if clips:
                        local_footage_folder = "skeleton"
                elif content_type == "challenge" and os.path.exists("gameplay"):
                    clips = [f for f in os.listdir("gameplay") if f.endswith((".mp4",".mov"))]
                    if clips:
                        local_footage_folder = "gameplay"

        # ── Voice ─────────────────────────────────────────────────────────────
        print("\n[voice] Generating voiceover...")
        voice_path = output_path.replace(".mp4", "_voice.mp3")
        word_timestamps = generate_voice(content["script"], voice_path)
        caption_segments = words_to_caption_segments(word_timestamps, words_per_caption=3)
        print(f"Captions: {len(caption_segments)} segments")

        # ── Video assembly ────────────────────────────────────────────────────
        print("\n[video] Assembling video...")
        try:
            final_path = assemble_video(
                topic=content["topic"],
                voice_path=voice_path,
                word_timestamps=word_timestamps,
                caption_segments=caption_segments,
                output_path=output_path,
                pexels_key=pexels_key,
                local_footage_folder=local_footage_folder,
                hook_text=content.get("hook"),
                prebuilt_bg=bg_path  # cinematic mode passes bg directly
            )
        finally:
            if os.path.exists(voice_path):
                os.remove(voice_path)

        return final_path if os.path.exists(final_path) else None


def cleanup_video_files(*paths):
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
                print(f"Cleaned: {p}")
            except Exception as e:
                print(f"Cleanup error: {e}")


def run_pipeline(auto_upload=False, output_path="short.mp4",
                 content_type="skeleton", character="skeleton"):
    """
    CLI entry point.
    Usage:
      python app.py skeleton
      python app.py trending
      python app.py cinematic skeletor
      python app.py cinematic socrates
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("ERROR: GROQ_API_KEY not set in .env")
        return None

    print(f"\n[1/3] Generating {content_type} content...")
    content = get_content(api_key, content_type=content_type)
    content["character"] = character
    print(f"Topic   : {content['topic']}")
    print(f"Title   : {content['title']}")
    print(f"Hook    : {content['hook']}")
    print(f"Script  : {content['script'][:80]}...")

    print("\n[2/3] Generating video...")
    generator = ShortsGenerator()
    final_path = generator.generate_video(content, output_path=output_path)

    if not final_path:
        print("❌ Video generation failed")
        return None

    print(f"\n[3/3] ✅ Done: {final_path}")

    if auto_upload:
        print("Uploading to YouTube...")
        uploader = YouTubeShortsUploader(
            client_secrets_file='client-secret.json',
            target_channel_id=os.environ.get("YOUTUBE_CHANNEL_ID", ""),
            api_key=api_key
        )
        video_id = uploader.upload_short(final_path, content)
        if video_id:
            url = f"https://youtube.com/shorts/{video_id}"
            print(f"Uploaded: {url}")
            cleanup_video_files(final_path)
            return url
    return final_path


if __name__ == "__main__":
    import sys
    # Usage: python app.py [content_type] [character]
    ctype     = sys.argv[1] if len(sys.argv) > 1 else "skeleton"
    character = sys.argv[2] if len(sys.argv) > 2 else "skeleton"
    print(f"Mode: {ctype} | Character: {character}")
    run_pipeline(content_type=ctype, character=character)
