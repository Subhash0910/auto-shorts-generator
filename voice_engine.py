import asyncio
import edge_tts
import json
import os
import re

# Best free neural voices
VOICES = [
    "en-US-AndrewNeural",     # Male, natural, great for facts
    "en-US-JennyNeural",      # Female, clear, energetic
    "en-US-GuyNeural",        # Male, deep, authoritative
    "en-GB-RyanNeural",       # British, sounds smart
]


async def _generate_voice(script, output_path, voice):
    """Generate voice with word-level timestamps"""
    communicate = edge_tts.Communicate(script, voice, rate="+15%")
    word_data = []
    with open(output_path, 'wb') as f:
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                f.write(chunk['data'])
            elif chunk['type'] == 'WordBoundary':
                word_data.append({
                    'word': chunk['text'],
                    'start': chunk['offset'] / 10_000_000,  # 100ns units -> seconds
                    'duration': chunk['duration'] / 10_000_000
                })
    return word_data


def generate_voice(script, output_path="voice.mp3", voice=None):
    """Generate edge-tts voice + return word timestamps"""
    if voice is None:
        voice = VOICES[0]
    print(f"Generating voice: {voice}")
    word_data = asyncio.run(_generate_voice(script, output_path, voice))
    print(f"Voice generated: {len(word_data)} words timestamped")
    return word_data


def words_to_caption_segments(word_data, words_per_caption=4):
    """Group words into caption segments with start/end times"""
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
    test_script = "Nobody talks about this but black holes are actually portals to other dimensions. Follow for more!"
    words = generate_voice(test_script, 'test_voice.mp3')
    print("Word timestamps:")
    for w in words[:5]:
        print(f"  {w['word']:20} {w['start']:.2f}s")
