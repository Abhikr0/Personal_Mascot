"""
memory/fast_extractor.py — Ultra-fast, lightweight rule & regex memory extraction for Friday 2.0.
100% Python standard library (re, datetime).
Zero heavy dependencies, 0MB RAM overhead, sub-millisecond execution.
Complements the cloud LLM extractor: handles common extraction cases instantly with 0 CPU impact.
"""
import re
import datetime
from typing import List, Dict, Any

_MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)"

_DATE_PATTERNS = [
    re.compile(r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})\b'),
    re.compile(rf'\b({_MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s*(\d{{4}})?\b', re.I),
    re.compile(rf'\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTHS}),?\s*(\d{{4}})?\b', re.I),
    re.compile(r'\b(?:tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month))\b', re.I),
]

_PREFERENCE_PATTERNS = [
    re.compile(r"(?:i\s+)?(?:like|love|prefer|enjoy|hate|dislike|can't stand)\s+(.+?)(?:\.|,|$)", re.I),
    re.compile(r"my\s+(?:favorite|favourite)\s+(\w+)\s+is\s+(.+?)(?:\.|,|$)", re.I),
]

_NAME_PATTERNS = [
    re.compile(r"(?:call me|my name is|i am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.I),
    re.compile(r"(?:my name is|i'm called)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.I),
]

_REMEMBER_PATTERNS = [
    re.compile(r"(?:remember|note|save|don't forget)(?:\s+that)?\s+(.+?)(?:\.|$)", re.I),
]

_CONTACT_PATTERNS = [
    re.compile(r"(?:my\s+(?:friend|colleague|brother|sister|mother|father|boss|manager|partner))\s+([A-Z][a-z]+)", re.I),
    re.compile(r"(?:reach|contact|email|call)\s+([A-Z][a-z]+)\s+at\s+([^\s,]+)", re.I),
]


def extract_fast(text: str) -> List[Dict[str, Any]]:
    """
    Fast, local, zero-dependency memory extraction.
    Returns schema:
    [{"category": str, "key": str, "value": str, "date_time": str|None, "context": str}]
    """
    results: List[Dict[str, Any]] = []
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    clean = text.strip()
    if not clean or len(clean) < 4:
        return []

    # 1. Identity / Name detection
    for pat in _NAME_PATTERNS:
        m = pat.search(clean)
        if m:
            name = m.group(1).strip()
            if 2 <= len(name) <= 60 and name.lower() not in ("sylphya", "friday", "sir", "here", "ready"):
                results.append({"category": "identity", "key": "name", "value": name, "date_time": None, "context": clean})
                break

    # 2. Preferences
    for pat in _PREFERENCE_PATTERNS:
        m = pat.search(clean)
        if m:
            groups = [g for g in m.groups() if g]
            value = " ".join(groups).strip()
            if 2 <= len(value) <= 200:
                key = re.sub(r'[\s\W]+', '_', value[:40].lower()).strip('_')
                if key:
                    results.append({"category": "preference", "key": key, "value": value, "date_time": None, "context": clean})

    # 3. Explicit remember/note requests
    for pat in _REMEMBER_PATTERNS:
        m = pat.search(clean)
        if m:
            value = m.group(1).strip()
            if 2 <= len(value) <= 300:
                key = re.sub(r'[\s\W]+', '_', value[:40].lower()).strip('_')
                if key:
                    results.append({"category": "fact", "key": key, "value": value, "date_time": today_str, "context": clean})

    # 4. Schedule / Dates detection
    for pat in _DATE_PATTERNS:
        m = pat.search(clean)
        if m:
            date_match = m.group(0).strip()
            key = f"event_{re.sub(r'[\s\W]+', '_', date_match.lower()).strip('_')}"
            results.append({"category": "schedule", "key": key, "value": clean, "date_time": date_match, "context": clean})
            break

    # 5. Contact detection
    for pat in _CONTACT_PATTERNS:
        m = pat.search(clean)
        if m:
            contact_name = m.group(1).strip()
            contact_val = clean if len(m.groups()) < 2 else f"{contact_name}: {m.group(2)}"
            key = f"contact_{re.sub(r'[\s\W]+', '_', contact_name.lower()).strip('_')}"
            results.append({"category": "contact", "key": key, "value": contact_val, "date_time": None, "context": clean})

    # Deduplicate results by key
    seen = set()
    deduped = []
    for r in results:
        if r["key"] not in seen:
            seen.add(r["key"])
            deduped.append(r)

    return deduped


def is_available() -> bool:
    """Fast regex extractor is always available with 0 dependencies."""
    return True
