from dotenv import load_dotenv
load_dotenv()

import os
from trend_engine import get_best_topic
from trending_content import get_content, generate_script, generate_title_and_tags
from voice_engine import generate_voice, words_to_caption_segments
from video_engine import assemble_video
from youtube_shorts_uploader import YouTubeShortsUploader


class ShortsGenerator:
    """Reusable generator class — used by both app.py CLI and server.py API"""

    def generate_video(self, content, output_path="short.mp4",
                       local_footage_folder=None):
        """
        Takes a content dict (topic, script, title, tags, hook, content_type)
        and produces the final .mp4. Returns output_path or None on failure.
        """
        pexels_key = os.environ.get("PEXELS_API_KEY", "")

        # Auto-select footage folder based on content type
        if local_footage_folder is None:
            content_type = content.get("content_type", "trending")
            if content_type == "skeleton" and os.path.exists("skeleton"):
                local_footage_folder = "skeleton"
            elif content_type == "challenge" and os.path.exists("gameplay"):
                local_footage_folder = "gameplay"

        print("\n[voice] Generating voiceover...")
        voice_path = output_path.replace(".mp4", "_voice.mp3")
        word_timestamps = generate_voice(content["script"], voice_path)
        caption_segments = words_to_caption_segments(word_timestamps, words_per_caption=3)
        print(f"Captions: {len(caption_segments)} segments")

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
                hook_text=content.get("hook")
            )
        finally:
            if os.path.exists(voice_path):
                os.remove(voice_path)

        return final_path if os.path.exists(final_path) else None


def cleanup_video_files(*paths):
    """Remove temp video files after upload"""
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
                print(f"Cleaned: {p}")
            except Exception as e:
                print(f"Cleanup error: {e}")


def run_pipeline(auto_upload=False, output_path="short.mp4",
                 content_type="skeleton"):
    """
    Full pipeline: trend → script → voice → video → (upload)
    content_type: 'skeleton' | 'trending' | 'challenge'
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("ERROR: GROQ_API_KEY not set in .env")
        return None

    # Step 1: Content
    print(f"\n[1/4] Generating {content_type} content...")
    content = get_content(api_key, content_type=content_type)
    print(f"Topic : {content['topic']}")
    print(f"Title : {content['title']}")
    print(f"Hook  : {content['hook']}")

    # Step 2: Video
    print("\n[2/4] Generating voice + assembling video...")
    generator = ShortsGenerator()
    final_path = generator.generate_video(content, output_path=output_path)

    if not final_path:
        print("Video generation failed")
        return None

    print(f"\n[3/4] Video saved: {final_path}")

    # Step 3: Upload (optional)
    if auto_upload:
        print("\n[4/4] Uploading to YouTube...")
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
        print("Upload failed")
        return None

    return final_path


if __name__ == "__main__":
    import sys
    ctype = sys.argv[1] if len(sys.argv) > 1 else "skeleton"
    print(f"Running pipeline — content type: {ctype}")
    result = run_pipeline(auto_upload=False, content_type=ctype)
    if result:
        upload = input("\nUpload to YouTube? (y/n): ").strip().lower()
        if upload == 'y':
            run_pipeline(auto_upload=True, content_type=ctype)
        else:
            print(f"Video saved: {result}")
