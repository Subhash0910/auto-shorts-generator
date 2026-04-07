from pytrends.request import TrendReq
from groq import Groq
import os
import time


def get_trending_topics(count=5):
    """Get top trending topics from Google Trends"""
    try:
        pytrends = TrendReq(hl='en-US', tz=330)
        trending = pytrends.trending_searches(pn='india')
        topics = trending[0].tolist()[:count]
        print(f"Trending topics fetched: {topics}")
        return topics
    except Exception as e:
        print(f"pytrends error: {e}, using fallback topics")
        return ["AI news", "technology", "science facts"]


def generate_script(topic, api_key):
    """Generate a punchy YouTube Shorts script about a trending topic"""
    client = Groq(api_key=api_key)

    prompt = f"""Write a YouTube Shorts script about "{topic}" which is trending right now.

STRICT RULES:
- Maximum 80 words total (must be speakable in 45 seconds)
- First 5 words MUST be a strong hook that stops scrolling
- Include 1-2 surprising facts most people don't know
- Conversational tone, like texting a friend
- End with exactly: "Follow for more!"
- NO hashtags, NO emojis, NO stage directions, NO labels
- Return ONLY the spoken script text, nothing else

Example format:
You won't believe what [topic] just did. [Fact 1]. [Fact 2]. Most people have no idea this is happening. Follow for more!"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )
        script = response.choices[0].message.content.strip()
        print(f"Script generated ({len(script.split())} words)")
        return script
    except Exception as e:
        print(f"Groq error: {e}")
        return None


def generate_title_and_tags(topic, script, api_key):
    """Generate SEO-optimized title and tags"""
    client = Groq(api_key=api_key)

    prompt = f"""Generate a YouTube Shorts title and tags for this video about "{topic}".

Script: {script[:200]}

RULES:
- Title: Under 60 chars, include 1-2 emojis, make it clickable
- Tags: 10 relevant tags as comma-separated list
- Include #Shorts in tags always

Format EXACTLY like this:
Title: [title here]
Tags: [tag1, tag2, tag3...]"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        lines = content.split('\n')
        title = ""
        tags = []

        for line in lines:
            if line.lower().startswith('title:'):
                title = line.replace('Title:', '').replace('title:', '').strip()
            elif line.lower().startswith('tags:'):
                tag_str = line.replace('Tags:', '').replace('tags:', '').strip()
                tags = [t.strip() for t in tag_str.split(',')]

        if not title:
            title = f"🔥 {topic} - You Need To Know This!"
        if not tags:
            tags = ['Shorts', 'trending', topic.lower()]

        return title, tags
    except Exception as e:
        print(f"Title/tags error: {e}")
        return f"🔥 {topic} Facts!", ['Shorts', 'trending']


def get_content(api_key):
    """Main function: get trending topic + generate all content"""
    topics = get_trending_topics(count=5)

    for topic in topics:
        print(f"\nTrying topic: {topic}")
        script = generate_script(topic, api_key)
        if script and len(script.split()) >= 20:
            title, tags = generate_title_and_tags(topic, script, api_key)
            return {
                "topic": topic,
                "script": script,
                "title": title,
                "tags": tags
            }
        time.sleep(1)

    print("All trending topics failed, using fallback")
    fallback_topic = "AI technology"
    script = generate_script(fallback_topic, api_key)
    return {
        "topic": fallback_topic,
        "script": script or "AI is changing everything. The technology growing fastest right now will reshape jobs, creativity, and daily life within 5 years. Most people are completely unprepared. Follow for more!",
        "title": "🤖 AI Is Changing Everything!",
        "tags": ["Shorts", "AI", "technology", "trending"]
    }


if __name__ == "__main__":
    api_key = os.environ.get("RIDDLE_API_KEY", "")
    content = get_content(api_key)
    print(f"\n{'='*50}")
    print(f"Topic: {content['topic']}")
    print(f"Title: {content['title']}")
    print(f"Tags: {', '.join(content['tags'])}")
    print(f"\nScript:\n{content['script']}")
    print(f"{'='*50}")
