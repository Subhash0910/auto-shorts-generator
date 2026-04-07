import os
import subprocess
import requests
import random
import math
import json
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy.editor import (
    VideoFileClip, AudioFileClip, ColorClip,
    concatenate_videoclips, CompositeVideoClip
)

FONT_PATHS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/arialbd.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]

WIDTH, HEIGHT = 1080, 1920


def get_font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def get_pexels_footage(topic, duration_needed, api_key):
    """Download Pexels video clip matching topic"""
    if not api_key:
        print("No PEXELS_API_KEY, skipping footage")
        return None
    try:
        # Try topic keywords, then generic fallback
        keywords = topic.split()[:3]
        for kw in [' '.join(keywords), keywords[0], 'nature']:
            url = f"https://api.pexels.com/videos/search?query={kw}&per_page=10&orientation=portrait"
            r = requests.get(url, headers={'Authorization': api_key}, timeout=15)
            if r.status_code != 200:
                continue
            videos = r.json().get('videos', [])
            # Filter by duration
            suitable = [v for v in videos if v['duration'] >= duration_needed]
            if not suitable:
                suitable = videos  # take any
            if suitable:
                video = random.choice(suitable[:5])
                # Get best quality portrait file
                files = sorted(video['video_files'],
                               key=lambda x: x.get('width', 0), reverse=True)
                portrait = [f for f in files if f.get('width', 0) <= 1080]
                chosen = portrait[0] if portrait else files[0]
                print(f"Downloading Pexels footage: {chosen['link'][:60]}...")
                resp = requests.get(chosen['link'], timeout=60)
                footage_path = f"footage_{random.randint(1000,9999)}.mp4"
                with open(footage_path, 'wb') as f:
                    f.write(resp.content)
                print(f"Footage downloaded: {footage_path}")
                return footage_path
    except Exception as e:
        print(f"Pexels error: {e}")
    return None


def create_gradient_bg_video(duration, topic, fps=24, output='bg.mp4'):
    """Fallback: animated gradient background"""
    palettes = [
        ([139, 92, 246], [37, 99, 235]),
        ([239, 68, 68], [234, 88, 12]),
        ([16, 185, 129], [6, 95, 70]),
        ([59, 130, 246], [124, 58, 237]),
        ([245, 158, 11], [239, 68, 68]),
        ([236, 72, 153], [139, 92, 246]),
    ]
    idx = abs(hash(topic)) % len(palettes)
    top, bot = palettes[idx]

    gradient = np.linspace(0, 1, HEIGHT)
    arr = (gradient[:, None, None] * np.array(bot) +
           (1 - gradient[:, None, None]) * np.array(top)).astype(np.uint8)
    frame = np.repeat(arr, WIDTH, axis=1)

    clip = ColorClip(size=(WIDTH, HEIGHT), color=top, duration=duration)

    def make_frame(t):
        return frame

    from moviepy.editor import VideoClip
    bg = VideoClip(make_frame, duration=duration)
    bg.write_videofile(output, fps=fps, codec='libx264',
                       audio=False, logger=None,
                       ffmpeg_params=["-crf", "28"])
    return output


def prepare_background(topic, duration, pexels_key):
    """Get Pexels footage or fallback gradient"""
    footage = get_pexels_footage(topic, duration, pexels_key)
    if footage:
        return footage, True
    print("Using gradient background fallback")
    bg = create_gradient_bg_video(duration, topic)
    return bg, False


def build_caption_frame(text, width=1080, height=300, font_size=72):
    """Build a single caption image (transparent PNG)"""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_font(font_size)

    # Word wrap
    words = text.split()
    lines, line = [], []
    for word in words:
        line.append(word)
        bbox = draw.textbbox((0, 0), ' '.join(line), font=font)
        if bbox[2] - bbox[0] > width - 60:
            if len(line) > 1:
                line.pop()
                lines.append(' '.join(line))
                line = [word]
            else:
                lines.append(' '.join(line))
                line = []
    if line:
        lines.append(' '.join(line))

    line_h = font_size * 1.4
    total_h = len(lines) * line_h
    start_y = (height - total_h) / 2

    for i, ln in enumerate(lines):
        y = start_y + i * line_h
        cx = width // 2
        # Black outline
        for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,-2),(-2,2),(2,2)]:
            draw.text((cx + dx, y + dy), ln, font=font,
                      fill=(0, 0, 0, 255), anchor='mt')
        # Yellow text
        draw.text((cx, y), ln, font=font, fill=(255, 220, 0, 255), anchor='mt')
    return img


