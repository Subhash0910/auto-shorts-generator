from dotenv import load_dotenv
load_dotenv()

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import imageio
import math
import os
import random
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips, CompositeAudioClip
from scipy.io import wavfile
from trending_content import get_content
from youtube_shorts_uploader import YouTubeShortsUploader


def cleanup_video_files(output_path):
    for f in [output_path, f"final_{output_path}"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


class ShortsGenerator:
    def __init__(self):
        self.width = 1080
        self.height = 1920
        self.fps = 24  # 24fps is fine for Shorts and uses less memory than 30
        self.font_bold = self._get_font()

    def _get_font(self):
        paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/msttcorefonts/arialbd.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        ]
        for p in paths:
            if os.path.exists(p):
                print(f"Using font: {p}")
                return p
        raise FileNotFoundError("No bold font found.")

    def _get_bg_colors(self, topic):
        palettes = [
            ([139, 92, 246], [37, 99, 235]),
            ([239, 68, 68], [234, 88, 12]),
            ([16, 185, 129], [6, 95, 70]),
            ([59, 130, 246], [124, 58, 237]),
            ([245, 158, 11], [239, 68, 68]),
            ([236, 72, 153], [139, 92, 246]),
        ]
        idx = abs(hash(topic)) % len(palettes)
        return palettes[idx]

    def _create_background(self, top_color, bottom_color):
        """Create RGB background directly — no RGBA to avoid memory bloat"""
        gradient = np.linspace(0, 1, self.height)
        top = np.array(top_color, dtype=np.float32)
        bot = np.array(bottom_color, dtype=np.float32)
        gradient = gradient[:, np.newaxis, np.newaxis]
        arr = (gradient * bot + (1 - gradient) * top).astype(np.uint8)
        bg = np.repeat(arr, self.width, axis=1)
        return Image.fromarray(bg, mode='RGB')

    def _draw_text(self, draw, text, x, y, font_size, color, max_width=None):
        # Strip alpha from color if present for RGB image
        if isinstance(color, tuple) and len(color) == 4:
            color = color[:3]
        font = ImageFont.truetype(self.font_bold, font_size)
        max_w = max_width or (self.width - 80)
        words = text.split()
        lines = []
        current = []
        for word in words:
            current.append(word)
            bbox = draw.textbbox((0, 0), ' '.join(current), font=font)
            if bbox[2] - bbox[0] > max_w:
                if len(current) > 1:
                    current.pop()
                    lines.append(' '.join(current))
                    current = [word]
                else:
                    lines.append(' '.join(current))
                    current = []
        if current:
            lines.append(' '.join(current))
        line_h = font_size * 1.3
        start_y = y - (len(lines) * line_h) / 2
        for i, line in enumerate(lines):
            ly = start_y + i * line_h
            draw.text((x + 3, ly + 3), line, font=font, fill=(0, 0, 0), anchor="mm")
            draw.text((x, ly), line, font=font, fill=color, anchor="mm")

    def _create_frame(self, bg, topic, caption_lines, current_line_idx):
        """Create RGB frame — no RGBA mode, no alpha, no memory issues"""
        frame = bg.copy()  # RGB copy
        draw = ImageDraw.Draw(frame)  # plain RGB draw
        cx = self.width // 2

        # Top badge
        draw.rectangle([cx - 200, 70, cx + 200, 130], fill=(255, 255, 255, ))
        self._draw_text(draw, "TRENDING NOW", cx, 100, 30, (50, 50, 50))

        # Topic title
        self._draw_text(draw, topic.upper(), cx, 220, 54, (255, 255, 255))

        # Divider
        draw.line([(cx - 180, 275), (cx + 180, 275)], fill=(255, 255, 255), width=2)

        # Caption lines
        start_y = 650
        line_spacing = 155
        for i, line in enumerate(caption_lines):
            if i > current_line_idx:
                break
            if i == current_line_idx:
                color = (255, 220, 0)   # yellow = current line
                font_size = 70
            else:
                color = (220, 220, 220)  # light grey = done lines
                font_size = 56
            y_pos = start_y + i * line_spacing
            self._draw_text(draw, line, cx, y_pos, font_size, color)

        # CTA bottom
        self._draw_text(draw, "Follow for more!", cx, 1840, 44, (255, 220, 0))

        return np.array(frame)  # RGB numpy array — clean

    def _create_silence(self, duration, path="silence.wav"):
        rate = 44100
        data = np.zeros(int(duration * rate), dtype=np.int16)
        wavfile.write(path, rate, data)
        return path

    def _get_music(self):
        folder = "music"
        if not os.path.exists(folder):
            return None
        files = [f for f in os.listdir(folder) if f.endswith(('.mp3', '.wav'))]
        return os.path.join(folder, random.choice(files)) if files else None

    def generate_video(self, content, output_path="short.mp4"):
        topic = content["topic"]
        script = content["script"]
        cleanup_video_files(output_path)

        # Split into caption lines
        words = script.split()
        caption_lines, chunk = [], []
        for w in words:
            chunk.append(w)
            if len(chunk) >= 7 or w.endswith(('.', '!', '?')):
                caption_lines.append(' '.join(chunk))
                chunk = []
        if chunk:
            caption_lines.append(' '.join(chunk))
        caption_lines = caption_lines[:8]

        top_c, bot_c = self._get_bg_colors(topic)
        bg = self._create_background(top_c, bot_c)

        print("Generating TTS audio...")
        tts = gTTS(text=script, lang='en', slow=False)
        voice_path = "voice.mp3"
        tts.save(voice_path)
        voice_clip = AudioFileClip(voice_path)
        total_dur = voice_clip.duration + 1.5

        print(f"Rendering {total_dur:.1f}s @ {self.fps}fps with {len(caption_lines)} caption lines...")
        writer = imageio.get_writer(
            output_path, fps=self.fps,
            codec='libx264', quality=8,
            pixelformat='yuv420p', macro_block_size=None
        )

        frames_total = int(total_dur * self.fps)
        time_per_line = voice_clip.duration / max(len(caption_lines), 1)

        for frame_i in range(frames_total):
            t = frame_i / self.fps
            line_idx = min(int(t / time_per_line), len(caption_lines) - 1)
            frame = self._create_frame(bg, topic, caption_lines, line_idx)
            writer.append_data(frame)

        writer.close()

        music_path = self._get_music()
        if music_path:
            try:
                bg_music = AudioFileClip(music_path).volumex(0.06)
                if bg_music.duration < total_dur:
                    loops = math.ceil(total_dur / bg_music.duration)
                    bg_music = concatenate_audioclips([bg_music] * loops)
                bg_music = bg_music.subclip(0, total_dur)
                final_audio = CompositeAudioClip([bg_music, voice_clip])
            except Exception as e:
                print(f"Music error: {e}")
                final_audio = voice_clip
        else:
            final_audio = voice_clip

        video = VideoFileClip(output_path)
        final = video.set_audio(final_audio)
        final_path = f"final_{output_path}"
        final.write_videofile(final_path, codec='libx264', audio_codec='aac', logger=None)

        video.close()
        voice_clip.close()
        if os.path.exists(voice_path):
            os.remove(voice_path)
        if os.path.exists("silence.wav"):
            os.remove("silence.wav")

        print(f"Video ready: {final_path}")
        return final_path


if __name__ == "__main__":
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("RIDDLE_API_KEY", "")
    print("Fetching trending topic...")
    content = get_content(api_key)
    print(f"Topic  : {content['topic']}")
    print(f"Title  : {content['title']}")
    print(f"Script : {content['script'][:100]}...")

    generator = ShortsGenerator()
    final_path = generator.generate_video(content)

    if final_path and os.path.exists(final_path):
        upload = input("Upload to YouTube? (y/n): ").strip().lower()
        if upload == 'y':
            uploader = YouTubeShortsUploader(
                client_secrets_file='client-secret.json',
                target_channel_id=os.environ.get("YOUTUBE_CHANNEL_ID", ""),
                api_key=api_key
            )
            video_id = uploader.upload_short(final_path, content)
            if video_id:
                print(f"Uploaded: https://youtube.com/shorts/{video_id}")
                cleanup_video_files("short.mp4")
            else:
                print("Upload failed.")
        else:
            print(f"Saved at: {final_path}")
    else:
        print("Video generation failed.")
