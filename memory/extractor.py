import os
import json
import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv(override=True)

EXTRACTION_SYSTEM_PROMPT = """Extract durable personal info (identity, schedule/dates, preferences, contacts, notes) from text.
Ignore transient commands, small talk, and temporary questions. Return [] if none.
Return JSON array: [{"category": "identity|schedule|preference|contact|fact", "key": "short_key", "value": "info", "date_time": "date/time or null"}]"""



class MemoryExtractor:
    def __init__(self):
        mistral_key = os.getenv("MISTRAL_API_KEY")
        if mistral_key:
            self.llm = ChatMistralAI(
                model="open-mistral-nemo",
                api_key=mistral_key,
                temperature=0.0
            )
        else:
            api_key = os.getenv("GEMINI_API_KEY")
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-flash-lite-latest",
                google_api_key=api_key,
                temperature=0.0
            )

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
            
            messages = [
                SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            raw = response.content
            if isinstance(raw, list):
                raw = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in raw])
            raw = str(raw).strip()

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
