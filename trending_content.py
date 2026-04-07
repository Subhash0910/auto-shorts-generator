from groq import Groq
import os
import time
import random
import hashlib
from datetime import datetime


FALLBACK_TOPICS = [
    "Artificial Intelligence", "Space exploration", "Human brain facts",
    "Quantum computing", "Climate change", "Crypto markets",
    "Sleep science", "Psychology tricks", "Stock market",
    "Social media algorithms", "Black holes", "Future of work",
    "Neuroscience", "Viral tech trends", "Health hacks"
]


def _get_daily_topics():
    """Rotate topics daily based on date so no two days are the same"""
    today_seed = int(datetime.now().strftime("%Y%m%d"))
    random.seed(today_seed)
    shuffled = FALLBACK_TOPICS.copy()
    random.shuffle(shuffled)
    return shuffled[:5]


def get_trending_topics(count=5):
    """Try Google Trends first, fall back to date-rotated topic list"""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=330, timeout=(10, 25))
        trending = pytrends.trending_searches(pn='india')
        topics = trending[0].tolist()[:count]
        if topics:
            print(f"✅ Google Trends: {topics}")
            return topics
    except Exception as e:
        print(f"pytrends unavailable ({e}), using curated topics")
    return _get_daily_topics()


def generate_script(topic, api_key):
    client = Groq(api_key=api_key)
    prompt = f"""Write a YouTube Shorts script about "{topic}".

STRICT RULES:
- 60-80 words total (45 seconds when spoken aloud)
- First 4-5 words MUST be a powerful hook that stops scrolling (e.g. "Nobody talks about this...", "This will change how you...")
- Include 1-2 surprising facts most people don't know
- Conversational, punchy tone — like texting a friend
- End with exactly: "Follow for more!"
- NO hashtags, NO emojis, NO labels like "Hook:" or "Script:"
- Return ONLY the spoken script text"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )
        script = response.choices[0].message.content.strip()
        # Remove any markdown formatting
        for prefix in ["Script:", "Hook:", "**", "*"]:
            script = script.replace(prefix, "").strip()
        word_count = len(script.split())
        print(f"Script generated ({word_count} words)")
        return script if word_count >= 20 else None
    except Exception as e:
        print(f"Script generation error: {e}")
        return None


def generate_title_and_tags(topic, script, api_key):
    client = Groq(api_key=api_key)
    prompt = f"""Generate a YouTube Shorts title and 10 tags for a video about "{topic}".

RULES:
- Title: Under 70 chars, include 1-2 emojis, make it irresistible to click
- Tags: 10 relevant comma-separated tags, include #Shorts
- No explanation, just the output

Format EXACTLY:
Title: [title]
Tags: [tag1, tag2, ...]"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        text = response.choices[0].message.content.strip()
        title, tags = "", []
        for line in text.split('\n'):
            if line.lower().startswith('title:'):
                title = line.split(':', 1)[1].strip()
            elif line.lower().startswith('tags:'):
                tags = [t.strip() for t in line.split(':', 1)[1].split(',')]
        if not title:
            title = f"🔥 {topic} Facts You Never Knew!"
        if not tags:
            tags = ['Shorts', 'trending', topic.lower(), 'facts']
        return title, tags
    except Exception as e:
        print(f"Title/tags error: {e}")
        return f"🔥 {topic}!", ['Shorts', 'trending']


def get_content(api_key):
    """Main entry: get trending topic → script → title → tags"""
    topics = get_trending_topics(count=5)

    for topic in topics:
        print(f"\nTrying: {topic}")
        script = generate_script(topic, api_key)
        if script:
            title, tags = generate_title_and_tags(topic, script, api_key)
            return {
                "topic": topic,
                "script": script,
                "title": title,
                "tags": tags
            }
        time.sleep(0.5)

    # Hard fallback
    topic = "AI technology"
    return {
        "topic": topic,
        "script": "Nobody talks about how fast AI is actually moving. In the last 6 months alone, AI wrote code, passed medical exams, and created Oscar-winning visuals. Most people have no idea how close we are to a complete shift in how work happens. Follow for more!",
        "title": "🤖 AI Is Moving Faster Than You Think!",
        "tags": ["AI", "technology", "future", "Shorts", "trending", "facts"]
    }


if __name__ == "__main__":
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("RIDDLE_API_KEY", "")
    content = get_content(api_key)
    print(f"\n{'='*55}")
    print(f"Topic : {content['topic']}")
    print(f"Title : {content['title']}")
    print(f"Tags  : {', '.join(content['tags'][:5])}")
    print(f"\nScript:\n{content['script']}")
    print('='*55)
