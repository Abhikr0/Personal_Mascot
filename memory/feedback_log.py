"""
memory/feedback_log.py — Interaction feedback logging for Friday 2.0 ML self-improvement.
Logs every interaction with metadata. Thumbs up/down signals stored for future fine-tuning.
"""
import os
import sys
import json
import datetime
from typing import Optional

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_dir = os.path.join(base_dir, "data")
os.makedirs(data_dir, exist_ok=True)
LOG_PATH = os.path.join(data_dir, "interaction_log.jsonl")


def log_interaction(
    user_input: str,
    assistant_reply: str,
    emotion: str,
    intensity: float,
    tools_used: list,
    latency_ms: float,
    model_used: str = "",
    positive: Optional[bool] = None,
):
    """Append an interaction record to the JSONL log."""
    record = {
        "ts": datetime.datetime.now().isoformat(),
        "input": user_input,
        "reply": assistant_reply,
        "emotion": emotion,
        "intensity": round(intensity, 3),
        "tools": [t.get("name", "") if isinstance(t, dict) else str(t) for t in tools_used],
        "latency_ms": round(latency_ms, 1),
        "model": model_used,
        "feedback": positive,  # None = no feedback, True = thumbs up, False = thumbs down
    }
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[FeedbackLog] Write error: {e}")


def log_feedback(reply_text: str, positive: bool):
    """Retroactively mark the most recent matching reply with feedback."""
    if not os.path.exists(LOG_PATH):
        return
    try:
        lines = []
        updated = False
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        # Walk backwards to find the most recent matching reply
        for i in range(len(all_lines) - 1, -1, -1):
            record = json.loads(all_lines[i])
            if not updated and record.get("reply", "") == reply_text and record.get("feedback") is None:
                record["feedback"] = positive
                all_lines[i] = json.dumps(record, ensure_ascii=False) + "\n"
                updated = True
                break
        if updated:
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(all_lines)
            print(f"[FeedbackLog] Marked feedback={'positive' if positive else 'negative'} for: {reply_text[:60]}")
    except Exception as e:
        print(f"[FeedbackLog] Feedback update error: {e}")


def get_stats() -> dict:
    """Return basic stats: total interactions, positive/negative feedback counts."""
    if not os.path.exists(LOG_PATH):
        return {"total": 0, "positive": 0, "negative": 0, "no_feedback": 0}
    total = positive = negative = no_fb = 0
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    total += 1
                    fb = r.get("feedback")
                    if fb is True: positive += 1
                    elif fb is False: negative += 1
                    else: no_fb += 1
                except Exception:
                    pass
    except Exception:
        pass
    return {"total": total, "positive": positive, "negative": negative, "no_feedback": no_fb}
