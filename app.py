from dotenv import load_dotenv
load_dotenv()

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import imageio
import math
import time
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
            except Exception as e:
                print(f"Error deleting {f}: {e}")


class ShortsGenerator:
    def __init__(self):
        self.width = 1080
        self.height = 1920
        self.fps = 30
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
        raise FileNotFoundError("No bold font found on this system.")

    def _get_bg_colors(self, topic):
        """Dynamic gradient based on topic hash so each video looks different"""
        palettes = [
            ([139, 92, 246], [37, 99, 235]),    # purple → blue
            ([239, 68, 68], [234, 88, 12]),      # red → orange
            ([16, 185, 129], [6, 95, 70]),       # green → dark green
            ([59, 130, 246], [124, 58, 237]),    # blue → violet
            ([245, 158, 11], [239, 68, 68]),     # amber → red
            ([236, 72, 153], [139, 92, 246]),    # pink → purple
        ]
        idx = hash(topic) % len(palettes)
        return palettes[idx]

    def _create_background(self, top_color, bottom_color):
        gradient = np.linspace(0, 1, self.height)
        top = np.array(top_color)
        bot = np.array(bottom_color)
        gradient = gradient[:, np.newaxis, np.newaxis]
        arr = (gradient * bot + (1 - gradient) * top).astype(np.uint8)
        return Image.fromarray(np.repeat(arr, self.width, axis=1))

    def _draw_text(self, draw, text, x, y, font_size, color, max_width=None):
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
            # shadow
            draw.text((x + 3, ly + 3), line, font=font, fill=(0, 0, 0, 130), anchor="mm")
            # main text
            draw.text((x, ly), line, font=font, fill=color, anchor="mm")

    def _draw_pill(self, draw, x, y, w, h, color):
        """Draw a rounded rectangle pill shape"""
        r = h // 2
        draw.ellipse([x, y, x + h, y + h], fill=color)
        draw.ellipse([x + w - h, y, x + w, y + h], fill=color)
        draw.rectangle([x + r, y, x + w - r, y + h], fill=color)

    def _create_frame(self, bg, topic, caption_lines, current_line_idx, progress=1.0):
        frame = bg.copy()
        draw = ImageDraw.Draw(frame, 'RGBA')
        cx = self.width // 2

        # Top label pill
        pill_w, pill_h = 400, 60
        pill_x = cx - pill_w // 2
        self._draw_pill(draw, pill_x, 80, pill_w, pill_h, (255, 255, 255, 40))
        self._draw_text(draw, "TRENDING NOW", cx, 110, 28, (255, 255, 255, 220))

        # Topic title
        self._draw_text(draw, topic.upper(), cx, 230, 52, (255, 255, 255, 255))

        # Divider line
        draw.line([(cx - 200, 290), (cx + 200, 290)], fill=(255, 255, 255, 80), width=2)

        # Caption lines - show completed lines + current animating line
        start_y = 700
        line_spacing = 160
        for i, line in enumerate(caption_lines):
            if i > current_line_idx:
                break
            alpha = 255 if i < current_line_idx else int(255 * progress)
            color = (255, 220, 0, alpha) if i == current_line_idx else (255, 255, 255, 200)
            font_size = 68 if i == current_line_idx else 58
            y = start_y + i * line_spacing
            self._draw_text(draw, line, cx, y, font_size, color)

        # Bottom CTA
        self._draw_text(draw, "Follow for more! 🔥", cx, 1820, 42, (255, 220, 0, 255))

        return np.array(frame.convert('RGB'))

    def _create_silence(self, duration, path="silence.wav"):
        rate = 44100
        data = np.zeros(int(duration * rate)).astype(np.int16)
        wavfile.write(path, rate, data)
        return path

    def _get_music(self):
        folder = "music"
        if not os.path.exists(folder):
            return None
        files = [f for f in os.listdir(folder) if f.endswith(('.mp3', '.wav'))]
        return os.path.join(folder, random.choice(files)) if files else None

    def generate_video(self, content, output_path):
        topic = content["topic"]
        script = content["script"]
        cleanup_video_files(output_path)

        # Split script into caption lines (max 7 words per line)
        words = script.split()
        caption_lines = []
        chunk = []
        for w in words:
            chunk.append(w)
            if len(chunk) >= 7 or w.endswith(('.', '!', '?')):
                caption_lines.append(' '.join(chunk))
                chunk = []
        if chunk:
            caption_lines.append(' '.join(chunk))
        caption_lines = caption_lines[:8]  # max 8 lines for screen space

        top_c, bot_c = self._get_bg_colors(topic)
        bg = self._create_background(top_c, bot_c)

        print(f"Generating TTS audio...")
        tts = gTTS(text=script, lang='en', slow=False)
        voice_path = "voice.mp3"
        tts.save(voice_path)
        voice_clip = AudioFileClip(voice_path)
        total_dur = voice_clip.duration + 1.5  # +1.5s ending hold

        silence_path = self._create_silence(total_dur + 2)
        silence = AudioFileClip(silence_path)

        print(f"Rendering {total_dur:.1f}s video with {len(caption_lines)} caption lines...")
        writer = imageio.get_writer(output_path, fps=self.fps, codec='h264',
                                    quality=9, pixelformat='yuv420p', macro_block_size=8)

        frames_total = int(total_dur * self.fps)
        time_per_line = voice_clip.duration / max(len(caption_lines), 1)

        for frame_i in range(frames_total):
            t = frame_i / self.fps
            line_idx = min(int(t / time_per_line), len(caption_lines) - 1)
            line_progress = (t % time_per_line) / time_per_line
            frame = self._create_frame(bg, topic, caption_lines, line_idx, line_progress)
            writer.append_data(frame)

        writer.close()

        # Mix voice + background music
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
                print(f"Music error: {e}, using voice only")
                final_audio = voice_clip
        else:
            final_audio = voice_clip

        video = VideoFileClip(output_path)
        final = video.set_audio(final_audio)
        final_path = f"final_{output_path}"
        final.write_videofile(final_path, codec='libx264', audio_codec='aac', logger=None)

        video.close()
        voice_clip.close()
        final_audio.close()
        if os.path.exists(voice_path):
            os.remove(voice_path)
        if os.path.exists(silence_path):
            os.remove(silence_path)

        print(f"✅ Video saved: {final_path}")
        return final_path


if __name__ == "__main__":
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("RIDDLE_API_KEY", "")

    print("🔍 Fetching trending topic + generating script...")
    content = get_content(api_key)

    print(f"\n📌 Topic   : {content['topic']}")
    print(f"📝 Title   : {content['title']}")
    print(f"🏷  Tags    : {', '.join(content['tags'][:5])}")
    print(f"📜 Script  : {content['script'][:120]}...\n")

    generator = ShortsGenerator()
    output = "short.mp4"

    print("🎬 Generating video...")
    final_path = generator.generate_video(content, output)

    if final_path and os.path.exists(final_path):
        upload = input("\n✅ Video ready! Upload to YouTube? (y/n): ").strip().lower()
        if upload == 'y':
            uploader = YouTubeShortsUploader(
                client_secrets_file='client-secret.json',
                target_channel_id=os.environ.get("YOUTUBE_CHANNEL_ID", ""),
                api_key=api_key
            )
            video_id = uploader.upload_short(final_path, content)
            if video_id:
                print(f"🚀 Uploaded! https://youtube.com/shorts/{video_id}")
                cleanup_video_files(output)
            else:
                print("❌ Upload failed.")
        else:
            print(f"Video saved at: {final_path}")
    else:
        print("❌ Video generation failed.")
