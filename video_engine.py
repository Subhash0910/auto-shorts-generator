import os
import subprocess
import requests
import random
import math
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Patch moviepy ANTIALIAS before import
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    VideoFileClip, AudioFileClip, ImageClip,
    concatenate_videoclips, CompositeVideoClip,
    CompositeAudioClip, concatenate_audioclips
)

# Get FFmpeg binary from imageio-ffmpeg (bundled with moviepy)
# This avoids needing ffmpeg in system PATH
def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"FFmpeg: {path}")
        return path
    except Exception:
        return 'ffmpeg'  # fallback to PATH

FFMPEG = _get_ffmpeg()

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


def _ffmpeg(*args):
    """Run ffmpeg with the bundled binary"""
    cmd = [FFMPEG] + list(args)
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"FFmpeg warning: {result.stderr.decode()[-300:]}")
    return result


def get_pexels_footage(topic, duration_needed, api_key):
    if not api_key:
        print("No PEXELS_API_KEY, using gradient background")
        return None
    try:
        keywords = topic.split()[:3]
        search_terms = [' '.join(keywords[:2]), keywords[0], 'nature cinematic']
        for kw in search_terms:
            url = f"https://api.pexels.com/videos/search?query={kw}&per_page=15&orientation=portrait"
            r = requests.get(url, headers={'Authorization': api_key}, timeout=15)
            if r.status_code != 200:
                continue
            videos = r.json().get('videos', [])
            if not videos:
                continue
            suitable = [v for v in videos if v['duration'] >= duration_needed] or videos
            video = random.choice(suitable[:5])
            files = video.get('video_files', [])
            portrait = [f for f in files if f.get('width', 9999) <= 1080 and f.get('height', 0) > f.get('width', 0)]
            chosen = (portrait or sorted(files, key=lambda x: x.get('width', 0), reverse=True))[0]
            print("Downloading Pexels footage...")
            resp = requests.get(chosen['link'], timeout=60)
            footage_path = f"footage_{random.randint(1000,9999)}.mp4"
            with open(footage_path, 'wb') as f:
                f.write(resp.content)
            print(f"Footage ready: {footage_path}")
            return footage_path
    except Exception as e:
        print(f"Pexels error: {e}")
    return None


def resize_footage_ffmpeg(input_path, output_path, width=WIDTH, height=HEIGHT):
    _ffmpeg(
        '-y', '-i', input_path,
        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}',
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-an',
        output_path
    )
    return output_path


def create_gradient_bg_video(duration, topic, fps=24, output='bg.mp4'):
    palettes = [
        ([139, 92, 246], [37, 99, 235]),
        ([239, 68, 68], [234, 88, 12]),
        ([16, 185, 129], [6, 95, 70]),
        ([59, 130, 246], [124, 58, 237]),
        ([245, 158, 11], [239, 68, 68]),
        ([236, 72, 153], [139, 92, 246]),
    ]
    idx = abs(hash(topic)) % len(palettes)
    top, bot = [np.array(c) for c in palettes[idx]]
    gradient = np.linspace(0, 1, HEIGHT)
    frame = (gradient[:, None, None] * bot + (1 - gradient[:, None, None]) * top).astype(np.uint8)
    frame = np.repeat(frame, WIDTH, axis=1)
    img = Image.fromarray(frame, 'RGB')
    img_path = 'bg_frame.png'
    img.save(img_path)
    _ffmpeg(
        '-y', '-loop', '1', '-i', img_path,
        '-t', str(duration + 0.5),
        '-vf', f'fps={fps}',
        '-c:v', 'libx264', '-crf', '28', '-preset', 'fast',
        '-pix_fmt', 'yuv420p', '-an', output
    )
    if os.path.exists(img_path):
        os.remove(img_path)
    return output


