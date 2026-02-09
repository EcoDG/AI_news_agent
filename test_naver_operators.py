import os
import requests
import urllib.parse
from config import Config
from dotenv import load_dotenv

load_dotenv()

def test_naver_operators():
    client_id = Config.NAVER_CLIENT_ID
    client_secret = Config.NAVER_CLIENT_SECRET
    
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    # Query 1: Using "OR" (Current Strategy)
    q1 = '"Claude" OR "클로드"'
    print(f"Testing: {q1}")
    resp = requests.get(url, headers=headers, params={'query': q1, 'display': 5})
    print(f"Result (OR): {len(resp.json().get('items', []))}")
    if resp.json().get('items'):
        print(f" Sample: {resp.json()['items'][0]['title']}")

    # Query 2: Using "|" (Pipe)
    q2 = "Claude | 클로드"
    print(f"\nTesting: {q2}")
    resp = requests.get(url, headers=headers, params={'query': q2, 'display': 5})
    print(f"Result (|): {len(resp.json().get('items', []))}")
    if resp.json().get('items'):
        print(f" Sample: {resp.json()['items'][0]['title']}")

    # Query 3: Separate Calls (What I might have to do)
    q3 = "클로드"
    print(f"\nTesting: {q3}")
    resp = requests.get(url, headers=headers, params={'query': q3, 'display': 5})
    print(f"Result (Single): {len(resp.json().get('items', []))}")

if __name__ == "__main__":
    test_naver_operators()
