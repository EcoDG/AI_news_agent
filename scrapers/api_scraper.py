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
        
        # Default Query (V4 Niche)
        if not query:
            query = '"바이브코딩" OR "AI 에이전트" OR "AX" OR "업무 자동화" OR "생성형 AI 보안" OR "K-LLM"'
            
        params = {
            'query': query,
            'display': display, 
            'sort': 'date'
        }
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            items = []
            for item in response.json().get('items', []):
                # Naver returns titles with bold tags
                clean_title = item.get('title', '').replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                items.append({
                    'title': clean_title,
                    'link': item.get('originallink') or item.get('link'),
                    'source': 'Naver News',
                    'published': item.get('pubDate'),
                    'summary': item.get('description', '').replace('<b>', '').replace('</b>', '')
                })
            return items
        except Exception as e:
            print(f"Error fetching Naver News: {e}")
            return []
