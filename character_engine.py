import os
import time
import random
import requests
from PIL import Image
from io import BytesIO

# ─── Character Presets ───────────────────────────────────────────────────────
# Add more characters here. Each has a base_prompt that stays consistent
# across all scenes to keep the character recognizable.
CHARACTERS = {
    "skeletor": {
        "base": "Skeletor from He-Man, blue skull face, purple hood, evil grin, cartoon style, vibrant colors, cinematic lighting",
        "style": "cartoon villain style, bold colors, dramatic shadows"
    },
    "socrates": {
        "base": "Socrates the ancient Greek philosopher, white robe, white beard, bald, wise expression, realistic illustration",
        "style": "classical painting style, warm tones, dramatic lighting"
    },
    "skeleton": {
        "base": "a realistic 3D human skeleton, clean white bones, dark dramatic background, cinematic",
        "style": "hyper-realistic 3D render, cinematic lighting, dark background"
    },
    "chad": {
        "base": "a buff cartoon chad character, square jaw, confident smirk, gym outfit",
        "style": "bold cartoon style, high contrast, vivid colors"
    }
}

# Day labels used in progression videos
DAY_LABELS = [
    "Day 1", "Day 5", "Day 10", "Day 15", "Day 20", "Day 25", "Day 30"
]


# ─── Pollinations AI Image Generator ─────────────────────────────────────────
# No API key. No signup. Pure HTTP GET. Returns a PIL Image.
def generate_image_pollinations(prompt, width=1080, height=1920,
                                 model="flux", retries=3):
    """
    Calls Pollinations AI free image endpoint.
    Returns PIL Image or None on failure.
    """
    # Encode prompt for URL
    from urllib.parse import quote
    encoded = quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model={model}&nologo=true"

    for attempt in range(retries):
        try:
            print(f"  Pollinations [{attempt+1}]: {prompt[:60]}...")
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) > 5000:
                img = Image.open(BytesIO(r.content)).convert("RGB")
                print(f"  ✅ Image generated ({img.size})")
                return img
            print(f"  ⚠️ Bad response: {r.status_code}, retrying...")
        except Exception as e:
            print(f"  ⚠️ Attempt {attempt+1} failed: {e}")
        time.sleep(2)
    return None


def save_image(img, path):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    img.save(path, "PNG")
    return path


# ─── Scene Prompt Builder ─────────────────────────────────────────────────────
def build_scene_prompts(character_key, scenes):
    """
    Given a character key and a list of scene descriptions,
    returns a list of full prompts for Pollinations.

    scenes: list of strings like ["sitting on a couch being lazy",
                                   "at the gym struggling to lift"]
    """
    char = CHARACTERS.get(character_key, CHARACTERS["skeleton"])
    prompts = []
    for scene in scenes:
        prompt = f"{char['base']}, {scene}, {char['style']}, 9:16 vertical portrait, high quality"
        prompts.append(prompt)
    return prompts


# ─── Main Character Scene Generator ──────────────────────────────────────────
def generate_character_scenes(character_key, scenes, output_folder="scenes"):
    """
    Generates one image per scene using Pollinations AI.
    Saves to output_folder/scene_0.png, scene_1.png, etc.
    Returns list of image file paths.

    character_key : 'skeletor' | 'socrates' | 'skeleton' | 'chad'
    scenes        : list of scene descriptions (strings)
    """
    os.makedirs(output_folder, exist_ok=True)
    prompts = build_scene_prompts(character_key, scenes)
    paths = []

    for i, prompt in enumerate(prompts):
        out_path = os.path.join(output_folder, f"scene_{i:02d}.png")

        # Skip if already exists (re-run safe)
        if os.path.exists(out_path):
            print(f"  Scene {i} exists, skipping")
            paths.append(out_path)
            continue

        img = generate_image_pollinations(prompt)
        if img:
            save_image(img, out_path)
            paths.append(out_path)
        else:
            print(f"  ❌ Scene {i} failed — using placeholder")
            # Create a dark placeholder so pipeline doesn't break
            placeholder = Image.new("RGB", (1080, 1920), color=(10, 10, 20))
            save_image(placeholder, out_path)
            paths.append(out_path)

        # Small delay to be polite to the free API
        time.sleep(1.5)

    print(f"\n✅ {len(paths)} scenes ready in '{output_folder}/'")
    return paths


