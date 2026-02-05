import google.generativeai as genai
from config import Config
from typing import Dict, List
import re
import time
import random

class ContentProcessor:
    def __init__(self):
        self.client = None
        if Config.GOOGLE_API_KEY:
            genai.configure(api_key=Config.GOOGLE_API_KEY)
            # Fallback to flash-latest (might be 1.5 or 2.0 but hopes for different quota)
            self.model = genai.GenerativeModel('gemini-flash-latest')
        else:
            print("Google API Key missing. Summarization will be skipped/mocked.")

    def process_news(self, news_items: List[Dict]) -> List[Dict]:
        processed = []
        for item in news_items:
            if not Config.GOOGLE_API_KEY:
                item['processed_summary'] = item['summary'][:200]
                processed.append(item)
                continue
            
            clean_content = self._clean_text(item.get('summary', ''))
            
            # Retry logic
            summary_block = None
            for attempt in range(4): # 4 attempts
                try:
                    summary_block = self._generate_v2_summary(item['title'], clean_content)
                    break # Success
                except Exception as e:
                    print(f"Attempt {attempt+1} failed for '{item['title'][:20]}': {e}")
                    time.sleep(10 * (attempt + 1)) # Aggressive backoff: 10, 20, 30
            
            if not summary_block:
                summary_block = f"(번역 실패) {item['title']}\n- 요약 생성 불가 (API 한도 초과)\n- 원문 링크를 참고해주세요"

            item['processed_summary'] = summary_block
            processed.append(item)
            
            # Safety delay between items
            time.sleep(10) # 6 RPM max 
            
        return processed

    def _clean_text(self, text: str) -> str:
        text = re.sub('<[^<]+?>', '', text)
        return text.strip()

    def _generate_v2_summary(self, title: str, content: str) -> str:
        prompt = f"""
        Role: Professional Tech News Editor for Korean Audience.
        
        Input:
        Title: {title}
        Content: {content}

        Instructions:
        1. **TRANSLATE** the title into natural Korean. (CRITICAL)
        2. **SUMMARIZE** the key points into exactly 3 Korean bullet points.
        3. IGNORE marketing fluff, focus on facts (What, Who, Why).
        4. If the content is too short, perform a best-effort summary based on title.

        Output Format (Strictly follow this):
        [Korean Title]
        - Point 1 (Korean)
        - Point 2 (Korean)
        - Point 3 (Korean)
        """
        
        response = self.model.generate_content(prompt)
        # Check if response was blocked
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            raise Exception(f"Blocked: {response.prompt_feedback.block_reason}")
            
        return response.text.strip()
