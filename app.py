from dotenv import load_dotenv
load_dotenv()

import os
from trend_engine import get_best_topic
from trending_content import generate_script, generate_title_and_tags
from voice_engine import generate_voice, words_to_caption_segments
from video_engine import assemble_video
from youtube_shorts_uploader import YouTubeShortsUploader


def run_pipeline(auto_upload=False, output_path="short.mp4"):
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("RIDDLE_API_KEY", "")
    pexels_key = os.environ.get("PEXELS_API_KEY", "")

    # Step 1: Trend discovery
    print("\n[1/5] Discovering trending topic...")
    topic = get_best_topic()
    print(f"Topic: {topic}")

    # Step 2: Script generation
    print("\n[2/5] Generating script...")
    script = generate_script(topic, api_key)
    if not script:
        print("Script generation failed")
        return None
    title, tags = generate_title_and_tags(topic, script, api_key)
    print(f"Title: {title}")
    content = {"topic": topic, "script": script, "title": title, "tags": tags}

    # Step 3: Voice generation
    print("\n[3/5] Generating voiceover (edge-tts)...")
    voice_path = "voice.mp3"
    word_timestamps = generate_voice(script, voice_path)
    caption_segments = words_to_caption_segments(word_timestamps, words_per_caption=4)
    print(f"Captions: {len(caption_segments)} segments")

    # Step 4: Video assembly
    print("\n[4/5] Assembling video...")
    final_path = assemble_video(
        topic=topic,
        voice_path=voice_path,
        word_timestamps=word_timestamps,
        caption_segments=caption_segments,
        output_path=output_path,
        pexels_key=pexels_key
    )

    if os.path.exists(voice_path):
        os.remove(voice_path)

    # Step 5: Upload
    if auto_upload and final_path:
        print("\n[5/5] Uploading to YouTube...")
        uploader = YouTubeShortsUploader(
            client_secrets_file='client-secret.json',
            target_channel_id=os.environ.get("YOUTUBE_CHANNEL_ID", ""),
            api_key=api_key
        )
        video_id = uploader.upload_short(final_path, content)
        if video_id:
            print(f"Uploaded: https://youtube.com/shorts/{video_id}")
        return video_id

    return final_path


if __name__ == "__main__":
    result = run_pipeline(auto_upload=False)
    if result and os.path.exists(result):
        upload = input("\nUpload to YouTube? (y/n): ").strip().lower()
        if upload == 'y':
            api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("RIDDLE_API_KEY", "")
            pexels_key = os.environ.get("PEXELS_API_KEY", "")
            from trending_content import generate_script, generate_title_and_tags
            # Re-read content from the run
            print("Upload skipped — run with auto_upload=True next time or use server.py")
        print(f"\nVideo saved: {result}")
