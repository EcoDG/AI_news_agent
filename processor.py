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
                # [Graceful Fallback] Title Only
                last_error = getattr(self, 'last_error', 'Unknown Error')
                if "Korean" in item.get('source', ''): # If domestic
                     summary_block = item['title']
                else:
                     summary_block = f"{item['title']} (번역 실패)"
                
                # Append error as debug note? User wants clean output.
                # summary_block += f"\n[Debug: {last_error}]" 
                # Let's hide error if user wants clean output, or keep it subtle.
                pass

            # Add Agent Score Footer (Compact)
            if 'agent_score' in item and item['agent_score'] > 0:
                summary_block += f"\n[💡 AI 점수: {item['agent_score']} / {item['agent_reason']}]"

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
            print(f"Debug Raw Text: {text[:100]}...") # Debug log

            # Robust JSON Extraction
            # Find the substring that looks like a JSON object: { ... }
            json_match = re.search(r'(\{.*\})', text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Try to fix common JSON errors (newline in string)
                    json_str = json_str.replace('\n', ' ')
                    data = json.loads(json_str)
            else:
                # Fallback if no {} found
                print(f"⚠️ No JSON found in response. Text: {text[:50]}...")
                # Trigger heuristic instead of raising generic error
                h_score, h_reason, h_action = self._heuristic_score(title, content)
                return h_score, h_reason, h_action
            
            score = float(data.get('score', 0))
            reason = data.get('reason', "판단 근거 없음")
            action = data.get('action_item', "참고")
            
            return score, reason, action

        except Exception as e:
            print(f"Scoring Error: {e} | Fallback to Heuristic")
            h_score, h_reason, h_action = self._heuristic_score(title, content)
            return h_score, h_reason, h_action

    def _heuristic_score(self, title: str, content: str) -> (float, str, str):
        """
        Fallback scoring based on Keyword Matching when LLM fails.
        """
        text = (title + " " + content).lower()
        
        # Tier S Keywords (+9.0)
        tier_s = ["claude", "gemini", "gpt-5", "gpt-4", "cursor", "windsurf", "agent", "opus"]
        for kw in tier_s:
            if kw in text:
                return 9.0, f"주요 키워드 감지 ({kw}) - API 대체 평가", "내용 확인 요망"
        
        # Tier A Keywords (+8.0)
        tier_a = ["automation", "workflow", "enterprise", "기업", "자동화", "도입", "사례"]
        for kw in tier_a:
            if kw in text:
                return 8.0, f"관련 키워드 감지 ({kw}) - API 대체 평가", "업무 활용 가능성 있음"
                
        # Default Pass
        return 7.5, "기본 점수 (API 오류로 인한 통과)", "참고"

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
        # Complete Translation & Summary Prompt v3.0

        ## Role
        You are a **Professional Tech News Editor** for Korean AX practitioners.

        ## Your Mission
        Transform English tech news into **natural Korean** that reads like it was originally written by a Korean tech journalist at 테크크런치 or 블로터.

        ## Input
        Title: {title}
        Content: {content}

        ---

        ## CRITICAL RULES

        ### Language
        - **ALL output must be in Korean**
        - NO English except:
          - Product names (Claude, GPT-4, Cursor)
          - Well-known acronyms (LLM, ROI, API, SaaS)
          - Company names when commonly written in English (OpenAI, Microsoft)

        ### Translation Quality Standards

        **1. Natural Korean (자연스러운 한국어)**
        ❌ "~입니다", "~되었습니다" (formal written)
        ✅ "~임", "~됨" or 체언종결 (professional brief)

        ❌ "~것으로 나타났다", "~라고 발표했다"
        ✅ Direct statement (불필요한 인용 구조 제거)

        **2. Technical Terms (Consistency Table)**
        | English | Korean (USE) | 금지어 |
        |---------|--------------|--------|
        | AI Agent | AI 에이전트 | AI 에이전트들, 에이전트 솔루션 |
        | Implementation | 도입, 적용 | 구현, 이행 |
        | Workflow | 워크플로 | 작업 흐름, 업무 흐름 |
        | Case Study | 사례 | 케이스 스터디 |
        | ROI | ROI | 투자수익률 |
        | Deploy | 배포 | 디플로이 |
        | Enterprise | 기업, 엔터프라이즈 | 엔터프라이즈급 |

        **3. Numbers & Metrics**
        - Percentage: 50% (no space)
        - Money: 1,000만 달러, 100억 원
        - Time: 3개월, 2주, 6시간
        - Dates: 2024년 3분기, 2025년 2월

        ---

        ## Output Format
        Just the **Korean Translated Title**.
        - Do NOT include original English title.
        - Do NOT add bullets or summary.
        - Do NOT add "Title:" prefix.
        - Keep it under 80 characters.
        """
        
        try:
            # For domestic news, if it's alread Korean, just return it? 
            # But the input 'content' might be English for international.
            # We rely on the LLM to detect.
             return self._generate_content_robust(prompt)
        except Exception as e:
            self.last_error = str(e) # Store error for debugging
            print(f"Summary generation failed: {e}")
            return None
