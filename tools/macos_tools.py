"""
tools/macos_tools.py — macOS-native desktop automation for Friday 2.0.
Uses osascript / AppleScript to control apps, media, Notes, Shortcuts, etc.
"""
import subprocess
from .decorator import tool


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
    Examples: 'Music', 'Notes', 'Safari', 'Messages', 'Calendar', 'Reminders', 'System Settings'.
    """
    if not app_name or not app_name.strip():
        return "Please specify an app name."
    app_name = app_name.strip()
    script = f'tell application "{app_name}" to activate'
    return _run_applescript(script)


@tool
def close_app(app_name: str) -> str:
    """Quit a macOS app by name."""
    if not app_name or not app_name.strip():
        return "Please specify an app name."
    app_name = app_name.strip()
    script = f'tell application "{app_name}" to quit'
    return _run_applescript(script)


@tool
def list_running_apps() -> str:
    """List currently running macOS apps with their bundle IDs."""
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
    """Return the name and bundle ID of the currently active (frontmost) macOS app."""
    script = """
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        return name of frontApp & " | " & (bundle identifier of frontApp)
    end tell
    """
    return _run_applescript(script)


@tool
def play_music(song_name: str = "") -> str:
    """Play music in the macOS Music app.
    - If song_name is given, search for and play that song.
    - If empty, just resume/start playback.
    """
    if song_name and song_name.strip():
        song = song_name.strip().replace('"', '\\"')
        script = f'''
        tell application "Music"
            activate
            set foundTracks to every track of library playlist 1 whose name contains "{song}"
            if length of foundTracks > 0 then
                play foundTracks's item 1
                return "Playing: " & name of foundTracks's item 1
            else
                return "Not found"
            end if
        end tell
        '''
    else:
        script = '''
        tell application "Music"
            activate
            if player state is stopped then
                play
                return "Playback started"
            else
                return "Already playing"
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
    safe_title = title.strip().replace('"', '\\"')
    safe_text = text.strip().replace('"', '\\"')
    script = f'''
    tell application "Notes"
        activate
        set newNote to make new note at folder "Notes"
        set name of newNote to "{safe_title}"
        set body of newNote to "{safe_text}"
        return "Created note: {safe_title}"
    end tell
    '''
    return _run_applescript(script)


@tool
def send_notification(title: str, message: str = "") -> str:
    """Send a macOS notification banner. Requires Notification permission for the host app."""
    safe_title = title.strip().replace('"', '\\"')
    safe_msg = message.strip().replace('"', '\\"')
    script = f'''
    display notification "{safe_msg}" with title "{safe_title}"
    '''
    return _run_applescript(script)


@tool
def run_shortcut(name: str = "") -> str:
    """Run an Apple Shortcuts workflow by exact name.
    Example: 'Morning Routine', 'Generate Image'.
    """
    if not name or not name.strip():
        return "Please provide a Shortcuts workflow name."
    safe_name = name.strip().replace('"', '\\"')
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
    return _run_applescript(script)


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
    script = f'open location "{url}"'
    return _run_applescript(script)


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
@tool
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
        return lines[0]
    except Exception as e:
        return f"Error: {e}"


@tool
def open_trackpad_settings() -> str:
    """Open the macOS Trackpad / Mouse settings pane."""
    script = 'tell application "System Preferences" to show pane id "com.apple.preference.trackpad"'
    return _run_applescript(script)


@tool
def open_wifi_settings() -> str:
    """Open the macOS Wi-Fi settings pane."""
    script = 'tell application "System Preferences" to show pane id "com.apple.preference.network"'
    return _run_applescript(script)
