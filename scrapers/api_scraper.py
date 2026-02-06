import requests
import datetime
from typing import List, Dict
from .base import NewsScraper
from config import Config

class HackerNewsScraper(NewsScraper):
    def fetch_news(self) -> List[Dict]:
        # Using Algolia API for search
        url = "http://hn.algolia.com/api/v1/search_by_date"
        params = {
            'query': 'AI OR LLM OR "Artificial Intelligence"',
            'tags': 'story',
            'hitsPerPage': 5
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            items = []
            for hit in data.get('hits', []):
                items.append({
                    'title': hit.get('title'),
                    'link': hit.get('url') or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    'source': 'Hacker News',
                    'published': hit.get('created_at'),
                    'summary': '' # No summary in HN search usually
                })
            return items
        except Exception as e:
            print(f"Error fetching Hacker News: {e}")
            return []

class NewsAPIScraper(NewsScraper):
    def fetch_news(self) -> List[Dict]:
        if not Config.NEWSAPI_KEY:
            print("NewsAPI Key missing. Skipping.")
            return []
            
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            'apiKey': Config.NEWSAPI_KEY,
            'category': 'technology',
            'q': 'AI', # Basic filter
            'pageSize': 5,
            'language': 'en' 
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            articles = response.json().get('articles', [])
            items = []
            for art in articles:
                items.append({
                    'title': art.get('title'),
                    'link': art.get('url'),
                    'source': f"NewsAPI ({art.get('source', {}).get('name')})",
                    'published': art.get('publishedAt'),
                    'summary': art.get('description', '')
                })
            return items
        except Exception as e:
            print(f"Error fetching NewsAPI: {e}")
            return []

# Naver Query Strategy v2.0
NAVER_QUERIES = {
    # TIER 1: Core Priority (Attempts first)
    "tier1": [
        '"Claude"', # Relaxed from AND
        '"Gemini"', # Relaxed
        '"GPT" AND (API OR 기업)',
        '"코딩 에이전트"',
        '"AI 코딩"',
        '"Cursor" OR "Windsurf" OR "Cline"',
        '"AI 에이전트" OR "업무 자동화"',
        '"생성형 AI" AND 기업',
        '"AX" AND 사례',
    ],
    
    # TIER 2: Fallback (If Tier 1 is empty)
    "tier2": [
        '"AI 도입"',
        '"생성형 AI" AND (기업 OR 산업)',
        '"LLM" AND (활용 OR 적용)',
        '"ChatGPT" AND (업무 OR 자동화)',
        '"인공지능" AND (솔루션 OR 서비스)'
    ],
    
    "exclude": ['-게임', '-웹툰', '-영화', '-연예', '-아이돌', '-캐릭터', '-NFT']
}

class NaverNewsScraper(NewsScraper):
    def fetch_news(self, query=None, display=20) -> List[Dict]:
        if not Config.NAVER_CLIENT_ID or not Config.NAVER_CLIENT_SECRET:
            print("Naver API keys missing. Skipping.")
            return []
            
        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": Config.NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": Config.NAVER_CLIENT_SECRET
        }

        all_items = []
        seen_links = set()
        
        # Strategy: Tier 1 -> Check Count -> Tier 2 if needed
        # Or if manual query provided, use that.
        
        query_list = []
        if query:
            query_list = [query]
        else:
            query_list = NAVER_QUERIES["tier1"]

        # 1. Fetch Tier 1 (or manual query)
        print("  [Naver] Fetching Tier 1 Queries...")
        self._execute_queries(url, headers, query_list, display, all_items, seen_links)
        
        # 2. Check Fallback
        if not query and len(all_items) < 3:
            print(f"  [Naver] Tier 1 only found {len(all_items)} items. Trying Tier 2...")
            self._execute_queries(url, headers, NAVER_QUERIES["tier2"], display, all_items, seen_links)

        return all_items

    def _execute_queries(self, url, headers, queries, display, collection, seen_links):
        base_display = max(5, int(display / max(1, len(queries)))) # Distribute display count
        
        for q in queries:
            # Append excludes
            full_query = q + " " + " ".join(NAVER_QUERIES["exclude"])
            
            params = {
                'query': full_query,
                'display': base_display, 
                'sort': 'date'
            }
            try:
                response = requests.get(url, headers=headers, params=params)
                if response.status_code != 200: continue
                
                for item in response.json().get('items', []):
                    link = item.get('originallink') or item.get('link')
                    if link in seen_links: continue
                    
                    clean_title = item.get('title', '').replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                    
                    seen_links.add(link)
                    collection.append({
                        'title': clean_title,
                        'link': link,
                        'source': 'Naver News',
                        'published': item.get('pubDate'),
                        'summary': item.get('description', '').replace('<b>', '').replace('</b>', '')
                    })
            except Exception as e:
                print(f"Error Naver query '{q}': {e}")
