import asyncio
import os
import subprocess

VOICES = [
    "en-US-AndrewNeural",
    "en-US-JennyNeural",
    "en-US-GuyNeural",
]


def _estimate_timestamps(script, duration):
    """Build word-level timestamps from total duration (uniform distribution)"""
    words = script.split()
    if not words:
        return []
    time_per_word = duration / len(words)
    return [
        {'word': w, 'start': i * time_per_word, 'duration': time_per_word}
        for i, w in enumerate(words)
    ]


def _try_edge_tts(script, output_path, voice):
    """Attempt edge-tts, return word_data or None on failure"""
    try:
        import edge_tts

        async def _run():
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
            if not audio_chunks:
                return None
            raw = output_path.replace('.mp3', '_raw.mp3')
            with open(raw, 'wb') as f:
                for c in audio_chunks:
                    f.write(c)
            subprocess.run(
                ['ffmpeg', '-y', '-i', raw, '-ar', '44100', '-ac', '2', output_path],
                capture_output=True
            )
            if os.path.exists(raw):
                os.remove(raw)
            return word_data if word_data else None

        result = asyncio.run(_run())
        if result:
            print(f"edge-tts success: {len(result)} words timestamped")
        return result
    except Exception as e:
        print(f"edge-tts failed ({e}), falling back to gTTS")
        return None


def _use_gtts(script, output_path):
    """gTTS fallback - always works, estimates timestamps"""
    from gtts import gTTS
    from moviepy.editor import AudioFileClip
    print("Using gTTS...")
    tts = gTTS(text=script, lang='en', slow=False)
    tts.save(output_path)
    dur = AudioFileClip(output_path).duration
    word_data = _estimate_timestamps(script, dur)
    print(f"gTTS ready: {len(word_data)} words, {dur:.1f}s")
    return word_data


def generate_voice(script, output_path="voice.mp3", voice=None):
    if voice is None:
        voice = VOICES[0]
    print(f"Voice engine: trying edge-tts ({voice})...")
    word_data = _try_edge_tts(script, output_path, voice)
    if word_data and os.path.exists(output_path):
        return word_data
    return _use_gtts(script, output_path)


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
    words = generate_voice(
        "Nobody talks about this but black holes are actually portals. Follow for more!",
        'test_voice.mp3'
    )
    segs = words_to_caption_segments(words)
    for s in segs:
        print(f"{s['start']:.2f}s - {s['end']:.2f}s : {s['text']}")
