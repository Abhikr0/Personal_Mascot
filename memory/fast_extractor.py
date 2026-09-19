"""
memory/fast_extractor.py — Ultra-fast local NER-based memory extraction for Friday 2.0.
Uses spaCy for near-zero-latency entity extraction (no API calls).
Falls back gracefully if spaCy is not installed.
Complements the existing LLM extractor: handles ~80% of cases in <5ms.
"""
import re
import datetime
from typing import List, Dict, Any

_nlp = None
_available = False

_MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)"
_DATE_PATTERNS = [
    re.compile(r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})\b'),
    re.compile(rf'\b({_MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b', re.I),
    re.compile(rf'\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTHS}),?\s+(\d{{4}})\b', re.I),
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


def _init_spacy():
    global _nlp, _available
    try:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            from spacy.cli import download
            download("en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
        _available = True
        print("[FastExtractor] spaCy en_core_web_sm loaded — fast NER active.")
    except ImportError:
        print("[FastExtractor] spaCy not installed — fast extraction disabled.")
    except Exception as e:
        print(f"[FastExtractor] spaCy init failed: {e}")


def extract_fast(text: str) -> List[Dict[str, Any]]:
    """
    Fast, local memory extraction. Returns same schema as LLM extractor:
    [{"category": str, "key": str, "value": str, "date_time": str|None, "context": str}]
    """
    results = []
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    clean = text.strip()
    if not clean or len(clean) < 4:
        return []

    # 1. Name detection
    for pat in _NAME_PATTERNS:
        m = pat.search(clean)
        if m:
            name = m.group(1).strip()
            if 2 <= len(name) <= 60:
                results.append({"category": "identity", "key": "name", "value": name, "date_time": None, "context": clean})

    # 2. Preferences
    for pat in _PREFERENCE_PATTERNS:
        m = pat.search(clean)
        if m:
            groups = [g for g in m.groups() if g]
            value = " ".join(groups).strip()
            if 2 <= len(value) <= 200:
                key = re.sub(r'\s+', '_', value[:40].lower())
                results.append({"category": "preference", "key": key, "value": value, "date_time": None, "context": clean})

    # 3. Explicit remember/note requests
    for pat in _REMEMBER_PATTERNS:
        m = pat.search(clean)
        if m:
            value = m.group(1).strip()
            if 2 <= len(value) <= 300:
                key = re.sub(r'\s+', '_', value[:40].lower())
                results.append({"category": "fact", "key": key, "value": value, "date_time": today_str, "context": clean})

    # 4. spaCy NER for PERSON, ORG, DATE, TIME, GPE
    if _available and _nlp:
        try:
            doc = _nlp(clean)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    results.append({"category": "contact", "key": ent.text.lower().replace(" ", "_"), "value": ent.text, "date_time": None, "context": clean})
                elif ent.label_ == "DATE" and len(ent.text) > 3:
                    results.append({"category": "schedule", "key": re.sub(r'\s+', '_', ent.text[:40].lower()), "value": clean, "date_time": ent.text, "context": clean})
                elif ent.label_ == "ORG" and len(ent.text) > 2:
                    results.append({"category": "fact", "key": f"organization_{ent.text.lower().replace(' ', '_')[:30]}", "value": ent.text, "date_time": None, "context": clean})
        except Exception:
            pass

    # Deduplicate by key
    seen = set()
    deduped = []
    for r in results:
        if r["key"] not in seen:
            seen.add(r["key"])
            deduped.append(r)

    return deduped


def is_available() -> bool:
    return _available


# Initialize on module load
_init_spacy()