def build_caption_frame(text, width=WIDTH, height=260, font_size=76):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_font(font_size)
    words = text.split()
    lines, line = [], []
    for word in words:
        line.append(word)
        bbox = draw.textbbox((0, 0), ' '.join(line), font=font)
        if bbox[2] - bbox[0] > width - 80:
            if len(line) > 1:
                line.pop()
                lines.append(' '.join(line))
                line = [word]
            else:
                lines.append(' '.join(line))
                line = []
    if line:
        lines.append(' '.join(line))
    line_h = int(font_size * 1.35)
    total_h = len(lines) * line_h
    start_y = (height - total_h) // 2
    cx = width // 2
    for i, ln in enumerate(lines):
        y = start_y + i * line_h
        for dx, dy in [(-4,0),(4,0),(0,-4),(0,4),(-3,-3),(3,-3),(-3,3),(3,3)]:
            draw.text((cx+dx, y+dy), ln, font=font, fill=(0,0,0,255), anchor='mt')
        draw.text((cx, y), ln, font=font, fill=(255,220,0,255), anchor='mt')
    return np.array(img)


def build_topic_label(topic, width=WIDTH):
    img = Image.new('RGBA', (width, 160), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_font(44)
    pill_w = min(len(topic) * 22 + 80, width - 40)
    cx = width // 2
    draw.rounded_rectangle([cx - pill_w//2, 20, cx + pill_w//2, 120],
                           radius=30, fill=(0, 0, 0, 150))
    # Truncate topic for label
    label = topic if len(topic) <= 40 else topic[:37] + '...'
    draw.text((cx, 65), label.upper(), font=font, fill=(255,255,255,255), anchor='mm')
    return np.array(img)


def assemble_video(topic, voice_path, word_timestamps, caption_segments,
                   output_path="short.mp4", pexels_key=None):
    voice = AudioFileClip(voice_path)
    total_dur = voice.duration + 1.0
    print(f"Duration: {total_dur:.1f}s")

    # Background
    footage_raw = get_pexels_footage(topic, total_dur, pexels_key)
    if footage_raw:
        bg_path = 'bg_resized.mp4'
        resize_footage_ffmpeg(footage_raw, bg_path)
        os.remove(footage_raw)
        if not os.path.exists(bg_path) or os.path.getsize(bg_path) < 1000:
            print("Footage resize failed, using gradient")
            bg_path = create_gradient_bg_video(total_dur, topic)
    else:
        bg_path = create_gradient_bg_video(total_dur, topic)

    bg = VideoFileClip(bg_path)
    if bg.duration < total_dur:
        loops = math.ceil(total_dur / bg.duration)
        bg = concatenate_videoclips([bg] * loops)
    bg = bg.subclip(0, total_dur).without_audio()

    # Caption clips
    caption_clips = []
    for seg in caption_segments:
        if not seg['text'].strip():
            continue
        arr = build_caption_frame(seg['text'])
        clip = (ImageClip(arr)
                .set_start(seg['start'])
                .set_end(min(seg['end'] + 0.05, total_dur))
                .set_position(('center', HEIGHT - 420)))
        caption_clips.append(clip)

    # Topic label
    label_clip = (ImageClip(build_topic_label(topic))
                  .set_duration(total_dur)
                  .set_position(('center', 50)))

    # Compose
    final_video = CompositeVideoClip([bg, label_clip] + caption_clips,
                                     size=(WIDTH, HEIGHT))

    # Audio
    final_audio = voice
    music_folder = "music"
    if os.path.exists(music_folder):
        music_files = [f for f in os.listdir(music_folder) if f.endswith(('.mp3', '.wav'))]
        if music_files:
            try:
                music = AudioFileClip(
                    os.path.join(music_folder, random.choice(music_files))
                ).volumex(0.07)
                if music.duration < total_dur:
                    music = concatenate_audioclips(
                        [music] * math.ceil(total_dur / music.duration)
                    )
                music = music.subclip(0, total_dur)
                final_audio = CompositeAudioClip([music, voice])
            except Exception as e:
                print(f"Music skip: {e}")

    final_video = final_video.set_audio(final_audio)

    print("Rendering final video...")
    final_video.write_videofile(
        output_path, fps=24, codec='libx264',
        audio_codec='aac', logger=None,
        ffmpeg_params=["-crf", "23", "-preset", "fast"]
    )

    for f in ['bg_resized.mp4', 'bg.mp4', 'bg_frame.png']:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

    print(f"\nVideo ready: {output_path}")
    return output_path
