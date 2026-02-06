import os
import requests
import urllib.parse
from config import Config
from dotenv import load_dotenv

load_dotenv()

def test_excludes():
    client_id = Config.NAVER_CLIENT_ID
    client_secret = Config.NAVER_CLIENT_SECRET
    
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    # Test 1: "AI" without excludes
    print("--- Test 1: Broad 'AI' ---")
    params = {'query': 'AI', 'display': 5, 'sort': 'date'}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        print(f"Count: {len(resp.json().get('items', []))}")
    else:
        print(f"Error: {resp.text}")

    # Test 2: "AI" WITH excludes
    excludes = ['-게임', '-웹툰', '-영화', '-연예', '-아이돌', '-캐릭터', '-NFT']
    exclude_str = " " + " ".join(excludes)
    full_query = "AI" + exclude_str
    
    print(f"\n--- Test 2: 'AI' + Excludes ({exclude_str}) ---")
    params = {'query': full_query, 'display': 5, 'sort': 'date'}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        items = resp.json().get('items', [])
        print(f"Count: {len(items)}")
        for item in items:
            print(f"- {item['title'][:40]}...")
    else:
        print(f"Error: {resp.text}")

if __name__ == "__main__":
    test_excludes()
