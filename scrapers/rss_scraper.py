import feedparser
import requests
from typing import List, Dict
from .base import NewsScraper
from bs4 import BeautifulSoup
import re

# ========================================
# 해외 뉴스 키워드 가중치 (RSS Feed) v2.0
# ========================================

KEYWORD_TIER_S = {
    "keywords": [
        "Claude Code", "GPT-4", "GPT-5", "Opus 4.6",
        "Gemini 1.5", "Gemini 2.0", "Google Gemini",
        "GitHub Copilot", "Cursor", "Windsurf",
        "OpenClaw", "Oh-My-OpenCode",
    ],
    "score": 15
}

KEYWORD_TIER_A = {
    "keywords": [
        "autonomous agents", "agentic workflow", "AI adoption",
        "multi-agent", "implementation case study",
        "Gartner", "McKinsey", "a16z",
        "Vibe coding", "LLM orchestration", "Generative AI security", "Shadow AI"
    ],
    "score": 10
}

KEYWORD_TIER_B = {
    "keywords": [
        "LLM orchestration", "enterprise AI", "workflow automation",
        "tool comparison", "benchmark", "AI Tool",
        "Transformation", "Enterprise"
    ],
    "score": 5
}

KEYWORD_TIER_C = {
    "keywords": [
        "AI tool", "generative AI", "transformation",
        "digital", "productivity",
    ],
    "score": 2
}

NEGATIVE_KEYWORDS = {
    "keywords": [
        "consumer app", "gaming", "NFT", "metaverse", "crypto", "web3",
        "hiring", "job posting", "conference", "webinar", "event",
    ],
    "score": -99
}

IMMEDIATE_REJECT_PATTERNS = [
    r"conference|webinar|summit|event",
    r"launching soon|beta.*release|coming soon",
    r"free trial|promotion",
    r"game|movie|webtoon|idol|entertainment",
    r"cryptocurrency|NFT|metaverse",
]

class RSSScraper(NewsScraper):
    def __init__(self, feeds: List[str], category: str = "general"):
        self.feeds = feeds
        self.category = category
        self.keywords = {} # Not used in v2.0 logic directly

    def fetch_news(self) -> List[Dict]:
        news_items = []
        seen_links = set()
        
        for feed_url in self.feeds:
            try:
                # Use a browser-like user agent
                feed = feedparser.parse(feed_url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
                
                # Debug info
                print(f"Feed: {feed_url} - Status: {getattr(feed, 'status', 'Unknown')} - Entries: {len(feed.entries)}")
                
                if feed.bozo:
                    print(f"Feed bozo error: {feed.bozo_exception}")
                    continue
                
                # Check top 15 from each feed (increased from 10)
                for entry in feed.entries[:15]: 
                    link = entry.get('link', '')
                    if link in seen_links:
                        continue
                        
                    title = entry.get('title', '')
                    
                    # 1. Immediate Reject Check
                    if self._should_reject_immediately(title):
                        print(f"  [Reject] {title[:30]}... (Pattern Match)")
                        continue

                    raw_summary = entry.get('summary', '') or entry.get('description', '')
                    
                    # Clean summary for scoring
                    soup = BeautifulSoup(raw_summary, "html.parser")
                    text_content = soup.get_text().strip()
                    
                    # Two-Pass Extraction check
                    if len(text_content) < 200:
                        fetched_text = self._fetch_full_content(link)
                        if fetched_text:
                            text_content = fetched_text 
                    
                    score = self._calculate_score(title, text_content)
                    
                    # Negative Score Check
                    if score < 0:
                        print(f"  [Reject] {title[:30]}... (Negative Score)")
                        continue

                    # Threshold Check (Tier C min)
                    if score >= 2:
                        seen_links.add(link)
                        news_items.append({
                            'title': title,
                            'link': link,
                            'summary': text_content[:500],
                            'source': feed.feed.get('title', 'RSS Feed'),
                            'published': entry.get('published', ''),
                            'score': score,
                            'category': self.category
                        })
            except Exception as e:
                print(f"Error fetching RSS {feed_url}: {e}")
                
        return news_items

    def _calculate_score(self, title: str, content: str) -> int:
        score = 0
        text = (title + " " + content).lower()
        
        # Check Negative First
        for kw in NEGATIVE_KEYWORDS["keywords"]:
            if kw.lower() in text:
                return -99

        # Tier S
        for kw in KEYWORD_TIER_S["keywords"]:
            if kw.lower() in text:
                score += KEYWORD_TIER_S["score"]
        
        # Tier A
        for kw in KEYWORD_TIER_A["keywords"]:
            if kw.lower() in text:
                score += KEYWORD_TIER_A["score"]

        # Tier B
        for kw in KEYWORD_TIER_B["keywords"]:
            if kw.lower() in text:
                score += KEYWORD_TIER_B["score"]

        # Tier C
        for kw in KEYWORD_TIER_C["keywords"]:
            if kw.lower() in text:
                score += KEYWORD_TIER_C["score"]
                
        return score

    def _should_reject_immediately(self, title: str) -> bool:
        for pattern in IMMEDIATE_REJECT_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                return True
        return False
        
    def _is_relevant(self, title: str, content: str, score: int) -> bool:
        return score >= 2

    def _fetch_full_content(self, url: str) -> str:
        """
        Pass 2: Fetch article body or Meta Description
        """
        if not url: return ""
        
        try:
            # Random User-Agent to avoid blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code != 200:
                print(f"Failed to fetch {url}: {resp.status_code}")
                return ""
            
            resp.encoding = resp.apparent_encoding
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 1. Try <article>
            article = soup.find('article')
            if article:
                return article.get_text(strip=True)
            
            # 2. Try common content divs
            for class_name in ['main-content', 'article-body', 'post-content', 'entry-content', 'news_body', 'view_con']:
                content_div = soup.find('div', class_=class_name)
                if content_div:
                    return content_div.get_text(strip=True)
            
            # 3. Fallback: Meta Description
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc and meta_desc.get('content'):
                return "[Meta] " + meta_desc['content']
            
            return ""
            
        except Exception as e:
            print(f"Error fetching full content for {url}: {e}")
            return ""
