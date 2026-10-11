import os
import sys
import datetime
import subprocess
import webbrowser
from .decorator import tool

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


import re
import html
import time as _time
import urllib.parse
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# -------------------------------------------------------
# Simple in-memory TTL cache for web_search results
# -------------------------------------------------------
_SEARCH_CACHE: Dict[str, tuple] = {}  # {query: (result_str, timestamp)}
_SEARCH_CACHE_TTL = 60  # seconds


def _cache_get(query: str) -> Optional[str]:
    entry = _SEARCH_CACHE.get(query)
    if entry and (_time.time() - entry[1]) < _SEARCH_CACHE_TTL:
        return entry[0]
    return None


def _cache_set(query: str, result: str) -> None:
    # Evict oldest entry if cache grows beyond 100 items
    if len(_SEARCH_CACHE) >= 100:
        oldest = min(_SEARCH_CACHE, key=lambda k: _SEARCH_CACHE[k][1])
        _SEARCH_CACHE.pop(oldest, None)
    _SEARCH_CACHE[query] = (result, _time.time())


def _clean_search_text(text: str) -> str:
    """Clean and normalize search snippet or title text."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    # Strip relative date/timestamp prefixes like '1 day ago · ', '4 hours ago - '
    text = re.sub(r"^(?:\d+\s+(?:days?|hours?|mins?|minutes?|months?|years?)\s+ago\s*[\·\-\—]\s*)+", "", text, flags=re.I)
    text = re.sub(r"^[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s*[\·\-\—]\s*", "", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[\s\.\…]+$", "", text).strip()
    return text


def _extract_domain(url: str) -> str:
    """Extract clean domain name from URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _fetch_ddg_instant_answer(query: str) -> Optional[str]:
    """Fetch DuckDuckGo Instant Answer / Abstract if available."""
    try:
        import httpx
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"}
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        resp = httpx.get(url, params=params, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            data = resp.json()
            abstract = _clean_search_text(data.get("AbstractText", ""))
            answer = _clean_search_text(data.get("Answer", ""))
            heading = _clean_search_text(data.get("Heading", ""))
            if answer:
                return f"{heading}: {answer}" if heading else answer
            if abstract:
                return f"{heading}: {abstract}" if heading else abstract
    except Exception:
        pass
    return None


def _fetch_ddg_lite(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Fetch search results from DuckDuckGo Lite (reliable, lightweight fallback)."""
    results = []
    try:
        import httpx
        from lxml.html import document_fromstring
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"}
        url = "https://lite.duckduckgo.com/lite/"
        resp = httpx.post(url, data={"q": query}, headers=headers, timeout=4.0)
        if resp.status_code == 200 and resp.text:
            tree = document_fromstring(resp.text)
            rows = tree.xpath("//table//tr")
            current_link = None
            current_title = None
            for tr in rows:
                link_nodes = tr.xpath(".//a[contains(@class, 'result-link')]")
                snip_nodes = tr.xpath(".//td[contains(@class, 'result-snippet')]")
                if link_nodes:
                    current_title = _clean_search_text(link_nodes[0].text_content())
                    current_link = link_nodes[0].get("href", "")
                    if "duckduckgo.com/l/?uddg=" in current_link:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(current_link).query)
                        if "uddg" in parsed:
                            current_link = parsed["uddg"][0]
                elif snip_nodes and current_title and current_link:
                    snippet = _clean_search_text(snip_nodes[0].text_content())
                    if snippet and len(snippet) > 10:
                        results.append({
                            "title": current_title,
                            "href": current_link,
                            "body": snippet
                        })
                    current_link = None
                    current_title = None
                if len(results) >= max_results:
                    break
    except Exception:
        pass
    return results


def _fetch_wikipedia_summary(query: str) -> Optional[Dict[str, str]]:
    """Fetch Wikipedia lead summary for knowledge/entity queries."""
    try:
        import httpx
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"}
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1
        }
        resp = httpx.get(search_url, params=search_params, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            hits = resp.json().get("query", {}).get("search", [])
            if hits:
                top_title = hits[0].get("title", "")
                snippet = _clean_search_text(hits[0].get("snippet", ""))

                # Check relevance
                q_words = set(re.findall(r"\w+", query.lower()))
                t_words = set(re.findall(r"\w+", top_title.lower()))
                time_sensitive = {"weather", "news", "today", "yesterday", "tomorrow", "forecast", "score", "price", "stock"}
                if any(k in q_words for k in time_sensitive):
                    return None

                extract_params = {
                    "action": "query",
                    "prop": "extracts",
                    "exintro": 1,
                    "explaintext": 1,
                    "titles": top_title,
                    "format": "json"
                }
                resp_ext = httpx.get(search_url, params=extract_params, headers=headers, timeout=3.5)
                if resp_ext.status_code == 200:
                    pages = resp_ext.json().get("query", {}).get("pages", {})
                    for _, p in pages.items():
                        ext = _clean_search_text(p.get("extract", ""))
                        if ext:
                            return {
                                "title": top_title,
                                "summary": ext[:350] + ("..." if len(ext) > 350 else ""),
                                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(top_title.replace(' ', '_'))}"
                            }
                if snippet:
                    return {
                        "title": top_title,
                        "summary": snippet,
                        "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(top_title.replace(' ', '_'))}"
                    }
    except Exception:
        pass
    return None


def _fetch_ddgs_library(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Try duckduckgo_search / ddgs library."""
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                res = list(ddgs.text(query, max_results=max_results))
                if res:
                    return res
                # Try news if recent or news-related
                res_news = list(ddgs.news(query, max_results=max_results))
                if res_news:
                    return [{"title": r.get("title", ""), "href": r.get("url", ""), "body": r.get("body", "")} for r in res_news]
    except Exception:
        pass
    return []


@tool
def web_search(query: str) -> str:
    """Search the web for current information, facts, weather, news, or anything you don't know."""
    try:
        clean_query = query.strip()
        if not clean_query:
            return "Search query cannot be empty."

        # Check TTL cache first (avoids network entirely for repeated queries)
        cached = _cache_get(clean_query)
        if cached:
            return cached

        # Detect if this is a time-sensitive / news query
        time_sensitive_kws = {"news", "today", "yesterday", "tomorrow", "latest", "forecast",
                               "score", "price", "stock", "weather", "breaking"}
        is_time_sensitive = any(kw in clean_query.lower() for kw in time_sensitive_kws)

        # ── Parallel Tier Fetching ─────────────────────────────────────────────
        # Fire DDG instant answer + DDG Lite concurrently; optionally Wikipedia
        instant_answer: Optional[str] = None
        raw_results: List[Dict] = []
        wiki_info: Optional[Dict] = None

        with ThreadPoolExecutor(max_workers=3) as ex:
            fut_instant = ex.submit(_fetch_ddg_instant_answer, clean_query)
            fut_lite    = ex.submit(_fetch_ddg_lite, clean_query, 4)
            # Wikipedia only for non-time-sensitive queries (saves ~700ms on news)
            fut_wiki = ex.submit(_fetch_wikipedia_summary, clean_query) if not is_time_sensitive else None

            instant_answer = fut_instant.result()
            raw_results    = fut_lite.result()
            if fut_wiki:
                wiki_info = fut_wiki.result()

        # If DDG Lite returned nothing, try the DDGS library as last resort
        if not raw_results:
            raw_results = _fetch_ddgs_library(clean_query, max_results=4)

        # ── Parse & Deduplicate Results ────────────────────────────────────────
        parsed_items = []
        seen_urls: set = set()

        for r in raw_results:
            url = r.get("href", "").strip()
            title = _clean_search_text(r.get("title", ""))
            snippet = _clean_search_text(r.get("body", ""))

            if not title or not snippet or len(snippet) < 15:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            domain = _extract_domain(url)
            title = re.sub(r"\s+[\-\|\–]\s+[A-Za-z0-9\.\s]+$", "", title).strip()

            parsed_items.append({
                "title": title,
                "domain": domain,
                "url": url,
                "snippet": snippet
            })
            if len(parsed_items) >= 4:
                break

        # ── Build Structured Output ────────────────────────────────────────────
        output_sections = []

        if instant_answer:
            output_sections.append(f"Direct Fact / Instant Answer:\n{instant_answer}")
        elif wiki_info:
            output_sections.append(f"Direct Summary ({wiki_info['title']} - Wikipedia):\n{wiki_info['summary']}")

        if parsed_items:
            items_str = []
            for i, item in enumerate(parsed_items, 1):
                domain_label = f" ({item['domain']})" if item['domain'] else ""
                items_str.append(f"[{i}] {item['title']}{domain_label}\n    {item['snippet']}\n    Link: {item['url']}")
            output_sections.append("Web Search Results:\n" + "\n".join(items_str))

        if not output_sections:
            if wiki_info:
                fallback = f"Summary from Wikipedia:\n{wiki_info['title']}: {wiki_info['summary']}\nLink: {wiki_info['url']}"
                _cache_set(clean_query, fallback)
                return fallback
            return f"No results found for '{clean_query}'. Try rephrasing your search keywords."

        result = "\n\n".join(output_sections)
        _cache_set(clean_query, result)
        return result
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
        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(pictures_dir, filename)

        if sys.platform == "darwin":
            subprocess.run(["screencapture", "-x", filepath], check=True)
            return f"Screenshot successfully saved to {filepath}"
        elif sys.platform == "win32":
            ps_cmd = (
                f"Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                f"$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                f"$bmp = New-Object System.Drawing.Bitmap $bounds.width, $bounds.height; "
                f"$g = [System.Drawing.Graphics]::FromImage($bmp); "
                f"$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.size); "
                f"$bmp.Save('{filepath}', [System.Drawing.Imaging.ImageFormat]::Png); "
                f"$g.Dispose(); $bmp.Dispose();"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
            return f"Screenshot successfully saved to {filepath}"
        else:
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                img.save(filepath)
                return f"Screenshot successfully saved to {filepath}"
            except Exception:
                subprocess.run(["import", "-window", "root", filepath], check=True)
                return f"Screenshot successfully saved to {filepath}"
    except Exception as e:
        return f"Failed to capture screenshot: {str(e)}"


@tool
def open_application(app_name: str) -> str:
    """Open an application on the desktop. Use this when the user asks you to open an app like Notepad, Chrome, Calculator, VS Code, Spotify, etc."""
    try:
        clean_name = app_name.lower().strip()
        # Web services that should open in the browser
        web_services = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "github": "https://www.github.com",
            "gmail": "https://mail.google.com",
            "chatgpt": "https://chatgpt.com",
            "twitter": "https://www.twitter.com",
            "x": "https://www.x.com",
            "reddit": "https://www.reddit.com",
            "netflix": "https://www.netflix.com",
        }
        if clean_name in web_services:
            webbrowser.open(web_services[clean_name])
            return f"Opened {app_name} in your browser, Sir."

        app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "chrome": "start chrome",
            "google chrome": "start chrome",
            "edge": "start msedge",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "paint": "mspaint.exe",
            "cmd": "start cmd.exe",
            "terminal": "start wt.exe",
            "task manager": "taskmgr.exe",
            "vscode": "code",
            "code": "code",
            "spotify": "start spotify:",
            "discord": "start discord:",
            "powershell": "start powershell.exe",
            "settings": "start ms-settings:",
            "word": "start winword.exe",
            "excel": "start excel.exe",
        }
        
        exe = app_map.get(clean_name, f"start {app_name}")
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
