import feedparser
from typing import List, Dict
from .base import NewsScraper
from bs4 import BeautifulSoup

class RSSScraper(NewsScraper):
    def __init__(self, feeds: List[str], category: str = "general"):
        """
        category: 'domestic' or 'international'
        """
        self.feeds = feeds
        self.category = category
        
        # Priority Keywords
        if category == 'domestic':
            self.keywords = {
                'AI Tool': 3, 'AI 도구': 3,
                'AX': 5, 'AI 전환': 5, 'Transformation': 3, 'AX도입': 5,
                '기업': 2, '도입': 2, '사례': 2, '구축': 2,
                '업무': 1, '생산성': 1,
                '바이브코딩': 5, 'Vibe Coding': 5,
                '자동화': 3, 'Automation': 3,
                '에이전트': 4, 'Agent': 4,
                'RPA': 2, 'LLM': 2
            }
        else:
            self.keywords = {
                'AI Tool': 3, 'Productivity': 2,
                'AX': 5, 'Transformation': 3,
                'Enterprise': 3, 'Adoption': 3, 'Business': 1,
                'Workforce': 1, 'Workplace': 1
            }

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
                
                # Check top 10 from each feed
                for entry in feed.entries[:10]: 
                    link = entry.get('link', '')
                    if link in seen_links:
                        continue
                        
                    title = entry.get('title', '')
                    raw_summary = entry.get('summary', '') or entry.get('description', '')
                    
                    # Clean summary for scoring
                    soup = BeautifulSoup(raw_summary, "html.parser")
                    text_content = soup.get_text()
                    
                    score = self._calculate_score(title, text_content)
                    
                    # Basic relevance check (score > 0 OR contains basic AI/AX terms)
                    # For strict filtering, we can enforce score > X.
                    # Here we keep minimal filter, main.py will pick Top X.
                    if self._is_relevant(title, text_content, score):
                        seen_links.add(link)
                        news_items.append({
                            'title': title,
                            'link': link,
                            'summary': text_content[:500], # Store cleaned text, truncated
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
        
        for kw, points in self.keywords.items():
            if kw.lower() in text:
                score += points
                
        return score

    def _is_relevant(self, title: str, content: str, score: int) -> bool:
        # Base filter: Must contain some AI reference or have a high score
        base_keywords = ['ai', 'gpt', 'llm', 'generative', '인공지능', '모델']
        text = (title + " " + content).lower()
        
        # If score is high (matches AX/Tool keywords) -> Relevant
        if score >= 1: return True
        
        # Fallback: simple AI keyword check
        return any(k in text for k in base_keywords)