def assemble_video(topic, voice_path, word_timestamps, caption_segments,
                   output_path="short.mp4", pexels_key=None):
    """Full assembly: background + captions + voice + music"""
    voice = AudioFileClip(voice_path)
    total_dur = voice.duration + 1.0

    print(f"Total duration: {total_dur:.1f}s")

    # --- Background ---
    bg_path, is_footage = prepare_background(topic, total_dur, pexels_key)
    bg = VideoFileClip(bg_path)

    # Loop or trim to match duration
    if bg.duration < total_dur:
        loops = math.ceil(total_dur / bg.duration)
        from moviepy.editor import concatenate_videoclips
        bg = concatenate_videoclips([bg] * loops)
    bg = bg.subclip(0, total_dur)

    # Resize to 1080x1920 portrait
    if is_footage:
        bg = bg.resize(height=HEIGHT)
        if bg.w < WIDTH:
            bg = bg.resize(width=WIDTH)
        x_center = (bg.w - WIDTH) // 2
        bg = bg.crop(x1=x_center, y1=0, x2=x_center + WIDTH, y2=HEIGHT)

    bg = bg.without_audio()

    # --- Caption overlay using FFmpeg directly ---
    # Build caption video with PIL frames
    from moviepy.editor import ImageClip, CompositeVideoClip
    caption_clips = []
    for seg in caption_segments:
        cap_img = build_caption_frame(seg['text'])
        cap_arr = np.array(cap_img)
        clip = (ImageClip(cap_arr, ismask=False)
                .set_start(seg['start'])
                .set_end(min(seg['end'] + 0.1, total_dur))
                .set_position(('center', HEIGHT - 380)))
        caption_clips.append(clip)

    # --- Topic label at top ---
    label_img = build_caption_frame(
        topic.upper(), width=1080, height=160, font_size=48
    )
    label_clip = (ImageClip(np.array(label_img), ismask=False)
                  .set_duration(total_dur)
                  .set_position(('center', 80)))

    # --- Compose ---
    all_clips = [bg, label_clip] + caption_clips
    final = CompositeVideoClip(all_clips, size=(WIDTH, HEIGHT))
    final = final.set_audio(voice)

    # --- Add background music if available ---
    music_folder = "music"
    if os.path.exists(music_folder):
        music_files = [f for f in os.listdir(music_folder)
                       if f.endswith(('.mp3', '.wav'))]
        if music_files:
            import random
            from moviepy.editor import CompositeAudioClip
            music_path = os.path.join(music_folder, random.choice(music_files))
            try:
                music = AudioFileClip(music_path).volumex(0.07)
                if music.duration < total_dur:
                    loops = math.ceil(total_dur / music.duration)
                    from moviepy.editor import concatenate_audioclips
                    music = concatenate_audioclips([music] * loops)
                music = music.subclip(0, total_dur)
                final = final.set_audio(CompositeAudioClip([music, voice]))
            except Exception as e:
                print(f"Music skip: {e}")

    print("Rendering final video...")
    final.write_videofile(
        output_path, fps=24, codec='libx264',
        audio_codec='aac', logger=None,
        ffmpeg_params=["-crf", "23", "-preset", "fast"]
    )

    # Cleanup temp files
    if os.path.exists(bg_path) and 'footage_' in bg_path:
        os.remove(bg_path)
    if os.path.exists('bg.mp4'):
        os.remove('bg.mp4')

    print(f"Video ready: {output_path}")
    return output_path
