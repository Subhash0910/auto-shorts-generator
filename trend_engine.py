import requests
import xml.etree.ElementTree as ET
import json
import os
import re
from datetime import datetime

BLACKLIST = [
    'war', 'death', 'died', 'killed', 'shooting', 'murder', 'terrorist',
    'disaster', 'earthquake', 'flood', 'hurricane', 'politics', 'election',
    'president', 'congress', 'senate', 'republican', 'democrat', 'biden',
    'trump', 'ukraine', 'russia', 'israel', 'gaza', 'palestine', 'arrest',
    'suicide', 'overdose', 'crash', 'accident', 'fire', 'explosion'
]

GOOD_CATEGORIES = [
    'science', 'technology', 'ai', 'space', 'nature', 'psychology',
    'history', 'finance', 'health', 'entertainment', 'sports', 'music',
    'animals', 'ocean', 'brain', 'future', 'invention', 'discovery'
]


def is_blacklisted(text):
    text_lower = text.lower()
    return any(word in text_lower for word in BLACKLIST)


def score_topic(title):
    """Score a topic based on virality signals"""
    score = 50
    title_lower = title.lower()
    for cat in GOOD_CATEGORIES:
        if cat in title_lower:
            score += 20
    viral_words = ['secret', 'never', 'actually', 'truth', 'real', 'why',
                   'how', 'what', 'nobody', 'shocking', 'revealed', 'hidden',
                   'surprising', 'incredible', 'insane', 'mindblowing']
    for w in viral_words:
        if w in title_lower:
            score += 10
    if len(title.split()) < 4:
        score -= 20  # too short = too vague
    return score


def get_google_trends():
    """Parse Google Trends daily RSS — no library, no 404"""
    topics = []
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        r = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall('.//item'):
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()
                    if not is_blacklisted(title):
                        topics.append({'title': title, 'source': 'google', 'score': score_topic(title)})
            print(f"Google RSS: {len(topics)} topics")
    except Exception as e:
        print(f"Google RSS error: {e}")
    return topics


def get_reddit_trending():
    """Reddit r/all top posts — public JSON, no API key needed"""
    topics = []
    try:
        url = "https://www.reddit.com/r/all/top.json?limit=25&t=day"
        r = requests.get(url, timeout=10, headers={'User-Agent': 'shorts-bot/1.0'})
        if r.status_code == 200:
            posts = r.json()['data']['children']
            for post in posts:
                title = post['data']['title']
                upvotes = post['data']['ups']
                if not is_blacklisted(title) and upvotes > 5000:
                    score = score_topic(title) + min(upvotes // 10000, 30)
                    topics.append({'title': title, 'source': 'reddit', 'score': score})
            print(f"Reddit: {len(topics)} topics")
    except Exception as e:
        print(f"Reddit error: {e}")
    return topics


def get_youtube_trending():
    """YouTube trending via Data API v3"""
    topics = []
    api_key = os.environ.get('YOUTUBE_API_KEY', '')
    if not api_key:
        print("No YOUTUBE_API_KEY set, skipping YouTube trends")
        return topics
    try:
        url = (
            f"https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet&chart=mostPopular&regionCode=US"
            f"&maxResults=20&key={api_key}"
        )
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            items = r.json().get('items', [])
            for item in items:
                title = item['snippet']['title']
                if not is_blacklisted(title):
                    topics.append({'title': title, 'source': 'youtube', 'score': score_topic(title) + 15})
            print(f"YouTube: {len(topics)} topics")
    except Exception as e:
        print(f"YouTube trends error: {e}")
    return topics


def get_best_topic():
    """Aggregate all sources, score, return best topic string"""
    all_topics = []
    all_topics += get_google_trends()
    all_topics += get_reddit_trending()
    all_topics += get_youtube_trending()

    if not all_topics:
        print("All trend sources failed, using date-rotated fallback")
        fallbacks = [
            "Artificial Intelligence breakthroughs",
            "Space exploration discoveries",
            "Human brain psychology",
            "Quantum computing explained",
            "Ocean mysteries",
            "Future of money",
            "Sleep science facts",
            "Animal intelligence",
            "Climate technology",
            "History secrets"
        ]
        import random
        random.seed(int(datetime.now().strftime("%Y%m%d")))
        return random.choice(fallbacks)

    all_topics.sort(key=lambda x: x['score'], reverse=True)
    best = all_topics[0]
    print(f"\nBest topic: '{best['title']}' (score={best['score']}, source={best['source']})")
    return best['title']


if __name__ == '__main__':
    topic = get_best_topic()
    print(f"\nSelected: {topic}")
