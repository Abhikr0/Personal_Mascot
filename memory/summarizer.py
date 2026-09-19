"""
memory/summarizer.py — Conversation summarization for Friday 2.0.
Every 10 turns, compress old chat history to a concise summary to save context window.
Uses the cheapest/fastest available LLM.
"""
import os
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv(override=True)

_SUMMARIZE_SYSTEM = """You are a conversation summarizer. Given a conversation excerpt, produce a concise 3–5 bullet summary capturing:
- Key topics discussed
- Any decisions or actions taken
- Important user preferences or facts revealed
Return ONLY the bullet list, no preamble."""


def get_summarizer_llm():
    mistral_key = os.getenv("MISTRAL_API_KEY")
    if mistral_key:
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(model="ministral-3b-latest", api_key=mistral_key, temperature=0.0)
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-flash-lite-latest", google_api_key=gemini_key)
    return None


def summarize_history(messages: list) -> str:
    """
    Summarize a list of LangChain messages into a concise text block.
    Returns empty string on failure.
    """
    if not messages:
        return ""
    try:
        llm = get_summarizer_llm()
        if llm is None:
            return ""
        # Build a plain-text transcript of the conversation
        lines = []
        for m in messages:
            if isinstance(m, HumanMessage):
                content = m.content if isinstance(m.content, str) else str(m.content)
                lines.append(f"User: {content}")
            elif isinstance(m, AIMessage):
                content = m.content if isinstance(m.content, str) else str(m.content)
                lines.append(f"Sylphya: {content}")
        if not lines:
            return ""
        transcript = "\n".join(lines)
        resp = llm.invoke([
            SystemMessage(content=_SUMMARIZE_SYSTEM),
            HumanMessage(content=f"Conversation to summarize:\n{transcript}")
        ])
        result = resp.content if isinstance(resp.content, str) else str(resp.content)
        return result.strip()
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
