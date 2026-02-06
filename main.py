import schedule
import time
import asyncio
import sys
from scrapers.rss_scraper import RSSScraper
from scrapers.api_scraper import NaverNewsScraper
from processor import ContentProcessor
from notifier import TelegramNotifier
from config import Config

def job():
    print("=== Starting V2 Job ===")
    
    # 1. Define Sources (V2)
    # International Sources
    intl_feeds = [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://venturebeat.com/category/ai/feed/",
        "https://www.artificialintelligence-news.com/feed/",
        "https://feeds.bloomberg.com/markets/news.rss", # Added Bloomberg
    ]
    
    # Domestic Sources (RSS)
    domestic_feeds = [
        "https://www.aitimes.com/rss/allSection.xml", # Updated URL
        "https://rss.etnews.com/Section902.xml", 
        "https://zdnet.co.kr/rss/all", 
    ]
    
    # 2. Fetch & Score
    print("Fetching International News...")
    intl_scraper = RSSScraper(intl_feeds, category='international')
    intl_items = intl_scraper.fetch_news()
    intl_items.sort(key=lambda x: x['score'], reverse=True)
    candidates_intl = intl_items[:6] # Send top 6 to Agent
    
    print("Fetching Domestic News (RSS + Naver API)...")
    # 1. RSS
    dom_scraper = RSSScraper(domestic_feeds, category='domestic')
    dom_rss_items = dom_scraper.fetch_news()
    print(f"  - RSS Items: {len(dom_rss_items)}")
    
    # 2. API
    naver_scraper = NaverNewsScraper()
    dom_api_items = naver_scraper.fetch_news()
    print(f"  - Naver Items: {len(dom_api_items)}")
    
    # Merge & Deduplicate
    all_dom_items = dom_rss_items + dom_api_items
    unique_dom = []
    seen_titles = set()
    
    for item in all_dom_items:
        # Normalize title for dedup
        norm_title = item['title'].replace(' ', '').lower()
        if norm_title not in seen_titles:
            unique_dom.append(item)
            seen_titles.add(norm_title)
            
    # Sort by keyword score
    unique_dom.sort(key=lambda x: x.get('score', 0), reverse=True)
    candidates_dom = unique_dom[:6] # Send top 6 to Agent
    
    print(f"Candidates for Agent Scoring: {len(candidates_intl)} Intl, {len(candidates_dom)} Domestic.")
    
    # 3. Process (Agent Scoring + Summarize)
    processor = ContentProcessor()
    
    print("Agent evaluating International items...")
    processed_intl = processor.process_news(candidates_intl)
    final_intl = processed_intl[:3] # Pick Top 3 Survivors
    
    print("Agent evaluating Domestic items...")
    processed_dom = processor.process_news(candidates_dom)
    final_dom = processed_dom[:3] # Pick Top 3 Survivors
    
    # 4. Notify
    notifier = TelegramNotifier()
    asyncio.run(notifier.send_daily_brief(final_intl, final_dom))
    
    print("=== Job Finished ===")

def main():
    Config.validate()
    print("AI News Agent V2 Started. Waiting for schedule (Daily 09:00)...")
    
    schedule.every().day.at("09:00").do(job)
    
    # Also run once immediately for testing if argument provided
    if len(sys.argv) > 1 and (sys.argv[1] == "--run-now" or sys.argv[1] == "--once"):
        job()
        if sys.argv[1] == "--once":
            return # Exit main, thus exiting the script
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
