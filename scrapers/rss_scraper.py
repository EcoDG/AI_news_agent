import feedparser
import requests
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
                # [Domestic Grid]
                '바이브코딩': 10, 'Vibe Coding': 10,
                'AI 에이전트 도입': 10, 'Agent': 5,
                '업무 자동화 사례': 10, 'Automation': 5,
                'AX': 5, 'AX 전략': 10, 'AI 전환': 5,
                '생성형 AI 보안': 10, 'Security': 3,
                'K-LLM': 10,
                'AI B2B 솔루션': 10, 'B2B': 3,
                
                # Base
                'AI Tool': 5, '도구': 2,
                '기업': 2, '도입': 2, '사례': 2, '구축': 2,
                '업무': 1, '생산성': 1, 'RPA': 2
            }
        else:
            self.keywords = {
                # [Global Grid]
                'Autonomous Agents': 10, 'Agentic Workflow': 10,
                'Multi-agent': 10, 'AI-native': 10,
                'Vibe coding': 10,
                'LLM orchestration': 10,
                'Generative AI security': 10, 'Shadow AI': 10,
                
                # Base
                'AI Tool': 5, 'Transformation': 3,
                'Enterprise': 3, 'Adoption': 3, 'Business': 1,
                'Productivity': 2, 'Workforce': 1
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
                    text_content = soup.get_text().strip()
                    
                    # Two-Pass Extraction: If RSS summary is too short, fetch URL
                    if len(text_content) < 200:
                        fetched_text = self._fetch_full_content(link)
                        if fetched_text:
                            text_content = fetched_text # Override with full content
                    
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
