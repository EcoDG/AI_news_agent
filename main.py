import schedule
import time
import asyncio
import sys
from scrapers.rss_scraper import RSSScraper
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
    ]
    
    # Domestic Sources
    domestic_feeds = [
        "http://www.aitimes.com/rss/all.xml", # HTTP might work better
        "https://rss.etnews.com/Section902.xml", 
        "https://zdnet.co.kr/rss/all", # Direct RSS
    ]
    
    # 2. Fetch & Score
    print("Fetching International News...")
    intl_scraper = RSSScraper(intl_feeds, category='international')
    intl_items = intl_scraper.fetch_news()
    # Sort by score desc, then date
    intl_items.sort(key=lambda x: x['score'], reverse=True)
    top_intl = intl_items[:3]
    
    print("Fetching Domestic News...")
    dom_scraper = RSSScraper(domestic_feeds, category='domestic')
    dom_items = dom_scraper.fetch_news()
    # Sort by score desc
    dom_items.sort(key=lambda x: x['score'], reverse=True)
    top_dom = dom_items[:3]
    
    print(f"Selected {len(top_intl)} International and {len(top_dom)} Domestic items.")
    
    # 3. Process (Summarize) with LLM
    processor = ContentProcessor()
    
    print("Processing International items...")
    processed_intl = processor.process_news(top_intl)
    
    print("Processing Domestic items...")
    processed_dom = processor.process_news(top_dom)
    
    # 4. Notify
    notifier = TelegramNotifier()
    asyncio.run(notifier.send_daily_brief(processed_intl, processed_dom))
    
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
