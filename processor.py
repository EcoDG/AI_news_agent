import google.generativeai as genai
from openai import OpenAI
from config import Config
from typing import Dict, List
import re
import time
import random
import json

class ContentProcessor:
    def __init__(self):
        self.client = None
        if Config.GOOGLE_API_KEY:
            genai.configure(api_key=Config.GOOGLE_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-flash') # Stable version
        else:
            print("Google API Key missing. Summarization will be skipped/mocked.")
        
        # Initialize OpenAI Client (Lazy load or check key)
        self.openai_client = None
        if Config.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)

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
                score, reason, action = self._evaluate_relevance(item['title'], clean_content)
                item['agent_score'] = score
                item['agent_reason'] = reason
                item['agent_action'] = action
                
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
                # [Graceful Fallback] If all LLMs fail, show raw content instead of error
                fallback_text = clean_content[:300] if clean_content else "원문 링크를 참고해주세요."
                summary_block = f"{item['title']}\n{fallback_text}...\n\n[⚠️ AI 요약 불가: 원문 미리보기]"

            # Add Agent Score Footer
            if 'agent_score' in item and item['agent_score'] > 0:
                summary_block += f"\n\n[🤖 에이전트 판단: {item['agent_score']}점]\n- 이유: {item['agent_reason']}\n- 실행: {item.get('agent_action', '없음')}"

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

    def _evaluate_relevance(self, title: str, content: str) -> (float, str, str):
        """
        V4 Scoring Agent v3.0: AX Implementation Lead Persona
        Returns: (Score, Reason, Action Item)
        """
        prompt = f"""
        # AI/AX News Scoring Prompt v3.0
        
        ## Role
        You are an **AX (AI Transformation) Lead** at a large enterprise.
        
        ## Task
        Score this news article based on: **"Will this help me do my AX job better TODAY or THIS WEEK?"**
        
        ## News
        Title: {title}
        Content: {content}

        ## Evaluation Criteria (0-10 scale)

        ### 🛠️ TIER 1: Tool/Product Updates (Most Important)
        **10 points - MUST READ:** Major model releases (GPT-5, Claude Opus), Significant feature updates, Critical issues.
        **7 points - IMPORTANT:** Minor updates, Benchmarks, Pricing changes.
        **Specific Tool Checklist:** Claude, OpenAI, Cursor, Windsurf, n8n, Zapier, Microsoft Copilot. (If YES -> +3 points)

        ### 🏢 TIER 2: Enterprise Implementation
        **10 points - MUST READ:** Specific metrics (ROI, time saved), Detailed process.
        **7 points - IMPORTANT:** Case study with clear methodology, C-level strategy.
        **Examples:** "Time saved 40%", "Cost reduction"

        ### 📊 TIER 3: Industry Insights
        **10 points:** Analyst reports (Gartner) with data, ROI studies.
        **7 points:** Expert analysis, Regulatory updates.

        ## RED FLAGS (Auto-reject 0 points)
        - No mention of specific tools/companies
        - Abstract future predictions / Ethics debates
        - General hiring/stock news

        ## Output Format (JSON)
        {{
          "score": 8.5,
          "category": "TOOL_UPDATE | CASE_STUDY | INSIGHT",
          "relevance": "HIGH | MEDIUM | LOW",
          "reason": "[1-line Korean summary of why this matters for AX practitioners]",
          "action_item": "[What you can do with this info: e.g., '팀 미팅에서 도구 전환 검토 필요']",
          "decision": "ACCEPT | REJECT"
        }}
        """
        
        try:
            # Call Robust Generation
            text = self._generate_content_robust(prompt)
            
            # JSON Parsing Logic
            # Strip markdown code blocks if present
            clean_json = re.sub(r"```json", "", text)
            clean_json = re.sub(r"```", "", clean_json).strip()
            
            data = json.loads(clean_json)
            
            score = float(data.get('score', 0))
            reason = data.get('reason', "판단 근거 없음")
            action = data.get('action_item', "참고")
            
            return score, reason, action
        except Exception as e:
            print(f"Scoring Error: {e}")
            return 8.0, "평가 불가 (Pass)", "내용 확인 필요" # Default to pass on error

    def _clean_text(self, text: str) -> str:
        text = re.sub('<[^<]+?>', '', text)
        return text.strip()

    def _generate_content_robust(self, prompt: str) -> str:
        """
        Try Gemini (with retries) -> If 429/Exhausted -> Try OpenAI
        """
        # 1. Try Gemini with Retries
        if self.model:
            for attempt in range(3): # Try 3 times
                try:
                    response = self.model.generate_content(prompt)
                    # Check if response was blocked
                    if response.prompt_feedback and response.prompt_feedback.block_reason:
                        raise Exception(f"Blocked by Gemini: {response.prompt_feedback.block_reason}")
                    return response.text.strip()
                except Exception as e:
                    error_str = str(e)
                    # If it's the last attempt, check if we should fallback
                    if attempt == 2:
                        print(f"⚠️ Gemini failed after 3 attempts: {e}")
                        break # Exit loop to trigger fallback
                        
                    # If quota related, wait and retry
                    if "429" in error_str or "ResourceExhausted" in error_str:
                        print(f"⚠️ Gemini Rate Limit (Attempt {attempt+1}/3). Waiting 20s...")
                        time.sleep(20)
                    else:
                        print(f"⚠️ Gemini Error (Attempt {attempt+1}/3): {e}. Waiting 5s...")
                        time.sleep(5)

        # 2. Fallback to OpenAI
        print("🔄 Switching to OpenAI Fallback...")
        return self._call_openai_fallback(prompt)

    def _call_openai_fallback(self, prompt: str) -> str:
        if not self.openai_client:
            print("❌ OpenAI Key missing. Cannot fallback.")
            raise Exception("All LLMs failed & no fallback key.")
            
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini", # Cost efficient
                messages=[
                    {"role": "system", "content": "You are a helpful AI news assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ OpenAI Fallback failed: {e}")
            raise e

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
        
        try:
            return self._generate_content_robust(prompt)
        except Exception as e:
            self.last_error = str(e) # Store error for debugging
            print(f"Summary generation failed: {e}")
            return None
