import urllib.request
import urllib.parse
import json
import ssl
from typing import List, Dict
from config import Config

class SimpleNaverScraper:
    def __init__(self):
        self.last_error = "Init"

    def fetch_news(self) -> List[Dict]:
        if not Config.NAVER_CLIENT_ID or not Config.NAVER_CLIENT_SECRET:
            self.last_error = "Keys Missing"
            return []

        # 1. Very Basic Query (Korean Only)
        # "AI" might be ambiguous. "인공지능" is safe.
        encText = urllib.parse.quote("인공지능")
        url = "https://openapi.naver.com/v1/search/news.json?query=" + encText + "&display=10&sort=date"
        
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id", Config.NAVER_CLIENT_ID)
        request.add_header("X-Naver-Client-Secret", Config.NAVER_CLIENT_SECRET)
        
        try:
            # Bypass SSL verification if needed (though not recommended, good for debugging)
            context = ssl._create_unverified_context()
            response = urllib.request.urlopen(request, context=context)
            rescode = response.getcode()
            
            if rescode == 200:
                response_body = response.read()
                data = json.loads(response_body.decode('utf-8'))
                items = data.get('items', [])
                
                self.last_error = f"Success (Found {len(items)})"
                
                # Convert to standard format
                clean_items = []
                for item in items:
                    clean_items.append({
                        'title': item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"'),
                        'link': item['originallink'] or item['link'],
                        'summary': item['description'].replace('<b>', '').replace('</b>', ''),
                        'source': 'Naver News (Simple)',
                        'published': item['pubDate']
                    })
                return clean_items
            else:
                self.last_error = f"HTTP {rescode}"
                return []
                
        except Exception as e:
            self.last_error = f"Exception: {e}"
            print(f"Error checking Naver: {e}")
            return []
