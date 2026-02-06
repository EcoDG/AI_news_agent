import os
import requests
from config import Config
from dotenv import load_dotenv

load_dotenv()

def test_naver():
    client_id = Config.NAVER_CLIENT_ID
    client_secret = Config.NAVER_CLIENT_SECRET

    print(f"Client ID: {client_id[:4]}****" if client_id else "Client ID: MISSING")
    print(f"Client Secret: {client_secret[:4]}****" if client_secret else "Client Secret: MISSING")

    if not client_id or not client_secret:
        print("❌ CRITICAL: Naver Keys are missing in .env")
        return

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {'query': 'AI', 'display': 5}

    try:
        resp = requests.get(url, headers=headers, params=params)
        print(f"API Response Code: {resp.status_code}")
        
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            print(f"✅ Success! Found {len(items)} items.")
            for i, item in enumerate(items):
                print(f"[{i+1}] {item['title'][:30]}...")
        else:
            print(f"❌ API Failed: {resp.text}")

    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_naver()
