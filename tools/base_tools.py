import os
import sys
import datetime
import subprocess
import webbrowser
from langchain_core.tools import tool

# Determine base directory
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tool
def get_current_time() -> str:
    """Get the current date and time. Use this when the user asks what time or date it is."""
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y at %I:%M %p")


@tool
def web_search(query: str) -> str:
    """Search the web for current information. Use this when the user asks about news, facts, or anything you don't know."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "No results found."
        summary = []
        for r in results:
            summary.append(f"- {r.get('title', '')}: {r.get('body', '')}")
        return "\n".join(summary)
    except Exception as e:
        return f"Search failed: {str(e)}"


@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file from disk. Use this when the user asks you to read, inspect, or check a file."""
    try:
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(abs_path):
            return f"File does not exist: {abs_path}"
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(6000)
        return content
    except Exception as e:
        return f"Could not read file: {str(e)}"


@tool
def write_note(note: str) -> str:
    """Write a note to the secretary log. Use this when the user asks you to remember something, take a note, or save a reminder."""
    try:
        log_path = os.path.join(base_dir, "secretary_log.txt")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}] {note}")
        return f"Note saved: '{note}'"
    except Exception as e:
        return f"Failed to save note: {str(e)}"


@tool
def read_notes(max_count: int = 5) -> str:
    """Read recent notes from the secretary log. Use this when the user asks what notes or reminders they have saved."""
    try:
        log_path = os.path.join(base_dir, "secretary_log.txt")
        if not os.path.exists(log_path):
            return "No notes found in the secretary log, Sir."
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        if not lines:
            return "You have no notes saved, Sir."
        recent = lines[-max_count:]
        return "\n".join(recent)
    except Exception as e:
        return f"Failed to read notes: {str(e)}"


@tool
def get_system_status() -> str:
    """Check current system hardware status: CPU percent, RAM memory usage, and battery/power status."""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        ram_percent = mem.percent
        ram_used_gb = round(mem.used / (1024**3), 1)
        ram_total_gb = round(mem.total / (1024**3), 1)
        
        battery = psutil.sensors_battery()
        if battery:
            plugged = "charging" if battery.power_plugged else "on battery"
            battery_info = f"Battery: {battery.percent}% ({plugged})"
        else:
            battery_info = "Desktop PC (no battery)"
            
        return f"CPU: {cpu_percent}%, RAM: {ram_percent}% ({ram_used_gb}/{ram_total_gb} GB), {battery_info}"
    except Exception as e:
        return f"Could not retrieve system stats: {str(e)}"


@tool
def open_website(target: str) -> str:
    """Open a website or search on YouTube/Google in the user's default browser.
    Target can be a URL, website name (e.g. 'youtube', 'github'), or search query like 'youtube Imagine Dragons Believer'."""
    try:
        target_clean = target.strip()
        shortcuts = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "github": "https://www.github.com",
            "twitter": "https://www.twitter.com",
            "x": "https://www.x.com",
            "reddit": "https://www.reddit.com",
            "chatgpt": "https://chatgpt.com",
            "gmail": "https://mail.google.com",
        }
        
        if target_clean.lower() in shortcuts:
            url = shortcuts[target_clean.lower()]
        elif target_clean.startswith("http://") or target_clean.startswith("https://"):
            url = target_clean
        elif "." in target_clean and not " " in target_clean:
            url = f"https://{target_clean}"
        elif target_clean.lower().startswith("youtube "):
            query = target_clean[8:].strip()
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        elif target_clean.lower().startswith("search "):
            query = target_clean[7:].strip()
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        else:
            url = f"https://www.google.com/search?q={target_clean.replace(' ', '+')}"
            
        webbrowser.open(url)
        return f"Opened {url} in your browser, Sir."
    except Exception as e:
        return f"Failed to open website: {str(e)}"


@tool
def take_screenshot() -> str:
    """Take a screenshot of the user's screen and save it to the Pictures folder."""
    try:
        from PIL import ImageGrab
        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(pictures_dir, filename)
        img = ImageGrab.grab()
        img.save(filepath)
        return f"Screenshot successfully saved to {filepath}"
    except Exception as e:
        return f"Failed to capture screenshot: {str(e)}"


@tool
def open_application(app_name: str) -> str:
    """Open an application on the desktop. Use this when the user asks you to open an app like Notepad, Chrome, Calculator, VS Code, Spotify, etc."""
    try:
        app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "chrome": "chrome",
            "google chrome": "chrome",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "paint": "mspaint.exe",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "task manager": "taskmgr.exe",
            "vscode": "code",
            "code": "code",
            "spotify": "spotify",
            "discord": "discord",
            "powershell": "powershell.exe",
            "settings": "start ms-settings:",
            "word": "winword.exe",
            "excel": "excel.exe",
        }
        
        exe = app_map.get(app_name.lower().strip(), app_name)
        subprocess.Popen(exe, shell=True)
        return f"Opened {app_name}, Sir."
    except Exception as e:
        return f"Failed to open {app_name}: {str(e)}"


@tool
def list_files(directory: str = ".") -> str:
    """List files in a directory. Use this when the user asks what files are in a folder."""
    try:
        # Resolve aliases
        user_home = os.path.expanduser("~")
        alias_map = {
            "desktop": os.path.join(user_home, "Desktop"),
            "downloads": os.path.join(user_home, "Downloads"),
            "documents": os.path.join(user_home, "Documents"),
            "pictures": os.path.join(user_home, "Pictures"),
            ".": base_dir,
            "project": base_dir,
        }
        target_dir = alias_map.get(directory.lower().strip(), directory)
        abs_path = os.path.abspath(os.path.expanduser(target_dir))
        
        if not os.path.exists(abs_path):
            return f"Directory does not exist: {abs_path}"
            
        entries = os.listdir(abs_path)
        if not entries:
            return "The directory is empty."
        items = []
        for e in entries[:35]:
            full = os.path.join(abs_path, e)
            if os.path.isdir(full):
                items.append(f"📁 {e}/")
            else:
                size = os.path.getsize(full)
                items.append(f"📄 {e} ({size:,} bytes)")
        return f"Contents of {abs_path}:\n" + "\n".join(items)
    except Exception as e:
        return f"Could not list directory: {str(e)}"
