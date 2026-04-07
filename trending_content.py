from groq import Groq
import os
import time
import random
from datetime import datetime


# ─── Skeleton / Anatomy Niche Topics ──────────────────────────────────────────
SKELETON_TOPICS = [
    "Your skeleton replaces itself every 10 years",
    "The human jaw is the strongest muscle in the body",
    "Your bones are stronger than concrete",
    "You have more bones as a baby than as an adult",
    "The smallest bone in your body is in your ear",
    "Your skull has 22 bones fused together",
    "Bone marrow produces 2 million red blood cells per second",
    "The femur can support 30 times your body weight",
    "Teeth are not technically bones",
    "Your ribs move every time you breathe — 20,000 times a day",
    "Cartilage has no blood supply and feels no pain",
    "The hyoid is the only bone not connected to any other bone",
    "Your spine has 33 vertebrae but adults only have 26",
    "Knuckle cracking releases gas bubbles in joint fluid",
    "Broken bones heal stronger than before",
    "Your skeleton makes up only 15% of your total body weight",
    "Human bones contain gold, iron, and copper",
    "The kneecap doesn't appear until you're 3 years old",
]

# ─── General Viral Fallback Topics ────────────────────────────────────────────
FALLBACK_TOPICS = [
    "Artificial Intelligence", "Space exploration", "Human brain facts",
    "Quantum computing", "Sleep science", "Psychology tricks",
    "Neuroscience", "Ocean mysteries", "Animal intelligence", "Future of money"
]


def _get_daily_topics():
    today_seed = int(datetime.now().strftime("%Y%m%d"))
    random.seed(today_seed)
    shuffled = FALLBACK_TOPICS.copy()
    random.shuffle(shuffled)
    return shuffled[:5]


def get_trending_topics(count=5):
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=330, timeout=(10, 25))
        trending = pytrends.trending_searches(pn='india')
        topics = trending[0].tolist()[:count]
        if topics:
            print(f"Google Trends: {topics}")
            return topics
    except Exception as e:
        print(f"pytrends unavailable ({e}), using curated topics")
    return _get_daily_topics()


# ─── Script Generators ────────────────────────────────────────────────────────
def generate_script(topic, api_key, content_type="trending"):
    """
    content_type options:
      - 'trending'  : general viral short about any topic
      - 'skeleton'  : anatomy/body fact short (skeleton niche)
      - 'challenge' : 30-day / list format ("30 things only...")
    """
    client = Groq(api_key=api_key)

    if content_type == "skeleton":
        prompt = f"""Write a YouTube Shorts script about this human body / skeleton fact: "{topic}".

STRICT RULES:
- 60-80 words total (45 seconds when spoken)
- Open with a SHOCKING hook about the body fact — something that makes people say "wait, what?!"
- Include the actual science/fact explained simply
- Make it feel like a mind-blowing discovery
- Conversational tone, short punchy sentences
- End with: "Follow for more body facts!"
- NO hashtags, NO emojis, NO section labels
- Return ONLY the spoken script"""

    elif content_type == "challenge":
        prompt = f"""Write a YouTube Shorts script in a rapid-fire list format about: "{topic}".

STRICT RULES:
- 60-80 words total
- Open with hook like "30 things that happen when..." or "Nobody tells you these X facts about..."
- Deliver 4-6 punchy list items rapidly
- Each item = one short sentence
- End with: "Follow for more!"
- NO hashtags, NO emojis, NO section labels
- Return ONLY the spoken script"""

    else:  # trending
        prompt = f"""Write a YouTube Shorts script about "{topic}".

STRICT RULES:
- 60-80 words total (45 seconds when spoken)
- First 4-5 words MUST be a powerful hook (e.g. "Nobody talks about this...", "This will change how you...")
- Include 1-2 surprising facts most people don't know
- Conversational, punchy tone — like texting a friend
- End with exactly: "Follow for more!"
- NO hashtags, NO emojis, NO section labels
- Return ONLY the spoken script"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )
        script = response.choices[0].message.content.strip()
        for prefix in ["Script:", "Hook:", "**", "*", "---"]:
            script = script.replace(prefix, "").strip()
        word_count = len(script.split())
        print(f"Script: {word_count} words ({content_type})")
        return script if word_count >= 20 else None
    except Exception as e:
        print(f"Script generation error: {e}")
        return None


def generate_title_and_tags(topic, script, api_key):
    client = Groq(api_key=api_key)
    prompt = f"""Generate a YouTube Shorts title and 10 tags for a video about "{topic}".

RULES:
- Title: Under 70 chars, include 1-2 emojis, irresistible to click
- Tags: 10 comma-separated tags, always include #Shorts and #anatomy or #facts
- No explanation — just the output

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
            title = f"🦴 {topic[:50]}!"
        if not tags:
            tags = ['Shorts', 'anatomy', 'facts', 'skeleton', topic.lower()]
        return title, tags
    except Exception as e:
        print(f"Title/tags error: {e}")
        return f"🦴 {topic[:50]}!", ['Shorts', 'anatomy', 'facts']


def get_content(api_key, content_type="skeleton"):
    """Main entry: get topic → script → title → tags"""

    if content_type == "skeleton":
        # Rotate skeleton topics daily so no repeats
        random.seed(int(datetime.now().strftime("%Y%m%d%H")))
        topics = random.sample(SKELETON_TOPICS, min(5, len(SKELETON_TOPICS)))
    else:
        topics = get_trending_topics(count=5)

    for topic in topics:
        print(f"Trying: {topic}")
        script = generate_script(topic, api_key, content_type)
        if script:
            title, tags = generate_title_and_tags(topic, script, api_key)
            # First line of script = hook text for hook overlay in video
            hook = script.split('.')[0].split('!')[0].strip()
            return {
                "topic": topic,
                "script": script,
                "title": title,
                "tags": tags,
                "hook": hook,
                "content_type": content_type
            }
        time.sleep(0.5)

    # Hard fallback
    topic = "Your bones are stronger than steel"
    script = "Nobody tells you this but your bones are actually four times stronger than concrete. The femur alone can support 30 times your body weight before it breaks. Your skeleton isn't just a frame — it's the most advanced structural engineering on earth. Follow for more body facts!"
    return {
        "topic": topic,
        "script": script,
        "title": "🦴 Your Bones Are Stronger Than You Think!",
        "tags": ["anatomy", "skeleton", "bodyFacts", "Shorts", "science"],
        "hook": "Nobody tells you this but your bones are actually four times stronger than concrete",
        "content_type": content_type
    }


if __name__ == "__main__":
    api_key = os.environ.get("GROQ_API_KEY", "")
    for ctype in ["skeleton", "trending", "challenge"]:
        print(f"\n{'='*55}\nContent type: {ctype}")
        content = get_content(api_key, content_type=ctype)
        print(f"Topic : {content['topic']}")
        print(f"Title : {content['title']}")
        print(f"Hook  : {content['hook']}")
        print(f"Script:\n{content['script']}")
        print('='*55)
