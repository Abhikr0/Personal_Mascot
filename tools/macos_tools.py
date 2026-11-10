"""
tools/macos_tools.py — macOS-native desktop automation for Friday 2.0.
Uses NSWorkspace / Quartz / Apple Vision and osascript to control apps, media, Notes, etc.
"""
import os
import sys
import subprocess
from typing import Dict, Any, List, Tuple
from .decorator import tool


def _applescript_escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace('"', '\\"')


_MACOS_APP_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "notepad": "TextEdit",
    "textedit": "TextEdit",
    "calc": "Calculator",
    "calculator": "Calculator",
    "explorer": "Finder",
    "file explorer": "Finder",
    "finder": "Finder",
    "settings": "System Settings",
    "system preferences": "System Settings",
    "system settings": "System Settings",
    "apple music": "Music",
    "music": "Music",
    "notes": "Notes",
    "safari": "Safari",
    "terminal": "Terminal",
    "iterm": "iTerm",
    "messages": "Messages",
    "calendar": "Calendar",
    "reminders": "Reminders",
    "mail": "Mail",
    "spotify": "Spotify",
    "discord": "Discord",
    "slack": "Slack",
}


def resolve_macos_app_name(app_name: str) -> str:
    clean = (app_name or "").strip()
    return _MACOS_APP_ALIASES.get(clean.lower(), clean)


def _is_mascot_window(owner: str, title: str, bundle_id: str = "") -> bool:
    title_l = (title or "").lower()
    bid_l = (bundle_id or "").lower()
    return bid_l == "com.github.electron" or "friday mascot" in title_l or "sylphya" in title_l


def get_macos_screen_context() -> Dict[str, Any]:
    """Inspect Screen Recording permission, active app, and visible on-screen windows via Quartz/AppKit."""
    info: Dict[str, Any] = {
        "screen_recording_ok": True,
        "frontmost_app": "",
        "frontmost_bundle_id": "",
        "active_user_window": "",
        "visible_windows": [],
    }
    if sys.platform != "darwin":
        return info

    try:
        import Quartz
        from AppKit import NSWorkspace

        info["screen_recording_ok"] = bool(Quartz.CGPreflightScreenCaptureAccess())

        ws = NSWorkspace.sharedWorkspace()
        front = ws.frontmostApplication()
        if front:
            info["frontmost_app"] = str(front.localizedName() or "")
            info["frontmost_bundle_id"] = str(front.bundleIdentifier() or "")

        pid_to_bid: Dict[int, str] = {}
        for a in ws.runningApplications():
            try:
                pid_to_bid[int(a.processIdentifier())] = str(a.bundleIdentifier() or "")
            except Exception:
                pass

        wins = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        ) or []

        visible: List[Tuple[str, str, str]] = []
        for w in wins:
            if w.get("kCGWindowLayer", 0) != 0:
                continue
            bounds = w.get("kCGWindowBounds") or {}
            if float(bounds.get("Width", 0)) < 40 or float(bounds.get("Height", 0)) < 40:
                continue
            owner = str(w.get("kCGWindowOwnerName") or "")
            title = str(w.get("kCGWindowName") or "").strip()
            pid = int(w.get("kCGWindowOwnerPID") or 0)
            bid = pid_to_bid.get(pid, "")
            if not owner or _is_mascot_window(owner, title, bid):
                continue
            visible.append((owner, title, bid))

        info["visible_windows"] = visible
        if visible:
            top_owner, top_title, _ = visible[0]
            info["active_user_window"] = f"{top_owner} — {top_title}" if top_title else top_owner
    except Exception:
        pass
    return info


