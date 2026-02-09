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
    print("="*30)
    print(">>> RUNNING VERSION: 2026-02-09 (SIMPLIFIED) <<<")
    print(">>> IF YOU DO NOT SEE THIS, YOU ARE RUNNING OLD CODE <<<")
    print("="*30)
    
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
        # Google News is the best aggregator for "Artificial Intelligence" in Korea
        "https://news.google.com/rss/search?q=%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5+when:24h&hl=ko&gl=KR&ceid=KR:ko",
        "https://rss.etnews.com/Section902.xml", # ETNews AI
        # "http://feeds.feedburner.com/zdkorea", # ZDNet (often unstable but try)
        "https://www.hankyung.com/feed/ai", # Hankyung AI
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
    
    # 2. API (Simple v3)
    # from scrapers.api_scraper import NaverNewsScraper
    from scrapers.simple_naver import SimpleNaverScraper
    
    print("Fetching Domestic News (Naver Simple V3)...")
    naver_scraper = SimpleNaverScraper()
    dom_api_items = naver_scraper.fetch_news()
    print(f"  - Naver V3 Items: {len(dom_api_items)}")
    
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
    
    # [Diagnostic Debug] If Domestic is empty, append debug info
    if not final_dom:
        debug_msg = "\n[🔍 디버그 정보]\n"
        debug_msg += f"- Naver ID Loaded: {'YES' if Config.NAVER_CLIENT_ID else 'NO'}\n"
        debug_msg += f"- Naver Secret Loaded: {'YES' if Config.NAVER_CLIENT_SECRET else 'NO'}\n"
        debug_msg += f"- Google Key Loaded: {'YES' if Config.GOOGLE_API_KEY else 'NO'}\n"
        debug_msg += f"- Naver Error: {getattr(naver_scraper, 'last_error', 'None')}\n" # Added
        debug_msg += f"- Raw Naver items found: {len(dom_api_items)}\n"
        debug_msg += f"- Raw/Dedup/Candidate: {len(dom_api_items)}/{len(unique_dom)}/{len(candidates_dom)}"
        
        # Append as a mock item so it shows up
        final_dom.append({
            'processed_summary': debug_msg
        })

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
