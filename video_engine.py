import os
import subprocess
import requests
import random
import math
from PIL import Image, ImageDraw, ImageFont
import numpy as np

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    VideoFileClip, AudioFileClip, ImageClip,
    concatenate_videoclips, CompositeVideoClip,
    CompositeAudioClip, concatenate_audioclips
)

# ─── Constants ────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1080, 1920
FPS = 30

# ─── FFmpeg ───────────────────────────────────────────────────────────────────
def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 'ffmpeg'

FFMPEG = _get_ffmpeg()

def _ffmpeg(*args):
    cmd = [FFMPEG] + list(args)
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"FFmpeg warning: {result.stderr.decode()[-300:]}")
    return result


# ─── Font ─────────────────────────────────────────────────────────────────────
# Drop Anton-Regular.ttf in assets/fonts/ — free from Google Fonts
FONT_PATHS = [
    "assets/fonts/Anton-Regular.ttf",
    "assets/fonts/Montserrat-ExtraBold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
]

def get_font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ─── Background: Pexels or Local Gameplay/Skeleton Folder ─────────────────────
def get_local_footage(folder):
    """Pick a random video from a local folder (gameplay/, skeleton/, etc.)"""
    if not os.path.exists(folder):
        return None
    clips = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.webm'))]
    if not clips:
        return None
    chosen = os.path.join(folder, random.choice(clips))
    print(f"Local footage: {chosen}")
    return chosen


def get_pexels_footage(topic, duration_needed, api_key):
    if not api_key:
        return None
    try:
        keywords = topic.split()[:3]
        search_terms = [' '.join(keywords[:2]), keywords[0], 'nature cinematic', 'abstract dark']
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