def _run_applescript(script: str, timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.returncode != 0:
            return f"Error: {err}" if err else f"osascript failed (code {result.returncode})"
        return out
    except subprocess.TimeoutExpired:
        return "Error: AppleScript timed out"
    except Exception as e:
        return f"Error: {e}"


@tool
def open_app(app_name: str) -> str:
    """Open or bring a macOS app to the front by name.
    Examples: 'Music', 'Notes', 'Safari', 'Messages', 'Calendar', 'Reminders', 'System Settings', 'Google Chrome', 'Visual Studio Code'.
    """
    if not app_name or not app_name.strip():
        return "Please specify an app name."
    resolved = resolve_macos_app_name(app_name)
    proc = subprocess.run(["open", "-a", resolved], capture_output=True, text=True, timeout=5)
    if proc.returncode == 0:
        return f"Opened {resolved}, Sir."
    script = f'tell application "{_applescript_escape(resolved)}" to activate'
    res = _run_applescript(script)
    return f"Opened {resolved}, Sir." if res == "" else res


@tool
def close_app(app_name: str) -> str:
    """Quit a macOS app by name."""
    if not app_name or not app_name.strip():
        return "Please specify an app name."
    resolved = resolve_macos_app_name(app_name)
    script = f'tell application "{_applescript_escape(resolved)}" to quit'
    res = _run_applescript(script)
    return f"Closed {resolved}, Sir." if res == "" else res


@tool
def list_running_apps() -> str:
    """List currently running macOS apps with their bundle IDs."""
    if sys.platform == "darwin":
        try:
            from AppKit import NSWorkspace
            apps = []
            for a in NSWorkspace.sharedWorkspace().runningApplications():
                if a.activationPolicy() == 0:
                    name = str(a.localizedName() or "Unknown")
                    bid = str(a.bundleIdentifier() or "")
                    active_mark = " [active]" if a.isActive() else ""
                    apps.append(f"{name} | {bid}{active_mark}")
            if apps:
                shown = "\n".join(apps[:40])
                more = f"\n... and {len(apps) - 40} more" if len(apps) > 40 else ""
                return f"Running apps ({len(apps)}):\n{shown}{more}"
        except Exception:
            pass

    script = """
    set output to ""
    tell application "System Events"
        set procList to every process whose background only is false
        repeat with proc in procList
            set output to output & name of proc & " | " & (bundle identifier of proc) & linefeed
        end repeat
    end tell
    return output
    """
    result = _run_applescript(script)
    if not result or result.startswith("Error"):
        return f"Could not list apps: {result}"
    lines = [l for l in result.splitlines() if l.strip()]
    if not lines:
        return "No running apps detected."
    shown = "\n".join(lines[:40])
    more = f"\n... and {len(lines) - 40} more" if len(lines) > 40 else ""
    return f"Running apps ({len(lines)}):\n{shown}{more}"


@tool
def get_frontmost_app() -> str:
    """Return the active macOS app, frontmost user window title, and visible background windows."""
    if sys.platform == "darwin":
        ctx = get_macos_screen_context()
        lines = []
        if not ctx["screen_recording_ok"]:
            lines.append("Warning: macOS Screen Recording permission is missing; other apps' window titles may be hidden.")
        if ctx["frontmost_app"]:
            lines.append(f"Frontmost app: {ctx['frontmost_app']} | {ctx['frontmost_bundle_id']}")
        if ctx["visible_windows"]:
            top_owner, top_title, top_bid = ctx["visible_windows"][0]
            lines.append(f"Top visible user window: {top_owner}" + (f" — \"{top_title}\"" if top_title else "") + (f" ({top_bid})" if top_bid else ""))
            if len(ctx["visible_windows"]) > 1:
                others = [f"{o}" + (f" — \"{t}\"" if t else "") for o, t, _ in ctx["visible_windows"][1:6]]
                lines.append("Other visible windows: " + "; ".join(others))
        if lines:
            return "\n".join(lines)

    script = """
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        return name of frontApp & " | " & (bundle identifier of frontApp)
    end tell
    """
    return _run_applescript(script)


@tool
def play_music(song_name: str = "") -> str:
    """Play music or inspect current playback in the macOS Music app.
    - If song_name is given, search for and play that song.
    - If empty, resume playback or report the currently playing track.
    """
    if song_name and song_name.strip():
        song = _applescript_escape(song_name.strip())
        script = f'''
        tell application "Music"
            activate
            set foundTracks to every track of library playlist 1 whose name contains "{song}"
            if length of foundTracks > 0 then
                play foundTracks's item 1
                return "Playing: " & name of foundTracks's item 1 & " by " & artist of foundTracks's item 1
            else
                return "Not found"
            end if
        end tell
        '''
    else:
        script = '''
        tell application "Music"
            activate
            if player state is playing then
                try
                    return "Currently playing: " & name of current track & " by " & artist of current track
                on error
                    return "Already playing"
                end try
            else
                play
                try
                    return "Playback started: " & name of current track & " by " & artist of current track
                on error
                    return "Playback started"
                end try
            end if
        end tell
        '''
    result = _run_applescript(script)
    if result == "Not found":
        return f"Song '{song_name}' not found in Music library, Sir."
    return result


@tool
def control_music(action: str = "toggle") -> str:
    """Control Music / Spotify / Podcasts playback.
    action: 'play', 'pause', 'toggle', 'next', 'previous', 'stop'
    """
    action = action.strip().lower()
    if action not in {"play", "pause", "toggle", "next", "previous", "stop"}:
        return "Invalid action. Use play/pause/toggle/next/previous/stop."

    scripts = {
        "play": 'tell application "Music" to play',
        "pause": 'tell application "Music" to pause',
        "toggle": 'tell application "Music" to playpause',
        "next": 'tell application "Music" to next track',
        "previous": 'tell application "Music" to previous track',
        "stop": 'tell application "Music" to stop',
    }
    return _run_applescript(scripts[action])


@tool
def open_notes_and_write(text: str = "", title: str = "Sylphya Note") -> str:
    """Open the macOS Notes app, create a new note with optional title and text."""
    safe_title = _applescript_escape(title.strip() or "Sylphya Note")
    html_body = _applescript_escape(text.strip()).replace("\n", "<br>")
    script = f'''
    tell application "Notes"
        activate
        set newNote to make new note at folder "Notes" with properties {{body:"<div><b>{safe_title}</b></div><div>{html_body}</div>"}}
        return "Created note: {safe_title}"
    end tell
    '''
    res = _run_applescript(script)
    if res.startswith("Error"):
        # Fallback to default account first folder if "Notes" localized/unavailable
        fallback_script = f'''
        tell application "Notes"
            activate
            set newNote to make new note with properties {{body:"<div><b>{safe_title}</b></div><div>{html_body}</div>"}}
            return "Created note: {safe_title}"
        end tell
        '''
        return _run_applescript(fallback_script)
    return res


@tool
def send_notification(title: str, message: str = "") -> str:
    """Send a macOS notification banner. Requires Notification permission for the host app."""
    safe_title = _applescript_escape(title.strip())
    safe_msg = _applescript_escape(message.strip())
    script = f'''
    display notification "{safe_msg}" with title "{safe_title}"
    '''
    res = _run_applescript(script)
    return f"Notification sent: '{title}' — {message}" if not res.startswith("Error") else res


@tool
def run_shortcut(name: str = "") -> str:
    """Run an Apple Shortcuts workflow by exact name.
    Example: 'Morning Routine', 'Generate Image'.
    """
    if not name or not name.strip():
        return "Please provide a Shortcuts workflow name."
    safe_name = _applescript_escape(name.strip())
    script = f'''
    tell application "Shortcuts"
        activate
        run shortcut named "{safe_name}"
        return "Ran: {safe_name}"
    end tell
    '''
    return _run_applescript(script)


@tool
def set_volume(level: int = 50) -> str:
    """Set macOS system volume (0-100)."""
    level = max(0, min(100, int(level)))
    script = f'set volume output volume {level}'
    res = _run_applescript(script)
    return f"System volume set to {level}%." if res == "" else res


@tool
def get_volume() -> str:
    """Get current macOS output volume (0-100)."""
    script = 'return (output volume of (get volume settings)) as string'
    result = _run_applescript(script)
    if result.startswith("Error"):
        return result
    return f"System volume: {result}%"


@tool
def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    res = _run_applescript(f'open location "{_applescript_escape(url)}"')
    return f"Opened {url} in browser." if res == "" else res


@tool
def lock_screen() -> str:
    """Lock the macOS screen."""
    script = 'tell application "System Events" to keystroke "q" using {control down, command down}'
    return _run_applescript(script)


@tool
def sleep_mac() -> str:
    """Put the Mac to sleep."""
    script = 'tell application "System Events" to sleep'
    return _run_applescript(script)


@tool
def empty_trash() -> str:
    """Empty the macOS Trash."""
    script = 'tell application "Finder" to empty trash'
    return _run_applescript(script)


@tool
def get_battery() -> str:
    """Get macOS battery level and power source."""
    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return "Could not read battery status."
        return " | ".join(lines[:2])
    except Exception as e:
        return f"Error: {e}"


@tool
def open_trackpad_settings() -> str:
    """Open the macOS Trackpad / Mouse settings pane."""
    try:
        subprocess.run(["open", "x-apple.systempreferences:com.apple.Trackpad-Settings.extension"], check=True)
        return "Opened Trackpad Settings, Sir."
    except Exception:
        return _run_applescript('tell application "System Settings" to activate')


@tool
def open_wifi_settings() -> str:
    """Open the macOS Wi-Fi settings pane."""
    try:
        subprocess.run(["open", "x-apple.systempreferences:com.apple.wifi-settings-extension"], check=True)
        return "Opened Wi-Fi Settings, Sir."
    except Exception:
        return _run_applescript('tell application "System Settings" to activate')
