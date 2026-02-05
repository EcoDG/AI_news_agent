import telegram
import asyncio
from typing import List, Dict
from config import Config
import datetime

class TelegramNotifier:
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.bot = None
        if self.bot_token:
            self.bot = telegram.Bot(token=self.bot_token)

    async def send_daily_brief(self, intl_news: List[Dict], domestic_news: List[Dict]):
        if not self.bot or not self.chat_id:
            print("Telegram config missing.")
            return

        print("Constructing V2 Daily Brief...")
        
        # Header
        message = "📢 오늘의 AI & AX 주요 뉴스\n\n"
        
        # International Section
        message += "🌐 [해외 주요 소식]\n\n"
        for item in intl_news:
            summary_block = item.get('processed_summary', '요약 없음')
            link = item.get('link', '')
            # The summary block already contains [Translated Title] + 3 bullets
            # We just need to append the link to the last bullet or simpler:
            # The prompt format was:
            # [Title]
            # - Point 1...
            # We will append the link at the end.
            
            message += f"{summary_block} 🔗 링크: {link}\n\n"
            
        # Domestic Section
        message += "🇰🇷 [국내 주요 소식]\n\n"
        for item in domestic_news:
            summary_block = item.get('processed_summary', '요약 없음')
            link = item.get('link', '')
            message += f"{summary_block} 🔗 링크: {link}\n\n"
            
        # Send
        try:
            # Telegram has a char limit (4096), but 6 items should fit.
            # If too long, we might need to split, but assuming it fits for now.
            await self.bot.send_message(chat_id=self.chat_id, text=message)
            print("Message sent successfully.")
        except Exception as e:
            print(f"Failed to send message: {e}")
