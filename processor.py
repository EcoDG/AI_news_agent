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
            # Skip if API key missing
            if not Config.GOOGLE_API_KEY:
                item['processed_summary'] = item['summary'][:200]
                processed.append(item)
                continue
            
            clean_content = self._clean_text(item.get('summary', ''))
            
            # --- Scoring Agent Step ---
            try:
                score, reason = self._evaluate_relevance(item['title'], clean_content)
                item['agent_score'] = score
                item['agent_reason'] = reason
                
                print(f"  > Scoring '{item['title'][:20]}...': {score}/10")
                
                # Filter: Only keep >= 7.0
                if score < 7.0:
                    print(f"    [Skip] Score too low ({score})")
                    continue
            except Exception as e:
                print(f"Scoring failed: {e}. Defaulting to keep.")
                item['agent_score'] = 0
                item['agent_reason'] = "평가 실패 (API 오류)"

            # --- Summarization Step ---
            # Retry logic
            summary_block = None
            for attempt in range(4): # 4 attempts
                try:
                    summary_block = self._generate_v2_summary(item['title'], clean_content)
                    break # Success
                except Exception as e:
                    print(f"Attempt {attempt+1} failed for '{item['title'][:20]}': {e}")
                    time.sleep(10 * (attempt + 1)) 
            
            if not summary_block:
                summary_block = f"(번역 실패) {item['title']}\n- 요약 생성 불가 (API 한도 초과)\n- 원문 링크를 참고해주세요"

            # Add Agent Score Footer
            if 'agent_score' in item and item['agent_score'] > 0:
                summary_block += f"\n\n[🤖 에이전트 판단: {item['agent_score']}점 / {item['agent_reason']}]"

            item['processed_summary'] = summary_block
            processed.append(item)
            
            # Safety delay between items
            time.sleep(5) 
            
        # Safety Net: If everything was filtered out, allow the top candidate from original input
        if not processed and news_items:
            print("⚠️ All items filtered by Agent. Using Safety Net (Top 1).")
            rescue_item = news_items[0]
            # Mock agent score for rescue
            if 'agent_score' not in rescue_item:
                rescue_item['agent_score'] = 7.0
                rescue_item['agent_reason'] = "구조된 뉴스 (Safety Net)"
            
            clean_content = self._clean_text(rescue_item.get('summary', ''))
            rescue_item['processed_summary'] = self._generate_v2_summary(rescue_item['title'], clean_content) + \
                                               f"\n\n[🤖 에이전트 판단: {rescue_item['agent_score']}점 / {(rescue_item['agent_reason'])}]"
            processed.append(rescue_item)

        return processed

    def _evaluate_relevance(self, title: str, content: str) -> (float, str):
        """
        V4 Scoring Agent: Evaluate Practicality, Impact, Novelty
        Returns: (Average Score, One-line Reason)
        """
        prompt = f"""
        Role: 10-year IT Strategy Consultant.
        Task: Evaluate the importance of this news for Enterprise AI/AX adoption.
        
        News:
        Title: {title}
        Content: {content}
        
        Criteria (0-10):
        1. Practicality: immediate application to business/automation?
        2. Impact: Large scale or major tech giant move?
        3. Novelty: New trend/insight vs generic news?
        
        Output Format (Strictly JSON-like):
        SCORE: [Average Score float]
        REASON: [One sentence summary of why]
        """
        
        try:
            # Short timeout for scoring to save time
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Parse SCORE and REASON
            score_match = re.search(r"SCORE:\s*([\d\.]+)", text)
            reason_match = re.search(r"REASON:\s*(.+)", text, re.DOTALL)
            
            score = float(score_match.group(1)) if score_match else 5.0
            reason = reason_match.group(1).strip() if reason_match else "판단 근거 없음"
            
            return score, reason
        except Exception:
            return 8.0, "평가 불가 (Pass)" # Default to pass on error to avoid over-filtering when API is shaky

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