# ─── Scene Descriptions from Script ──────────────────────────────────────────
def extract_scenes_from_script(script, character_key, num_scenes=6):
    """
    Uses Groq to extract cinematic scene descriptions from the script.
    Returns list of scene description strings.
    """
    from groq import Groq
    import json

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return _fallback_scenes(character_key, num_scenes)

    char = CHARACTERS.get(character_key, CHARACTERS["skeleton"])
    client = Groq(api_key=api_key)

    prompt = f"""You are a visual director for YouTube Shorts.

Script:
\"\"\"{script}\"\"\"

Character: {char['base']}

Generate EXACTLY {num_scenes} short visual scene descriptions for this character to illustrate the script.
Each scene = one image. Keep scenes simple, visual, and match the script's progression.

Return ONLY a JSON array of {num_scenes} strings. Example:
["standing at starting line looking nervous", "running slowly, struggling", "collapsed on ground tired"]

Return ONLY the JSON array, nothing else."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        text = response.choices[0].message.content.strip()
        # Strip markdown if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        scenes = json.loads(text)
        if isinstance(scenes, list) and len(scenes) > 0:
            print(f"✅ Groq generated {len(scenes)} scene descriptions")
            return scenes[:num_scenes]
    except Exception as e:
        print(f"Scene extraction error: {e}")

    return _fallback_scenes(character_key, num_scenes)


def _fallback_scenes(character_key, num_scenes):
    """Hardcoded fallback scenes per character"""
    fallbacks = {
        "skeletor": [
            "sitting lazily on evil throne looking bored",
            "attempting to do push-ups badly",
            "lifting tiny dumbbells looking confused",
            "sweating at a gym machine struggling",
            "flexing proudly in mirror with muscles",
            "standing triumphantly on mountaintop arms raised"
        ],
        "socrates": [
            "sitting under olive tree looking thoughtful",
            "confused staring at a modern smartphone",
            "arguing passionately with students in agora",
            "writing on ancient scroll with quill",
            "standing at podium delivering speech",
            "raising finger with enlightened expression"
        ],
        "skeleton": [
            "standing upright in dramatic dark background",
            "pointing at chest with glowing heart",
            "running dynamically cinematic motion blur",
            "flexing arm showing bone structure",
            "holding glowing brain in outstretched hand",
            "triumphant pose arms raised in light"
        ],
        "chad": [
            "slouching on couch eating chips",
            "struggling at gym with light weights",
            "sweating but pushing harder",
            "visible muscle definition emerging",
            "confident stride out of gym",
            "flexing massive muscles triumphant"
        ]
    }
    scenes = fallbacks.get(character_key, fallbacks["skeleton"])
    return (scenes * 3)[:num_scenes]


# ─── Image → Video Clip (Ken Burns) ──────────────────────────────────────────
def image_to_clip(image_path, duration=4.0, zoom_direction="in"):
    """
    Converts a still image to a Ken Burns animated video clip.
    zoom_direction: 'in' (zoom in) or 'out' (zoom out)
    Returns path to the generated .mp4 clip.
    """
    from moviepy.editor import ImageClip
    import numpy as np
    from PIL import Image as PILImage

    output_path = image_path.replace(".png", ".mp4").replace(".jpg", ".mp4")

    img = PILImage.open(image_path).convert("RGB")
    img_array = np.array(img)
    h, w = img_array.shape[:2]

    zoom_start = 1.0 if zoom_direction == "in" else 1.08
    zoom_end   = 1.08 if zoom_direction == "in" else 1.0

    def make_frame(t):
        progress = t / duration
        scale = zoom_start + (zoom_end - zoom_start) * progress
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = PILImage.fromarray(img_array).resize((new_w, new_h), PILImage.LANCZOS)
        left = (new_w - w) // 2
        top  = (new_h - h) // 2
        cropped = resized.crop((left, top, left + w, top + h))
        return np.array(cropped)

    clip = ImageClip(img_array).set_duration(duration)
    clip = clip.fl(lambda gf, t: make_frame(t))
    clip.write_videofile(
        output_path, fps=30, codec="libx264",
        audio=False, logger=None,
        ffmpeg_params=["-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p"]
    )
    return output_path


def generate_scene_clips(image_paths, clip_duration=4.0):
    """
    Converts all scene images to Ken Burns video clips.
    Alternates zoom in/out for visual variety.
    Returns list of .mp4 clip paths.
    """
    clip_paths = []
    directions = ["in", "out"]
    for i, img_path in enumerate(image_paths):
        print(f"  Animating scene {i+1}/{len(image_paths)}...")
        direction = directions[i % 2]
        clip_path = image_to_clip(img_path, duration=clip_duration, zoom_direction=direction)
        clip_paths.append(clip_path)
    print(f"✅ {len(clip_paths)} clips ready")
    return clip_paths


# ─── Full Cinematic Pipeline ──────────────────────────────────────────────────
def build_cinematic_background(script, character_key="skeleton",
                                num_scenes=6, clip_duration=4.0,
                                output_folder="scenes"):
    """
    Full pipeline:
    script → scene descriptions (Groq) → images (Pollinations) → clips (Ken Burns)
    Returns path to concatenated background .mp4
    """
    from moviepy.editor import VideoFileClip, concatenate_videoclips
    import math

    print(f"\n[character] Building cinematic background for '{character_key}'...")

    # Step 1: Get scene descriptions from script
    scenes = extract_scenes_from_script(script, character_key, num_scenes)
    print(f"Scenes: {scenes}")

    # Step 2: Generate images
    image_paths = generate_character_scenes(character_key, scenes, output_folder)

    # Step 3: Animate to clips
    clip_paths = generate_scene_clips(image_paths, clip_duration)

    # Step 4: Concatenate into one background video
    bg_output = os.path.join(output_folder, "background.mp4")
    clips = [VideoFileClip(p) for p in clip_paths if os.path.exists(p)]

    if not clips:
        return None

    bg = concatenate_videoclips(clips, method="compose")
    bg.write_videofile(
        bg_output, fps=30, codec="libx264",
        audio=False, logger=None,
        ffmpeg_params=["-crf", "20", "-preset", "fast"]
    )

    for c in clips:
        c.close()

    print(f"✅ Background ready: {bg_output}")
    return bg_output


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_script = """Nobody tells you this but Skeletor spent 30 days trying to get fit.
    Day 1 he couldn't do a single push-up. Day 10 he was crying at the gym.
    Day 30? He became the most jacked villain in Eternia. Follow for more!"""

    bg = build_cinematic_background(
        script=test_script,
        character_key="skeletor",
        num_scenes=6,
        clip_duration=4.0
    )
    print(f"Done: {bg}")
