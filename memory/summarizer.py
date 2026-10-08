"""
memory/summarizer.py — Conversation summarization for Friday 2.0.
Every 10 turns, compress old chat history to a concise summary to save context window.
Uses native lightweight SDKs with zero LangChain overhead.
"""
import os
from dotenv import load_dotenv
from agent_runner import SystemMessage, HumanMessage, AIMessage

load_dotenv(override=True)

_SUMMARIZE_SYSTEM = """You are a conversation summarizer. Given a conversation excerpt, produce a concise 3–5 bullet summary capturing:
- Key topics discussed
- Any decisions or actions taken
- Important user preferences or facts revealed
Return ONLY the bullet list, no preamble."""


def summarize_history(messages: list) -> str:
    """
    Summarize a list of messages into a concise text block.
    Returns empty string on failure.
    """
    if not messages:
        return ""
    try:
        # Build a plain-text transcript of the conversation
        lines = []
        for m in messages:
            content = getattr(m, "content", "")
            role = getattr(m, "role", "")
            if isinstance(m, dict):
                content = m.get("content", "")
                role = m.get("role", "")

            if role in ("user", "human"):
                lines.append(f"User: {content}")
            elif role in ("assistant", "ai"):
                lines.append(f"Sylphya: {content}")
            else:
                lines.append(f"Context: {content}")

        if not lines:
            return ""
        transcript = "\n".join(lines)
        prompt = f"Conversation to summarize:\n{transcript}"

        # 1. Try Mistral
        mistral_key = os.getenv("MISTRAL_API_KEY")
        if mistral_key:
            from mistralai.client import Mistral
            client = Mistral(api_key=mistral_key)
            resp = client.chat.complete(
                model="ministral-3b-latest",
                messages=[
                    {"role": "system", "content": _SUMMARIZE_SYSTEM},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            return (resp.choices[0].message.content or "").strip()

        # 2. Try Gemini
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=gemini_key)
            resp = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=_SUMMARIZE_SYSTEM, temperature=0.0)
            )
            return (resp.text or "").strip()

        # 3. Try Groq
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            from groq import Groq
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": _SUMMARIZE_SYSTEM},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            return (resp.choices[0].message.content or "").strip()

        return ""
    except Exception as e:
        print(f"[Summarizer] Failed: {e}")
        return ""


def maybe_compress_history(chat_history: list, turn_threshold: int = 20, keep_recent: int = 6) -> list:
    """
    If chat_history exceeds turn_threshold messages, summarize the old portion
    and return a compressed history: [SystemMessage(summary)] + last keep_recent messages.
    Otherwise returns the history unchanged.
    """
    if len(chat_history) <= turn_threshold:
        return chat_history

    old_messages = chat_history[:-keep_recent]
    recent_messages = chat_history[-keep_recent:]

    print(f"[Summarizer] Compressing {len(old_messages)} messages into summary...")
    summary_text = summarize_history(old_messages)

    if summary_text:
        compressed = [SystemMessage(content=f"[Earlier conversation summary]\n{summary_text}")] + recent_messages
        print(f"[Summarizer] Compressed to {len(compressed)} messages.")
        return compressed
    else:
        # Fallback: just keep last keep_recent * 2
        return chat_history[-(keep_recent * 2):]
