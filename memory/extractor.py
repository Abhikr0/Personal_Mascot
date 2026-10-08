import os
import json
import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)

EXTRACTION_SYSTEM_PROMPT = """Extract durable personal info (identity, schedule/dates, preferences, contacts, notes) from text.
Ignore transient commands, small talk, and temporary questions. Return [] if none.
Return JSON array: [{"category": "identity|schedule|preference|contact|fact", "key": "short_key", "value": "info", "date_time": "date/time or null"}]"""


class MemoryExtractor:
    def __init__(self):
        pass

    def _call_llm(self, prompt: str) -> str:
        # 1. Try Mistral
        mistral_key = os.getenv("MISTRAL_API_KEY")
        if mistral_key:
            from mistralai.client import Mistral
            client = Mistral(api_key=mistral_key)
            resp = client.chat.complete(
                model="open-mistral-nemo",
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            return resp.choices[0].message.content or ""

        # 2. Try Gemini
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=gemini_key)
            resp = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTION_SYSTEM_PROMPT,
                    temperature=0.0
                )
            )
            return resp.text or ""

        # 3. Try Groq
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            from groq import Groq
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            return resp.choices[0].message.content or ""

        return ""

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Analyze text and extract structured memory entities. Returns empty list if nothing durable."""
        clean_text = text.strip()
        if not clean_text or len(clean_text) < 4:
            return []

        # Fast heuristic pre-check to save API calls on obvious transient single commands and chit-chat
        lower = clean_text.lower()
        transient_starts = [
            "open ", "launch ", "close ", "kill ", "turn up ", "turn down ",
            "mute", "unmute", "volume ", "minimize ", "maximize ", "scroll ",
            "type ", "click ", "take a screenshot", "search google ", "search web ",
            "play ", "can you open", "can you play", "how are you", "what time",
            "hello", "hi ", "hey ", "yeah", "it's nothing", "nothing"
        ]
        durable_keywords = ["remember", "save", "note", "my name", "birthday", "meeting", "appointment", "prefer", "favorite", "i like", "i am", "call me"]
        if any(lower.startswith(prefix) for prefix in transient_starts) and not any(k in lower for k in durable_keywords):
            return []

        try:
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            user_prompt = f"Date: {today_str}\nText: {clean_text}"

            raw = self._call_llm(user_prompt).strip()
            if not raw:
                return []

            # Clean markdown code blocks
            if "```json" in raw:
                raw = raw.split("```json", 1)[1]
                if "```" in raw:
                    raw = raw.split("```", 1)[0]
            elif "```" in raw:
                raw = raw.split("```", 1)[1]
                if "```" in raw:
                    raw = raw.split("```", 1)[0]
            raw = raw.strip()

            start_idx = raw.find('[')
            end_idx = raw.rfind(']')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = raw[start_idx:end_idx+1]
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    valid_items = []
                    for item in parsed:
                        if isinstance(item, dict) and "key" in item and "value" in item:
                            valid_items.append({
                                "category": str(item.get("category", "fact")).lower(),
                                "key": str(item.get("key", "")).strip().lower().replace(" ", "_"),
                                "value": str(item.get("value", "")).strip(),
                                "date_time": str(item.get("date_time")).strip() if item.get("date_time") else None,
                                "context": clean_text
                            })
                    return valid_items
            return []

        except Exception as e:
            print(f"[MEMORY EXTRACTOR ERROR] {e}")
            return []


# Global extractor instance
memory_extractor = MemoryExtractor()
