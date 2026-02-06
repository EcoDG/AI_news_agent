import os
import requests
import urllib.parse
from config import Config
from dotenv import load_dotenv

load_dotenv()

def test_naver_complex():
    client_id = Config.NAVER_CLIENT_ID
    client_secret = Config.NAVER_CLIENT_SECRET
    
    if not client_id:
        print("❌ Keys missing.")
        return

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    # Test a complex Tier 1 query from our config
    test_query = '"Claude" AND (업데이트 OR 발표 OR 출시)'
    # Also test the exclude logic
    exclude = " -게임 -웹툰"
    full_query = test_query + exclude
    
    print(f"Testing Query: {full_query}")
    
    params = {'query': full_query, 'display': 5, 'sort': 'date'}

    try:
        resp = requests.get(url, headers=headers, params=params)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            print(f"Found: {len(items)}")
            for item in items:
                print(f"- {item['title'][:50]}...")
        else:
            print(f"Error: {resp.text}")

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_naver_complex()
