import datetime, os, webbrowser, subprocess, json, pyautogui, trafilatura
from typing import Optional
from duckduckgo_search import DDGS

def get_current_time():
    return f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

def web_search(query):
    try:
        with DDGS() as ddgs:
            res = [f"{r['title']}: {r['href']}" for r in ddgs.text(query, max_results=3)]
        return f"Results for '{query}':\n" + "\n".join(res) if res else "No results, Sir."
    except Exception as e: return f"Search Error: {e}"

def execute_shell_command(command):
    try:
        p = subprocess.run(command, shell=True, capture_output=True, text=True)
        return f"Out: {p.stdout or 'Done'}" if p.returncode == 0 else f"Err: {p.stderr}"
    except Exception as e: return f"Cmd Error: {e}"

def open_youtube(query: Optional[str] = None):
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}" if query else "https://www.youtube.com"
    try:
        webbrowser.open(url)
        return f"Opened YouTube {f'for {query}' if query else ''}."
    except Exception as e: return f"YT Error: {e}"

def ui_interact(action: str, text=None, x=None, y=None, app=None):
    try:
        if action == "click": pyautogui.click(x, y) if x is not None else pyautogui.click()
        elif action == "type": pyautogui.write(text, interval=0.1) if text else None
        elif action == "move": pyautogui.moveTo(x, y, duration=0.5) if x is not None else None
        elif action == "close_tab": pyautogui.hotkey('ctrl', 'w')
        elif action == "close_app": 
            if app: subprocess.run(f"taskkill /f /im {app}.exe", shell=True)
            else: pyautogui.hotkey('alt', 'f4')
        return f"UI {action} done."
    except Exception as e: return f"UI Error: {e}"

def smart_browser_interact(target: str):
    try:
        target = target.lower()
        if "video" in target:
            presses = 15 if "second" in target else 14
            pyautogui.press('tab', presses=presses, interval=0.05)
            pyautogui.press('enter')
            return f"Selected {target}."
        elif "title" in target or "click" in target:
            txt = target.replace("click video with title", "").replace("click video named", "").replace("click", "").strip()
            if txt:
                pyautogui.hotkey('ctrl', 'f'); pyautogui.write(txt, interval=0.05); pyautogui.press(['esc', 'enter'])
                return f"Clicked '{txt}' via search."
        return f"Unknown interaction: {target}"
    except Exception as e: return f"Smart Error: {e}"

def click_text_on_screen(text: str):
    try:
        pyautogui.hotkey('ctrl', 'f'); pyautogui.write(text, interval=0.05); pyautogui.press(['esc', 'enter'])
        return f"Clicked '{text}'."
    except Exception as e: return f"Click Error: {e}"

def scrape_website(url: str):
    try:
        d = trafilatura.fetch_url(url)
        res = trafilatura.extract(d) if d else None
        return f"Scraped {url}:\n{res[:1000]}" if res else f"Scrape failed for {url}."
    except Exception as e: return f"Scrape Error: {e}"

AVAILABLE_TOOLS = {
    "get_current_time": get_current_time, "web_search": web_search,
    "execute_shell_command": execute_shell_command, "open_youtube": open_youtube,
    "ui_interact": ui_interact, "smart_browser_interact": smart_browser_interact,
    "click_text_on_screen": click_text_on_screen, "scrape_website": scrape_website
}

TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "get_current_time", "description": "Get time.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "web_search", "description": "Search web.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "execute_shell_command", "description": "Run shell cmd.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "open_youtube", "description": "Open YT.", "parameters": {"type": "object", "properties": {"search_query": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "ui_interact", "description": "UI act.", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["click", "type", "move", "close_tab", "close_app"]}, "text": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}, "app": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "smart_browser_interact", "description": "Browser task.", "parameters": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}}},
    {"type": "function", "function": {"name": "click_text_on_screen", "description": "Click text.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "scrape_website", "description": "Scrape site.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}}
]
