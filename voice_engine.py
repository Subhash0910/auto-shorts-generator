import asyncio
import edge_tts
import os
import subprocess
import json

VOICES = [
    "en-US-AndrewNeural",
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-GB-RyanNeural",
]


async def _generate(script, output_path, voice):
    """Generate audio + collect word boundary events"""
    communicate = edge_tts.Communicate(text=script, voice=voice, rate="+15%")
    word_data = []
    audio_chunks = []

    async for chunk in communicate.stream():
        if chunk['type'] == 'audio':
            audio_chunks.append(chunk['data'])
        elif chunk['type'] == 'WordBoundary':
            word_data.append({
                'word': chunk['text'],
                'start': chunk['offset'] / 10_000_000,
                'duration': chunk['duration'] / 10_000_000
            })

    with open(output_path, 'wb') as f:
        for chunk in audio_chunks:
            f.write(chunk)

    return word_data


def generate_voice(script, output_path="voice.mp3", voice=None):
    if voice is None:
        voice = VOICES[0]
    print(f"Voice: {voice}")

    # edge-tts outputs webm/opus internally, convert to mp3 with ffmpeg
    raw_path = output_path.replace('.mp3', '_raw.mp3')

    word_data = asyncio.run(_generate(script, raw_path, voice))

    # Convert to standard mp3 so moviepy can read it cleanly
    cmd = ['ffmpeg', '-y', '-i', raw_path, '-ar', '44100', '-ac', '2', output_path]
    result = subprocess.run(cmd, capture_output=True)
    if os.path.exists(raw_path):
        os.remove(raw_path)

    if not word_data:
        print("WARNING: No word timestamps received from edge-tts")
        print("Falling back to gTTS voice")
        from gtts import gTTS
        tts = gTTS(text=script, lang='en', slow=False)
        tts.save(output_path)
        # Build fake timestamps from word count + estimated duration
        from moviepy.editor import AudioFileClip
        dur = AudioFileClip(output_path).duration
        words = script.split()
        time_per_word = dur / len(words)
        word_data = [
            {'word': w, 'start': i * time_per_word, 'duration': time_per_word}
            for i, w in enumerate(words)
        ]

    print(f"Voice ready: {len(word_data)} words timestamped")
    return word_data


def words_to_caption_segments(word_data, words_per_caption=4):
    segments = []
    i = 0
    while i < len(word_data):
        group = word_data[i:i + words_per_caption]
        text = ' '.join(w['word'] for w in group)
        start = group[0]['start']
        end = group[-1]['start'] + group[-1]['duration']
        segments.append({'text': text, 'start': start, 'end': end})
        i += words_per_caption
    return segments


if __name__ == '__main__':
    words = generate_voice("Nobody talks about this but black holes are actually portals. Follow for more!", 'test.mp3')
    segs = words_to_caption_segments(words)
    for s in segs:
        print(f"{s['start']:.2f}s - {s['end']:.2f}s : {s['text']}")
