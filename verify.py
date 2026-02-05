import asyncio
from scrapers.rss_scraper import RSSScraper
from scrapers.api_scraper import HackerNewsScraper
from processor import ContentProcessor
from notifier import TelegramNotifier
from config import Config

def test_fetch():
    print("Testing RSS Fetch...")
    rss = RSSScraper(["https://openai.com/blog/rss.xml"])
    items = rss.fetch_news()
    print(f"Fetched {len(items)} items from OpenAI.")
    if items:
        print(f"Sample: {items[0]['title']}")

    print("\nTesting HN Fetch...")
    hn = HackerNewsScraper()
    items = hn.fetch_news()
    print(f"Fetched {len(items)} items from HN.")
    if items:
        print(f"Sample: {items[0]['title']}")

    return items[:1] if items else []

def test_process(item):
    print("\nTesting Processor (Requires OpenAI Key)...")
    processor = ContentProcessor()
    if not Config.ANTHROPIC_API_KEY:
        print("Skipping LLM test (No Key)")
        return item
    
    processed = processor.process_news([item])
    print(f"Processed summary: {processed[0].get('processed_summary')}")
    return processed[0]

async def test_notify(item):
    print("\nTesting Telegram (Requires Token)...")
    notifier = TelegramNotifier()
    if not Config.TELEGRAM_BOT_TOKEN:
        print("Skipping Telegram test (No Token)")
        return
    
    await notifier.send_news([item])
    print("Message sent (check your bot).")

if __name__ == "__main__":
    print("=== START VERIFICATION ===")
    items = test_fetch()
    if items:
        processed_item = test_process(items[0])
        asyncio.run(test_notify(processed_item))
    print("=== END VERIFICATION ===")