def create_gradient_bg_video(duration, topic, fps=FPS, output='bg.mp4'):
    """Cinematic dark gradient fallback — better than flat colors"""
    palettes = [
        ([15, 15, 30], [40, 10, 60]),    # deep space purple
        ([10, 20, 40], [5, 40, 80]),     # midnight blue
        ([30, 5, 5], [60, 15, 10]),      # dark red
        ([5, 25, 20], [10, 50, 40]),     # dark teal
        ([20, 10, 30], [50, 20, 60]),    # violet
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


# ─── Ken Burns Zoom ────────────────────────────────────────────────────────────
def apply_ken_burns(clip, zoom_start=1.0, zoom_end=1.06):
    """Slow cinematic zoom over clip duration — makes stock footage look intentional"""
    duration = clip.duration
    def zoom_frame(get_frame, t):
        frame = get_frame(t)
        progress = t / duration if duration > 0 else 0
        scale = zoom_start + (zoom_end - zoom_start) * progress
        h, w = frame.shape[:2]
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = Image.fromarray(frame)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        # Crop center
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        img = img.crop((left, top, left + w, top + h))
        return np.array(img)
    return clip.fl(zoom_frame, apply_to=['mask'])


# ─── Hook Frame (first 2.5s) ───────────────────────────────────────────────────
def build_hook_frame(hook_text, width=WIDTH):
    """Full-width semi-transparent dark bar with bold centered hook text"""
    bar_h = 340
    img = Image.new('RGBA', (width, bar_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark semi-transparent background
    overlay = Image.new('RGBA', (width, bar_h), (0, 0, 0, 210))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    font_large = get_font(88)
    font_small = get_font(58)

    # Word wrap
    words = hook_text.upper().split()
    lines, line = [], []
    for word in words:
        line.append(word)
        bbox = draw.textbbox((0, 0), ' '.join(line), font=font_large)
        if bbox[2] - bbox[0] > width - 100:
            if len(line) > 1:
                line.pop()
                lines.append(' '.join(line))
                line = [word]
            else:
                lines.append(' '.join(line))
                line = []
    if line:
        lines.append(' '.join(line))

    font = font_large if len(lines) <= 2 else font_small
    line_h = int((88 if len(lines) <= 2 else 58) * 1.3)
    total_h = len(lines) * line_h
    start_y = (bar_h - total_h) // 2

    cx = width // 2
    for i, ln in enumerate(lines):
        y = start_y + i * line_h
        # Cyan glow shadow
        for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
            draw.text((cx + dx, y + dy), ln, font=font, fill=(0, 255, 220, 120), anchor='mt')
        draw.text((cx, y), ln, font=font, fill=(255, 255, 255, 255), anchor='mt')

    return np.array(img)


# ─── Word-Highlight Captions ───────────────────────────────────────────────────
def build_word_highlight_caption(words_in_segment, active_index, width=WIDTH):
    """
    Renders a caption strip where the active word is on a bright pill
    and surrounding words are dimmed. Viral word-highlight style.
    """
    height = 200
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_font(82)

    ACTIVE_BG   = (0, 220, 180, 255)   # cyan pill
    ACTIVE_TEXT = (0, 0, 0, 255)       # black text on cyan
    DIM_TEXT    = (200, 200, 200, 180) # dimmed white for inactive

    # Measure total row width
    padding_x = 22
    padding_y = 12
    word_sizes = []
    for w in words_in_segment:
        bbox = draw.textbbox((0, 0), w, font=font)
        word_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))

    gap = 18
    total_w = sum(ws[0] + padding_x * 2 for ws in word_sizes) + gap * (len(words_in_segment) - 1)
    start_x = max((width - total_w) // 2, 20)
    cy = height // 2

    x = start_x
    for i, (word, (w_w, w_h)) in enumerate(zip(words_in_segment, word_sizes)):
        pill_w = w_w + padding_x * 2
        pill_h = w_h + padding_y * 2
        pill_top = cy - pill_h // 2
        pill_left = x
        pill_right = x + pill_w
        pill_bottom = pill_top + pill_h
        text_x = x + pill_w // 2
        text_y = cy

        if i == active_index:
            # Bright cyan pill
            draw.rounded_rectangle(
                [pill_left, pill_top, pill_right, pill_bottom],
                radius=16, fill=ACTIVE_BG
            )
            draw.text((text_x, text_y), word, font=font,
                      fill=ACTIVE_TEXT, anchor='mm')
        else:
            # Dark background pill for readability + dimmed text
            draw.rounded_rectangle(
                [pill_left, pill_top, pill_right, pill_bottom],
                radius=16, fill=(0, 0, 0, 100)
            )
            draw.text((text_x, text_y), word, font=font,
                      fill=DIM_TEXT, anchor='mm')

        x += pill_w + gap

    return np.array(img)


# ─── Main Assembly ─────────────────────────────────────────────────────────────
def assemble_video(topic, voice_path, word_timestamps, caption_segments,
                   output_path="short.mp4", pexels_key=None,
                   local_footage_folder=None, hook_text=None):

    voice = AudioFileClip(voice_path)
    total_dur = voice.duration + 1.0
    print(f"Total duration: {total_dur:.1f}s")

    # ── 1. Background ──────────────────────────────────────────────────────────
    footage_raw = None

    # Priority: local folder (skeleton/gameplay) > Pexels > gradient
    if local_footage_folder:
        footage_raw = get_local_footage(local_footage_folder)

    if not footage_raw and pexels_key:
        footage_raw = get_pexels_footage(topic, total_dur, pexels_key)

    if footage_raw:
        bg_path = 'bg_resized.mp4'
        resize_footage_ffmpeg(footage_raw, bg_path)
        # Clean up downloaded file only (not local folder clips)
        if not local_footage_folder or footage_raw not in [
            os.path.join(local_footage_folder, f) for f in os.listdir(local_footage_folder or '.')
        ]:
            try: os.remove(footage_raw)
            except: pass
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

    # ── 2. Ken Burns zoom ─────────────────────────────────────────────────────
    bg = apply_ken_burns(bg, zoom_start=1.0, zoom_end=1.06)

    # ── 3. Hook overlay (first 2.5s) ──────────────────────────────────────────
    overlay_clips = []
    if hook_text:
        hook_arr = build_hook_frame(hook_text)
        hook_clip = (
            ImageClip(hook_arr)
            .set_start(0)
            .set_end(min(2.5, total_dur))
            .set_position(('center', HEIGHT // 2 - hook_arr.shape[0] // 2))
        )
        overlay_clips.append(hook_clip)

    # ── 4. Word-highlight captions ────────────────────────────────────────────
    caption_clips = []

    if word_timestamps:
        # Build per-word clips for true word-highlight effect
        # Group into lines of max 3 words for readability
        WORDS_PER_LINE = 3
        words = word_timestamps
        i = 0
        while i < len(words):
            group = words[i:i + WORDS_PER_LINE]
            word_texts = [w['word'] for w in group]
            group_start = group[0]['start']
            group_end = group[-1]['start'] + group[-1]['duration']

            for active_idx, w in enumerate(group):
                word_start = w['start']
                word_end = w['start'] + w['duration']

                arr = build_word_highlight_caption(word_texts, active_idx)
                clip = (
                    ImageClip(arr)
                    .set_start(word_start)
                    .set_end(min(word_end + 0.05, total_dur))
                    .set_position(('center', HEIGHT - 380))
                )
                caption_clips.append(clip)
            i += WORDS_PER_LINE
    else:
        # Fallback: segment-based captions
        for seg in caption_segments:
            if not seg['text'].strip():
                continue
            words_in_seg = seg['text'].split()
            arr = build_word_highlight_caption(words_in_seg, 0)
            clip = (
                ImageClip(arr)
                .set_start(seg['start'])
                .set_end(min(seg['end'] + 0.05, total_dur))
                .set_position(('center', HEIGHT - 380))
            )
            caption_clips.append(clip)

    # ── 5. Compose ────────────────────────────────────────────────────────────
    all_clips = [bg] + overlay_clips + caption_clips
    final_video = CompositeVideoClip(all_clips, size=(WIDTH, HEIGHT))

    # ── 6. Audio ──────────────────────────────────────────────────────────────
    final_audio = voice
    music_folder = "music"
    if os.path.exists(music_folder):
        music_files = [f for f in os.listdir(music_folder) if f.endswith(('.mp3', '.wav'))]
        if music_files:
            try:
                music = AudioFileClip(
                    os.path.join(music_folder, random.choice(music_files))
                ).volumex(0.06)
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
        output_path, fps=FPS, codec='libx264',
        audio_codec='aac', logger=None,
        ffmpeg_params=["-crf", "20", "-preset", "fast"]
    )

    for f in ['bg_resized.mp4', 'bg.mp4', 'bg_frame.png']:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

    print(f"\n✅ Video ready: {output_path}")
    return output_path
